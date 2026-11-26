#!/usr/bin/env python3
"""Merge the 20 shard outputs into one comparison table.

Reports the same statistic the suite's own README uses: pooled geometric mean
makespan per policy, plus strict-win counts and per-family breakdowns. A policy
that is missing or invalid on an instance is excluded from that instance's
comparison rather than being given a favourable or unfavourable placeholder.

Usage:
    python3 scripts/aggregate_benchmark.py --results bench-out --out docs/benchmark
"""
import argparse
import collections
import glob
import json
import math
import os
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="bench-out")
    ap.add_argument("--out", default="docs/benchmark")
    ap.add_argument("--title", default="ECTD benchmark on the real six-family corpus")
    args = ap.parse_args()

    rows = load(args.results)
    if not rows:
        raise SystemExit("no shard_*.jsonl under %s" % args.results)

    scored = [r for r in rows if "error" not in r]
    errors = [r for r in rows if "error" in r]
    policies = sorted({p for r in scored for p in r["makespan"]})

    # A policy counts only where it produced a valid schedule.
    usable = {p: [r for r in scored if r["makespan"].get(p) and r["valid"].get(p)]
              for p in policies}

    pooled = {p: geomean([r["makespan"][p] for r in usable[p]]) for p in policies}
    ranked = sorted((p for p in policies if pooled[p]), key=lambda p: pooled[p])
    best_pooled = pooled[ranked[0]] if ranked else None

    # Strict wins: lowest makespan on an instance, counting ties as shared.
    wins = collections.Counter()
    ties = collections.Counter()
    for r in scored:
        live = {p: r["makespan"][p] for p in policies
                if r["makespan"].get(p) and r["valid"].get(p)}
        if not live:
            continue
        low = min(live.values())
        leaders = [p for p, v in live.items() if v == low]
        if len(leaders) == 1:
            wins[leaders[0]] += 1
        else:
            for p in leaders:
                ties[p] += 1

    # Per-instance leaderboard. One row per (instance, leading policy), so a
    # shared win appears once per policy that shared it. This is the evidence
    # behind the win counts: without it the counts are unfalsifiable.
    leader_rows = []
    for r in scored:
        live = {p: r["makespan"][p] for p in policies
                if r["makespan"].get(p) and r["valid"].get(p)}
        if not live:
            continue
        low = min(live.values())
        leaders = sorted(p for p, v in live.items() if v == low)
        rest = sorted(v for v in live.values() if v > low)
        next_best = rest[0] if rest else None
        margin = None
        if next_best:
            margin = round(100.0 * (next_best - low) / low, 4)
        for p in leaders:
            leader_rows.append({
                "id": r["id"],
                "family": r.get("family", ""),
                "level": r.get("level", ""),
                "p": r.get("p", ""),
                "policy": p,
                "makespan": round(low, 6),
                "next_best": None if next_best is None else round(next_best, 6),
                "margin_pct": margin,
                "shared": len(leaders) > 1,
                "leaders": "|".join(leaders),
            })
    leader_rows.sort(key=lambda d: (d["family"], str(d["level"]), d["p"], d["id"], d["policy"]))

    families = sorted({r["family"] for r in scored})
    by_family = {}
    for fam in families:
        subset = [r for r in scored if r["family"] == fam]
        by_family[fam] = {
            "instances": len(subset),
            "pooled": {p: geomean([r["makespan"][p] for r in subset
                                   if r["makespan"].get(p) and r["valid"].get(p)])
                       for p in policies},
            "wins": {p: sum(1 for r in subset
                            if r["makespan"].get(p) and r["valid"].get(p)
                            and r["makespan"][p] == min(v for k, v in r["makespan"].items()
                                                        if v and r["valid"].get(k)))
                     for p in policies},
        }

    by_p = {}
    for p_count in sorted({r["p"] for r in scored}):
        subset = [r for r in scored if r["p"] == p_count]
        by_p[str(p_count)] = {
            "instances": len(subset),
            "pooled": {p: geomean([r["makespan"][p] for r in subset
                                   if r["makespan"].get(p) and r["valid"].get(p)])
                       for p in policies},
        }

    def pct(p):
        if not best_pooled or not pooled[p]:
            return None
        return round(100.0 * (pooled[p] - best_pooled) / best_pooled, 2)

    summary = {
        "title": args.title,
        "instances_scored": len(scored),
        "instances_failed": len(errors),
        "policies": policies,
        "ranking": ranked,
        "pooled_geomean_makespan": {p: round(pooled[p], 2) for p in policies if pooled[p]},
        "pct_over_best": {p: pct(p) for p in policies if pooled[p]},
        "strict_wins": dict(wins),
        "shared_wins": dict(ties),
        "at_or_best": {p: wins.get(p, 0) + ties.get(p, 0) for p in policies},
        "by_family": by_family,
        "by_processors": by_p,
        "invalid_schedules": {
            p: sum(1 for r in scored if r["valid"].get(p) is False) for p in policies
        },
        "errors": [{"id": r["id"], "error": r["error"]} for r in errors][:50],
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)

    header = ["policy", "pooled", "pct_over_best", "strict_wins", "shared_wins", "invalid"]
    lines = [",".join(header)]
    for p in ranked:
        lines.append(",".join([
            p,
            "%.2f" % pooled[p],
            "" if pct(p) is None else "%.2f" % pct(p),
            str(wins.get(p, 0)),
            str(ties.get(p, 0)),
            str(summary["invalid_schedules"][p]),
        ]))
    with open(os.path.join(args.out, "summary.csv"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    # winners.csv: the per-instance evidence behind the win counts.
    leader_header = ["id", "family", "level", "p", "policy", "makespan",
                     "next_best", "margin_pct", "shared", "leaders"]
    leader_lines = [",".join(leader_header)]
    for d in leader_rows:
        leader_lines.append(",".join([
            str(d["id"]), d["family"], str(d["level"]), str(d["p"]), d["policy"],
            "%.6f" % d["makespan"],
            "" if d["next_best"] is None else "%.6f" % d["next_best"],
            "" if d["margin_pct"] is None else "%.4f" % d["margin_pct"],
            "1" if d["shared"] else "0",
            d["leaders"],
        ]))
    with open(os.path.join(args.out, "winners.csv"), "w") as fh:
        fh.write("\n".join(leader_lines) + "\n")

    print("%d instances scored, %d failed" % (len(scored), len(errors)))
    print("%-8s %12s %8s %8s %8s" % ("policy", "pooled", "vs best", "wins", "invalid"))
    for p in ranked:
        print("%-8s %12.2f %7s%% %8d %8d"
              % (p, pooled[p], "" if pct(p) is None else "%.2f" % pct(p),
                 wins.get(p, 0), summary["invalid_schedules"][p]))
    print("\nwrote %s, %s and %s (%d leader rows)"
          % (os.path.join(args.out, "summary.json"),
             os.path.join(args.out, "summary.csv"),
             os.path.join(args.out, "winners.csv"), len(leader_rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
