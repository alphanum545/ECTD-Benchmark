#!/usr/bin/env python3
"""Run the six ECTD-benchmark policies over the real six-family corpus.

This is the scoring runner the repo has been missing: every other script builds
or measures *compositions*, none of them scores the six policies against the
2,100 real workflow instances.

Corpus
------
Techietal/Task-Scheduling-Dataset, layout ``<Family>/<N>Nodes/<P>PROCESSORS/<i>_<P>.txt``.
Six families, 2,100 files:

    Montage   11 levels x 6 processor counts x 10 instances = 660
    Genome    10 levels x 6 x 10                            = 600   (no 900Nodes)
    LIGO      11 levels x 6 x 10                            = 660
    FFT        5 levels x 6 x  2                            =  60
    GE         5 levels x 6 x  2                            =  60
    LA         5 levels x 6 x  2                            =  60

Instance format is D2: ``n p``, then a 5-by-``p`` preamble, then the ``n`` by
``p`` computation matrix, then the ``n`` by ``n`` communication matrix where
``-1`` means "no edge". Parsing is delegated to ``detect_and_parse`` in
``build_composition.py`` so there is exactly one reader in this repo, not two
that can drift apart.

Sharding
--------
Cost is dominated by the ``n`` by ``n`` communication matrix, so shards are
balanced by weight ``n*n + n*p`` using longest-processing-time-first assignment,
not by file count. A file-count split would put all six 2,079-node GE instances
in one shard and leave the other nineteen idle.

Usage
-----
    python3 scripts/run_benchmark.py --data-root /path/to/data --shard 0 --shards 20
    python3 scripts/run_benchmark.py --data-root /path/to/data --limit 6 --out /tmp/out
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                             # noqa: E402

# Do not rely on the current directory being the repo root: that is the exact
# assumption _paths.py was written to remove. Put the package root on the path
# explicitly so this works from any working directory.
_PACKAGE_ROOT = _paths.find_package_root()
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from build_composition import detect_and_parse            # noqa: E402  single reader
from ectdbench import policy_table                        # noqa: E402
from ectdbench.engine import validate_schedule            # noqa: E402
from ectdbench.model import Problem                       # noqa: E402

LEVEL_RE = re.compile(r"^(\d+)Nodes$")
PROC_RE = re.compile(r"^(\d+)PROCESSORS$")


def discover(data_root):
    """Return one record per instance file, with the weight used for sharding."""
    found = []
    for path in sorted(glob.glob(os.path.join(data_root, "*", "*Nodes", "*PROCESSORS", "*.txt"))):
        parts = os.path.normpath(path).split(os.sep)
        level_dir, proc_dir, family = parts[-3], parts[-2], parts[-4]
        level_match, proc_match = LEVEL_RE.match(level_dir), PROC_RE.match(proc_dir)
        if not level_match or not proc_match:
            continue
        n, p = int(level_match.group(1)), int(proc_match.group(1))
        stem = os.path.splitext(os.path.basename(path))[0]
        index = int(stem.split("_")[0]) if stem.split("_")[0].isdigit() else 0
        found.append({
            "path": path,
            "id": "%s/%s/%s/%s" % (family, level_dir, proc_dir, os.path.basename(path)),
            "family": family,
            "level": n,
            "p": p,
            "instance": index,
            "weight": n * n + n * p,
        })
    return found


def assign_shards(records, shards):
    """Longest-processing-time-first: heaviest file goes to the lightest shard."""
    order = sorted(range(len(records)), key=lambda i: (-records[i]["weight"], records[i]["id"]))
    loads = [0] * shards
    buckets = [[] for _ in range(shards)]
    for i in order:
        target = min(range(shards), key=lambda s: (loads[s], s))
        buckets[target].append(records[i])
        loads[target] += records[i]["weight"]
    return buckets, loads


def to_problem(record):
    """Parse one instance file into a validated Problem."""
    n, p, compc, commc, fmt = detect_and_parse(record["path"])
    edges = [(u, v, float(commc[u][v]))
             for u in range(n) for v in range(n)
             if commc[u][v] != -1]
    problem = Problem(compc, edges, name=record["id"],
                      metadata={"family": record["family"], "level": record["level"],
                                "p": p, "format": fmt, "source": record["id"]})
    return problem, fmt


def score_one(record, table, validate=True):
    """Run every policy on one instance. A policy failure is recorded, not raised."""
    started = time.time()
    try:
        problem, fmt = to_problem(record)
    except Exception as exc:
        return {"id": record["id"], "family": record["family"], "level": record["level"],
                "p": record["p"], "instance": record["instance"],
                "error": "%s: %s" % (type(exc).__name__, exc)}

    makespan, valid, errors, seconds, duplicates = {}, {}, {}, {}, {}
    lower_bound = None
    for name, policy in table.items():
        t0 = time.time()
        try:
            schedule = policy(problem)
            makespan[name] = float(schedule.makespan)
            duplicates[name] = int(schedule.duplicate_count)
            if validate:
                report = validate_schedule(problem, schedule)
                valid[name] = bool(report["valid"])
                if report["errors"]:
                    errors[name] = report["errors"][:5]
                if lower_bound is None:
                    lower_bound = float(report["lower_bound"])
        except Exception as exc:
            makespan[name] = None
            valid[name] = False
            errors[name] = ["%s: %s" % (type(exc).__name__, exc)]
        seconds[name] = round(time.time() - t0, 4)

    return {
        "id": record["id"], "family": record["family"], "level": record["level"],
        "p": record["p"], "instance": record["instance"], "format": fmt,
        "n": problem.original_n, "nodes_with_dummy": problem.n,
        "edges": len(problem.edges), "lower_bound": lower_bound,
        "makespan": makespan, "valid": valid, "errors": errors,
        "duplicates": duplicates, "seconds": seconds,
        "elapsed": round(time.time() - started, 4),
    }


# Worker state. Instances are independent and score_one is pure, so the shard
# can be fanned out across the runner's cores. The table is a dict of
# module-level functions, so it pickles by reference rather than by value.
_WORKER_TABLE = None
_WORKER_VALIDATE = True


def _init_worker(table, validate):
    global _WORKER_TABLE, _WORKER_VALIDATE
    _WORKER_TABLE = table
    _WORKER_VALIDATE = validate


def _score_task(record):
    return score_one(record, _WORKER_TABLE, validate=_WORKER_VALIDATE)


def default_workers():
    """Four cores is the shape this was tuned for; never oversubscribe."""
    return max(1, min(4, os.cpu_count() or 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True,
                    help="directory holding <Family>/<N>Nodes/<P>PROCESSORS/*.txt")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--out", default="bench-out")
    ap.add_argument("--limit", type=int, default=0, help="score only the first N files")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--workers", type=int, default=0,
                    help="parallel worker processes (0 = auto, capped at 4)")
    args = ap.parse_args()

    workers = args.workers if args.workers > 0 else default_workers()

    if not os.path.isdir(args.data_root):
        raise SystemExit("not a directory: %s" % args.data_root)

    records = discover(args.data_root)
    if not records:
        raise SystemExit("no instance files under %s" % args.data_root)
    buckets, loads = assign_shards(records, args.shards)
    mine = buckets[args.shard]
    if args.limit:
        mine = mine[:args.limit]

    # No point starting more processes than there are instances to score.
    workers = max(1, min(workers, len(mine) or 1))

    os.makedirs(args.out, exist_ok=True)
    table = policy_table()
    tag = "shard_%02d" % args.shard
    jsonl_path = os.path.join(args.out, tag + ".jsonl")

    print("corpus   %s" % args.data_root)
    print("files    %d total, %d in this shard" % (len(records), len(mine)))
    print("weight   %d of %d (%.1f%%)" % (loads[args.shard], sum(loads),
                                          100.0 * loads[args.shard] / max(sum(loads), 1)))
    print("policies %s" % ", ".join(table))
    print("workers  %d" % workers)

    started = time.time()
    written = 0
    failures = 0
    validate = not args.no_validate

    def tally(row):
        nonlocal written, failures
        written += 1
        if "error" in row or not all(row.get("valid", {}).values()):
            failures += 1

    with open(jsonl_path, "w") as fh:
        if workers <= 1:
            rows = (score_one(r, table, validate=validate) for r in mine)
            for i, row in enumerate(rows, 1):
                fh.write(json.dumps(row, sort_keys=True) + "\n")
                fh.flush()
                tally(row)
                if i % 25 == 0 or i == len(mine):
                    rate = (time.time() - started) / i
                    print("  %4d/%d  %.1fs elapsed  %.2fs/file  eta %.0fs"
                          % (i, len(mine), time.time() - started, rate,
                             rate * (len(mine) - i)))
        else:
            # imap keeps input order, so the jsonl is byte-identical to a
            # serial run for the same shard. chunksize=1 keeps the progress
            # line responsive instead of batching the whole shard up front.
            with Pool(workers, initializer=_init_worker,
                      initargs=(table, validate)) as pool:
                for i, row in enumerate(pool.imap(_score_task, mine, chunksize=1), 1):
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
                    fh.flush()
                    tally(row)
                    if i % 25 == 0 or i == len(mine):
                        rate = (time.time() - started) / i
                        print("  %4d/%d  %.1fs elapsed  %.2fs/file  eta %.0fs"
                              % (i, len(mine), time.time() - started, rate,
                                 rate * (len(mine) - i)))

    summary = {
        "shard": args.shard, "shards": args.shards,
        "files_total": len(records), "files_scored": written,
        "weight": loads[args.shard], "weight_total": sum(loads),
        "failures": failures,
        "elapsed_seconds": round(time.time() - started, 2),
        "workers": workers,
        "data_root": os.path.abspath(args.data_root),
    }
    with open(os.path.join(args.out, tag + ".json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
