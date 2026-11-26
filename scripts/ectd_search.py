#!/usr/bin/env python3
"""Search the ECTD design space instead of guessing at it.

The ablation in ``ectd_variants.py`` established that ``v:own_cost`` is the
single biggest win, but reading the code shows what it actually is. Both stock
ECTD and the variant score a processor as

    score = start + self_weight * w[task][q] + tail[task][q]

because ``_place_scored`` computes ``eft = start + w`` and then adds the tail on
top. Stock ECTD has ``self_weight = 1`` and a damped tail; ``v:own_cost`` has
``self_weight = 2`` and an undamped tail. So the tuning was never "add the own
cost" -- it was "weight the current task's own cost twice", which is one point
on a one-parameter family.

That makes it searchable. This script sweeps

    self_weight  in SELF_WEIGHTS      how hard to favour a processor where this
                                      task itself is fast, over a fast tail
    damping      in {on, off}         the author-code critical-successor damping
    ranks        in {descendant, mean} the static priority order

and reports pooled geomean makespan per combination, per family, so a
configuration is chosen from evidence rather than from one lucky variant.

Usage:
    python3 scripts/ectd_search.py --data-root corpus --per-cell 2 --out /tmp/search.json
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                             # noqa: E402

_PACKAGE_ROOT = _paths.find_package_root()
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from build_composition import detect_and_parse            # noqa: E402
from ectdbench import policy_table                        # noqa: E402
from ectdbench.engine import (Schedule, optimistic_cost_table,   # noqa: E402
                              ready_order, validate_schedule)
from ectdbench.model import Problem                       # noqa: E402
from ectdbench.proposed import (critical_path_weights, descendant_ranks,  # noqa: E402
                                _place_entry, _place_scored)

LEVEL_RE = re.compile(r"^(\d+)Nodes$")
PROC_RE = re.compile(r"^(\d+)PROCESSORS$")

SELF_WEIGHTS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
DAMPINGS = [True, False]
RANK_MODES = ["descendant", "mean"]


# ------------------------------------------------------------------ corpus

def discover(data_root):
    found = []
    for path in sorted(glob.glob(os.path.join(data_root, "*", "*Nodes",
                                              "*PROCESSORS", "*.txt"))):
        parts = os.path.normpath(path).split(os.sep)
        level_dir, proc_dir, family = parts[-3], parts[-2], parts[-4]
        lm, pm = LEVEL_RE.match(level_dir), PROC_RE.match(proc_dir)
        if not lm or not pm:
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        index = int(stem.split("_")[0]) if stem.split("_")[0].isdigit() else 0
        found.append({
            "path": path,
            "id": "%s/%s/%s/%s" % (family, level_dir, proc_dir, os.path.basename(path)),
            "family": family, "level": int(lm.group(1)), "p": int(pm.group(1)),
            "instance": index,
        })
    return found


def stratified(records, per_cell):
    """Take the first `per_cell` instances from every (family, level, p) cell.

    Sampling by cell rather than at random keeps every family and every
    processor count represented, so a configuration that wins the sweep is not
    winning because the sample was mostly Montage.
    """
    cells = {}
    for r in records:
        cells.setdefault((r["family"], r["level"], r["p"]), []).append(r)
    chosen = []
    for key in sorted(cells):
        chosen.extend(sorted(cells[key], key=lambda r: r["instance"])[:per_cell])
    return chosen


# --------------------------------------------------------------- policies

def build_tails(problem, damping):
    """Return (tail_table, damping_weights) for the scoring rule."""
    p = problem.p
    oct_table, cps = optimistic_cost_table(problem)
    if not damping:
        return oct_table, None
    ranks = descendant_ranks(problem)
    weights = critical_path_weights(problem, ranks, cps)
    damped = [[oct_table[i][q] * weights[i][q] for q in range(p)]
              for i in range(problem.n)]
    return damped, weights


def make_policy(self_weight, damping, rank_mode):
    """A policy with the given self-weight, damping and priority order."""

    def policy(problem, insertion=True):
        p = problem.p
        tail, _ = build_tails(problem, damping)

        if rank_mode == "descendant":
            ranks = descendant_ranks(problem)
        else:
            # Mean of (own cost + tail) per task: a stable reference that does
            # not depend on self_weight, so the order is comparable across the
            # sweep instead of shifting with the parameter being tuned.
            ranks = [sum(problem.w[i][q] + tail[i][q] for q in range(p)) / p
                     for i in range(problem.n)]

        schedule = Schedule(problem, insertion=insertion)
        for task in ready_order(problem, ranks):
            if task == problem.entry:
                _place_entry(schedule, problem, True)
                continue
            starts, finishes = schedule.earliest_slots(task)
            best = None
            for q in range(p):
                start = float(starts[q])
                eft = float(finishes[q])
                score = start + self_weight * float(problem.w[task][q]) + float(tail[task][q])
                key = (score, eft, q)
                if best is None or key < best[0]:
                    best = (key, q, (start, eft))
            schedule.place(task, best[1], slot=best[2])
        return schedule

    return policy


def name_of(sw, damping, rank_mode):
    return "s:sw%.1f_%s_%s" % (sw, "damp" if damping else "raw", rank_mode)


def build_table():
    table = dict(policy_table())
    for sw in SELF_WEIGHTS:
        for damping in DAMPINGS:
            for rank_mode in RANK_MODES:
                table[name_of(sw, damping, rank_mode)] = make_policy(sw, damping, rank_mode)
    return table


# ---------------------------------------------------------------- scoring

def to_problem(record):
    n, p, compc, commc, fmt = detect_and_parse(record["path"])
    edges = [(u, v, float(commc[u][v]))
             for u in range(n) for v in range(n) if commc[u][v] != -1]
    return Problem(compc, edges, name=record["id"],
                   metadata={"family": record["family"], "level": record["level"],
                             "p": p, "format": fmt, "source": record["id"]})


def score_one(record, table):
    try:
        problem = to_problem(record)
    except Exception as exc:
        return {"id": record["id"], "family": record["family"], "p": record["p"],
                "error": "%s: %s" % (type(exc).__name__, exc)}
    makespan, valid = {}, {}
    for name, policy in table.items():
        try:
            schedule = policy(problem)
            makespan[name] = float(schedule.makespan)
            valid[name] = bool(validate_schedule(problem, schedule)["valid"])
        except Exception:
            makespan[name] = None
            valid[name] = False
    return {"id": record["id"], "family": record["family"], "p": record["p"],
            "makespan": makespan, "valid": valid}


_W_TABLE = None


def _init(table):
    global _W_TABLE
    _W_TABLE = table


def _task(record):
    return score_one(record, _W_TABLE)


def geomean(values):
    values = [v for v in values if v and v > 0]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def summarise(rows, policies):
    scored = [r for r in rows if "error" not in r]
    usable = {p: [r["makespan"][p] for r in scored
                  if r["makespan"].get(p) and r["valid"].get(p)] for p in policies}
    pooled = {p: geomean(usable[p]) for p in policies}
    best = min((v for v in pooled.values() if v), default=None)
    families = sorted({r["family"] for r in scored})
    by_family = {}
    for fam in families:
        sub = [r for r in scored if r["family"] == fam]
        by_family[fam] = {p: geomean([r["makespan"][p] for r in sub
                                      if r["makespan"].get(p) and r["valid"].get(p)])
                          for p in policies}
    return {
        "instances": len(scored),
        "failed": len(rows) - len(scored),
        "pooled": {p: round(pooled[p], 2) for p in policies if pooled[p]},
        "pct_over_best": {p: (round(100.0 * (pooled[p] - best) / best, 3)
                              if pooled[p] and best else None) for p in policies},
        "by_family": {f: {p: (round(v, 1) if v else None) for p, v in d.items()}
                      for f, d in by_family.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--per-cell", type=int, default=2,
                    help="instances per (family, nodes, processors) cell")
    ap.add_argument("--out", default="/tmp/search.json")
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    workers = args.workers if args.workers > 0 else max(1, min(4, os.cpu_count() or 1))
    records = stratified(discover(args.data_root), args.per_cell)
    if not records:
        raise SystemExit("no instances found")
    table = build_table()
    policies = list(table)

    print("sample   %d instances, %d policies, %d runs"
          % (len(records), len(policies), len(records) * len(policies)))
    print("workers  %d" % workers)
    started = time.time()
    rows = []
    with Pool(workers, initializer=_init, initargs=(table,)) as pool:
        for i, row in enumerate(pool.imap_unordered(_task, records, chunksize=1), 1):
            rows.append(row)
            if i % 50 == 0 or i == len(records):
                rate = (time.time() - started) / i
                print("  %4d/%d  %.1fs  %.2fs/file  eta %.0fs"
                      % (i, len(records), time.time() - started, rate,
                         rate * (len(records) - i)))

    result = summarise(rows, policies)
    result["sample"] = {"per_cell": args.per_cell, "instances": len(records),
                        "elapsed_seconds": round(time.time() - started, 1),
                        "self_weights": SELF_WEIGHTS, "dampings": DAMPINGS,
                        "rank_modes": RANK_MODES}
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)

    pooled = result["pooled"]
    order = sorted(pooled, key=lambda p: pooled[p])
    print("\n%-26s %10s %8s" % ("policy", "pooled", "vs best"))
    for p in order:
        print("%-26s %10.2f %7.2f%%" % (p, pooled[p], result["pct_over_best"][p]))
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
