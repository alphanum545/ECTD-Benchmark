#!/usr/bin/env python3
"""Prove a refactor changed nothing, on a small stratified sample.

Two independent checks:

1. Rank equality. A frozen copy of the pre-patch ``descendant_ranks`` (the
   set-bit peeling walk) is compared against the live implementation on
   synthetic graphs of two densities and on real corpus instances. Equality is
   exact, not a tolerance: both routines visit set bits in ascending order, so
   they accumulate the same floats in the same order and must agree bit for bit.
   A tolerance here would hide exactly the kind of reordering that changes a
   heap key at a tie.

2. Schedule equality. Every policy and variant is scored on a stratified sample
   and each makespan is compared against a committed baseline artifact. Any
   difference means the refactor changed behaviour and the job fails.

The baseline is written once with ``--write-baseline`` from a known-good tree and
committed. It is the contract: a refactor that is supposed to be behaviour
preserving must reproduce it exactly.

Usage:
    python3 scripts/check_equivalence.py --data-root corpus \
        --baseline docs/benchmark/equivalence_baseline.json
    python3 scripts/check_equivalence.py --data-root corpus \
        --baseline docs/benchmark/equivalence_baseline.json --write-baseline
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                             # noqa: E402

_PACKAGE_ROOT = _paths.find_package_root()
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from build_composition import detect_and_parse            # noqa: E402
from ectdbench import policy_table                        # noqa: E402
from ectdbench.engine import validate_schedule            # noqa: E402
from ectdbench.model import Problem                       # noqa: E402
from ectdbench.proposed import descendant_ranks           # noqa: E402
from ectd_variants import VARIANTS                        # noqa: E402

LEVEL_RE = __import__("re").compile(r"^(\d+)Nodes$")
PROC_RE = __import__("re").compile(r"^(\d+)PROCESSORS$")


# ------------------------------------------------------------------ reference

def reference_descendant_ranks(problem):
    """The pre-patch implementation, frozen.

    Peels one set bit at a time with ``bits & -bits`` and ``bits ^= low``. Kept
    verbatim so the patched version has something exact to be compared against.
    Do not "optimise" this: it is the specification.
    """
    dct = [float(problem.min_w[i]) for i in range(problem.n)]
    for task in range(problem.n):
        dct[task] += sum(problem.edges[task, child] for child in problem.succ[task])

    descendants = [0] * problem.n
    ranks = [0.0] * problem.n
    for task in reversed(problem.topo):
        bits = 0
        for child in problem.succ[task]:
            bits |= (1 << child) | descendants[child]
        descendants[task] = bits
        total = float(dct[task])
        while bits:
            lowest = bits & -bits
            child = lowest.bit_length() - 1
            total += float(dct[child])
            bits ^= lowest
        ranks[task] = total
    return ranks


# ------------------------------------------------------------------ problems

def synthetic(n, p, dense, seed):
    """A DAG with either e ~ 3n (sparse) or e ~ n^2/4 (dense)."""
    rng = random.Random(seed)
    w = [[rng.uniform(1.0, 100.0) for _ in range(p)] for _ in range(n)]
    seen = set()
    edges = []
    if dense:
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < 0.5:
                    seen.add((u, v))
                    edges.append((u, v, rng.uniform(1.0, 50.0)))
    else:
        for u in range(n):
            for _ in range(3):
                v = u + 1 + rng.randrange(max(1, n // 8))
                if v < n and (u, v) not in seen:
                    seen.add((u, v))
                    edges.append((u, v, rng.uniform(1.0, 50.0)))
    return Problem(w, edges)


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
    cells = {}
    for r in records:
        cells.setdefault((r["family"], r["level"], r["p"]), []).append(r)
    chosen = []
    for key in sorted(cells):
        chosen.extend(sorted(cells[key], key=lambda r: r["instance"])[:per_cell])
    return chosen


def to_problem(record):
    n, p, compc, commc, _fmt = detect_and_parse(record["path"])
    edges = [(u, v, float(commc[u][v]))
             for u in range(n) for v in range(n) if commc[u][v] != -1]
    return Problem(compc, edges, name=record["id"],
                   metadata={"family": record["family"], "p": p})


# --------------------------------------------------------------------- checks

def check_ranks(records):
    """Compare live descendant_ranks against the frozen reference."""
    failures = []
    checked = 0

    for seed in range(20):
        for dense in (False, True):
            for n in (5, 20, 60, 150, 400):
                problem = synthetic(n, 4, dense, seed)
                want = reference_descendant_ranks(problem)
                got = descendant_ranks(problem)
                checked += 1
                if want != got:
                    failures.append({
                        "case": "synthetic seed=%d dense=%s n=%d" % (seed, dense, n),
                        "max_abs_diff": max(abs(a - b) for a, b in zip(want, got)),
                    })

    for record in records:
        try:
            problem = to_problem(record)
        except Exception:
            continue
        want = reference_descendant_ranks(problem)
        got = descendant_ranks(problem)
        checked += 1
        if want != got:
            failures.append({
                "case": record["id"],
                "max_abs_diff": max(abs(a - b) for a, b in zip(want, got)),
            })

    return {"checked": checked, "failures": failures}


def check_schedules(records):
    """Score every policy and variant; return makespans keyed by instance."""
    table = dict(policy_table())
    table.update(VARIANTS)
    out = {}
    invalid = []
    for record in records:
        try:
            problem = to_problem(record)
        except Exception as exc:
            out[record["id"]] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            continue
        row = {}
        for name, policy in table.items():
            try:
                schedule = policy(problem)
                row[name] = round(float(schedule.makespan), 6)
                if not validate_schedule(problem, schedule)["valid"]:
                    invalid.append("%s / %s" % (record["id"], name))
            except Exception as exc:
                row[name] = "error: %s" % type(exc).__name__
        out[record["id"]] = row
    return out, invalid


def compare(baseline, current):
    """Exact comparison of two makespan maps."""
    failures = []
    missing = sorted(set(baseline) - set(current))
    added = sorted(set(current) - set(baseline))
    for instance in missing:
        failures.append({"instance": instance, "reason": "missing from current run"})
    for instance in added:
        failures.append({"instance": instance, "reason": "not in baseline"})
    for instance in sorted(set(baseline) & set(current)):
        want, got = baseline[instance], current[instance]
        for policy in sorted(set(want) | set(got)):
            a, b = want.get(policy), got.get(policy)
            if a != b:
                failures.append({
                    "instance": instance, "policy": policy,
                    "baseline": a, "current": b,
                })
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--per-cell", type=int, default=1)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--out", default="equivalence-report.json")
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()

    records = stratified(discover(args.data_root), args.per_cell)
    if not records:
        raise SystemExit("no instances found under %s" % args.data_root)
    print("sample: %d instances" % len(records))

    print("\n[1/2] rank equality vs frozen reference")
    ranks = check_ranks(records)
    print("  checked %d cases, %d failures" % (ranks["checked"], len(ranks["failures"])))
    for failure in ranks["failures"][:5]:
        print("    %s (max diff %.3e)" % (failure["case"], failure["max_abs_diff"]))

    print("\n[2/2] schedule equality vs baseline")
    current, invalid = check_schedules(records)
    print("  scored %d instances, %d invalid schedules" % (len(current), len(invalid)))
    for item in invalid[:5]:
        print("    invalid: %s" % item)

    report = {
        "per_cell": args.per_cell,
        "instances": len(records),
        "rank_equality": {
            "checked": ranks["checked"],
            "failures": ranks["failures"],
        },
        "invalid_schedules": invalid,
    }

    if args.write_baseline:
        payload = {"per_cell": args.per_cell, "makespans": current}
        os.makedirs(os.path.dirname(os.path.abspath(args.baseline)), exist_ok=True)
        with open(args.baseline, "w") as fh:
            json.dump(payload, fh, indent=1, sort_keys=True)
        print("\nwrote baseline %s (%d instances)" % (args.baseline, len(current)))
        report["baseline_written"] = args.baseline
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
        return 0

    if not os.path.exists(args.baseline):
        raise SystemExit("baseline not found: %s" % args.baseline)
    with open(args.baseline) as fh:
        baseline = json.load(fh)["makespans"]

    schedule_failures = compare(baseline, current)
    print("  compared %d instances, %d differences"
          % (len(current), len(schedule_failures)))
    for failure in schedule_failures[:5]:
        print("    %s" % json.dumps(failure, sort_keys=True))
    report["schedule_equality"] = {
        "compared": len(current),
        "differences": schedule_failures,
    }

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    ok = not ranks["failures"] and not schedule_failures and not invalid
    print("\n%s" % ("EQUIVALENT" if ok else "NOT EQUIVALENT"))
    if not ok:
        print("  rank failures: %d" % len(ranks["failures"]))
        print("  schedule differences: %d" % len(schedule_failures))
        print("  invalid schedules: %d" % len(invalid))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
