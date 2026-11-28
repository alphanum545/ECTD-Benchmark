#!/usr/bin/env python3
"""Held-out validation for the ECTD rank parameters.

The problem this closes
-----------------------
``beta`` and ``gamma`` were both selected by measuring them on the same 2,094
instances used to report the final number. That makes 1360.64 an in-sample
figure: it is the best value of a search over 5 configurations, read off the
same data the search ran on. A reviewer is entitled to ask whether the choice
survives instances the search never saw.

What this does
--------------
Splits the corpus *within every cell* (family, level, processors) so that each
cell contributes instances to both halves. Splitting within the cell rather
than by cell is deliberate: a by-cell split would put whole families or whole
processor counts on one side, and the test half would then differ from the
training half in ways that have nothing to do with the parameters.

Re-selects ``beta``/``gamma`` on the training half only, then reports the
selected configuration on the test half. Repeats the split many times, because
one split is one sample and the interesting question is whether the selection
is stable, not whether it happened to win once.

It reads the per-instance results already produced by ``run_variants.py``, so
it re-runs no policy. Point ``--results`` at a shard directory.

Usage:
    python3 scripts/held_out_validation.py --results bench-out --trials 200
"""
import argparse
import collections
import glob
import json
import math
import os
import random
import sys


def load(results_dir):
    rows, seen = [], set()
    for path in sorted(glob.glob(os.path.join(results_dir, "shard_*.jsonl"))):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if "error" in row:
                    continue
                if row["id"] in seen:
                    raise SystemExit("duplicate instance across shards: %s" % row["id"])
                seen.add(row["id"])
                rows.append(row)
    return rows


def geomean(values):
    values = [v for v in values if v and v > 0]
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def pooled(rows, policy):
    """Pooled geometric mean makespan, over instances where the policy is valid.

    Same statistic and same exclusion rule as ``aggregate_benchmark.py``, so the
    numbers here are comparable to the published table.
    """
    return geomean([r["makespan"][policy] for r in rows
                    if r["makespan"].get(policy) and r["valid"].get(policy)])


def cells_of(rows):
    cells = collections.defaultdict(list)
    for row in rows:
        cells[(row["family"], row["level"], row["p"])].append(row)
    for key in cells:
        cells[key].sort(key=lambda r: r["instance"])
    return cells


def split_within_cells(cells, fraction, rng):
    """Stratified split: every cell contributes to both halves.

    ``max(1, ...)`` on each side matters. Some cells hold only two instances
    (the 50-node and 100-node levels), and a naive round() would hand both to
    one half, silently removing that cell from the other.
    """
    train, test = [], []
    for key in sorted(cells):
        members = cells[key]
        order = list(range(len(members)))
        rng.shuffle(order)
        cut = int(round(len(members) * fraction))
        cut = max(1, min(len(members) - 1, cut)) if len(members) > 1 else 1
        train.extend(members[i] for i in order[:cut])
        test.extend(members[i] for i in order[cut:])
    return train, test


def candidate_family(policies):
    """The configurations the search actually ranged over.

    Restricted to the ``ectd_succ_own`` family on purpose. The claim under test
    is that beta=0.5/gamma=0.5 was a legitimate selection from its own family,
    not that it beats every policy in the file; the latter is a different
    question and is reported separately as the test-half ranking.
    """
    return sorted(p for p in policies if p.startswith("v:ectd_succ_own"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="bench-out")
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--fraction", type=float, default=0.7,
                    help="share of each cell used for selection")
    ap.add_argument("--seed", type=int, default=20261127)
    ap.add_argument("--out", default="docs/benchmark/held_out.json")
    args = ap.parse_args()

    rows = load(args.results)
    if not rows:
        raise SystemExit("no usable rows under %s" % args.results)
    policies = sorted({p for r in rows for p in r["makespan"]})
    candidates = candidate_family(policies)
    if not candidates:
        raise SystemExit("no v:ectd_succ_own policies in the results")

    cells = cells_of(rows)
    rng = random.Random(args.seed)

    selections = collections.Counter()
    test_best = collections.Counter()
    regrets = []
    first = None

    for trial in range(args.trials):
        train, test = split_within_cells(cells, args.fraction, rng)
        train_score = {p: pooled(train, p) for p in candidates}
        chosen = min(train_score, key=lambda p: (train_score[p], p))
        selections[chosen] += 1

        test_score = {p: pooled(test, p) for p in policies}
        best = min(test_score, key=lambda p: (test_score[p], p))
        test_best[best] += 1
        regrets.append(100.0 * (test_score[chosen] - test_score[best]) / test_score[best])

        if first is None:
            first = {"train": train, "test": test, "chosen": chosen,
                     "train_score": train_score, "test_score": test_score}

    regrets.sort()
    n = len(regrets)
    report = {
        "title": "Held-out validation of the ECTD rank parameters",
        "instances": len(rows),
        "cells": len(cells),
        "trials": args.trials,
        "fraction": args.fraction,
        "seed": args.seed,
        "candidates": candidates,
        "selection_counts": dict(selections),
        "test_best_counts": dict(test_best.most_common()),
        "regret_pct": {
            "mean": round(sum(regrets) / n, 4),
            "median": round(regrets[n // 2], 4),
            "p90": round(regrets[int(n * 0.9)], 4),
            "max": round(regrets[-1], 4),
        },
        "zero_regret_trials": sum(1 for x in regrets if x < 1e-9),
        "example_split": {
            "train_instances": len(first["train"]),
            "test_instances": len(first["test"]),
            "chosen": first["chosen"],
            "train_pooled": {p: round(v, 2) for p, v in sorted(
                first["train_score"].items(), key=lambda kv: kv[1])},
            "test_pooled": {p: round(v, 2) for p, v in sorted(
                first["test_score"].items(), key=lambda kv: kv[1])},
        },
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")

    print("instances %d in %d cells, %d trials, %.0f%% per cell for selection"
          % (len(rows), len(cells), args.trials, 100 * args.fraction))
    print()
    print("selected on the training half:")
    for policy, count in selections.most_common():
        print("  %-32s %d/%d" % (policy, count, args.trials))
    print()
    print("regret against the test-half best, %%: mean %.3f  median %.3f  p90 %.3f  max %.3f"
          % (report["regret_pct"]["mean"], report["regret_pct"]["median"],
             report["regret_pct"]["p90"], report["regret_pct"]["max"]))
    print("trials where the selection was also test-best: %d/%d"
          % (report["zero_regret_trials"], args.trials))
    print()
    print("example split (%d train / %d test), chosen %s:"
          % (len(first["train"]), len(first["test"]), first["chosen"]))
    for policy, value in sorted(first["test_score"].items(), key=lambda kv: kv[1])[:8]:
        print("  %-32s test %10.2f" % (policy, value))
    print()
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
