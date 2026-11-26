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

    # Compact ECTD leaderboard, printed so it lands in the job log. The full
    # per-instance rows are in winners.csv; this is the readable digest.
    ectd = [d for d in leader_rows if d["policy"] == "ECTD"]
    if ectd:
        print("\n=== ECTD at-or-best: %d instances ===" % len(ectd))
        print("exclusive: %d   shared: %d"
              % (sum(1 for d in ectd if not d["shared"]),
                 sum(1 for d in ectd if d["shared"])))
        for label, key in (("family", "family"), ("processors", "p")):
            print("\nby %s:" % label)
            groups = collections.Counter(d[key] for d in ectd)
            for k in sorted(groups, key=lambda x: str(x)):
                print("  %-10s %4d" % (k, groups[k]))
        margins = sorted(d["margin_pct"] for d in ectd if d["margin_pct"] is not None)
        if margins:
            def q(f):
                return margins[min(len(margins) - 1, int(f * len(margins)))]
            print("\nmargin over next best (%%): min %.2f  q1 %.2f  median %.2f  q3 %.2f  max %.2f"
                  % (margins[0], q(0.25), q(0.5), q(0.75), margins[-1]))
            # margin is measured against the next-best policy, so it is
            # positive by construction on every leader row. Counting it would
            # always return the row count and say nothing. Report the split
            # that actually distinguishes rows instead.
            print("outright win (no tie): %d   tied: %d"
                  % (sum(1 for d in ectd if not d["shared"]),
                     sum(1 for d in ectd if d["shared"])))
        print("\ntop 10 by margin:")
        for d in sorted(ectd, key=lambda d: -(d["margin_pct"] or 0))[:10]:
            print("  %-46s %8.2f  +%.2f%%  %s"
                  % (d["id"], d["makespan"], d["margin_pct"] or 0.0,
                     "shared" if d["shared"] else "sole"))

        # ECTD-only slice. winners.csv carries every policy and is too large to
        # fetch in one read; this holds just the ECTD rows so the list of
        # winning instances can actually be retrieved and inspected.
        with open(os.path.join(args.out, "winners_ectd.csv"), "w") as fh:
            fh.write("\n".join(
                leader_lines[0:1]
                + [line for line, d in zip(leader_lines[1:], leader_rows)
                   if d["policy"] == "ECTD"]
            ) + "\n")
        print("\nwrote %s (%d rows)"
              % (os.path.join(args.out, "winners_ectd.csv"), len(ectd)))

        # Ranking of all six policies restricted to the instances ECTD is
        # at-or-best on. This is a CONDITIONAL slice, not a global ranking:
        # the set is selected by ECTD's own result, so ECTD leads by
        # construction. What it measures is the gap to each rival inside
        # ECTD's winning regime, which is what "who is second" means here.
        win_ids = {d["id"] for d in ectd}
        subset = [r for r in scored if r["id"] in win_ids]
        sub_pooled = {p: geomean([r["makespan"][p] for r in subset
                                  if r["makespan"].get(p) and r["valid"].get(p)])
                      for p in policies}
        sub_ranked = sorted((p for p in policies if sub_pooled[p]),
                            key=lambda p: sub_pooled[p])
        sub_best = sub_pooled[sub_ranked[0]] if sub_ranked else None

        rank_rows = []
        rank_sum = collections.Counter()
        second = collections.Counter()
        dist = {p: collections.Counter() for p in policies}
        for r in subset:
            live = {p: r["makespan"][p] for p in policies
                    if r["makespan"].get(p) and r["valid"].get(p)}
            if not live:
                continue
            order = sorted(live, key=lambda p: (live[p], p))
            for i, p in enumerate(order):
                rank_sum[p] += i + 1
                dist[p][i + 1] += 1
                if i == 1:
                    second[p] += 1
            rank_rows.append((r, live, order))
        n_rows = len(rank_rows) or 1

        print("\n=== Ranking on the %d instances where ECTD is at-or-best ===" % len(ectd))
        print("conditional slice: ECTD is at-or-best on every row by construction")
        print("%-8s %12s %10s %10s %6s" % ("policy", "pooled", "vs ECTD", "mean rank", "2nd"))
        for p in sub_ranked:
            gap = 100.0 * (sub_pooled[p] - sub_best) / sub_best if sub_best else 0.0
            print("%-8s %12.2f %9.2f%% %10.3f %6d"
                  % (p, sub_pooled[p], gap, rank_sum[p] / float(n_rows), second[p]))

        print("\nrank distribution (1=best) on the subset:")
        print("  %-8s %s" % ("policy", " ".join("%5d" % k for k in range(1, len(policies) + 1))))
        for p in sub_ranked:
            print("  %-8s %s" % (p, " ".join("%5d" % dist[p].get(k, 0)
                                              for k in range(1, len(policies) + 1))))

        for label, key in (("family", "family"), ("processors", "p")):
            print("\nby %s (pooled order on the subset):" % label)
            groups = sorted({str(r.get(key, "")) for r, _, _ in rank_rows})
            for g in groups:
                g_rows = [r for r, _, _ in rank_rows if str(r.get(key, "")) == g]
                gp = {p: geomean([r["makespan"][p] for r in g_rows
                                  if r["makespan"].get(p) and r["valid"].get(p)])
                      for p in policies}
                go = sorted((p for p in policies if gp[p]), key=lambda p: gp[p])
                print("  %-10s n=%-4d %s" % (g, len(g_rows),
                      " > ".join("%s(%.1f)" % (p, gp[p]) for p in go)))

        # Per-instance table: the order string plus every makespan, so the
        # ranking above is reproducible from one small file.
        rank_header = (["id", "family", "level", "p", "order"]
                       + ["%s_makespan" % p for p in sub_ranked])
        rank_lines = [",".join(rank_header)]
        for r, live, order in sorted(rank_rows, key=lambda t: (t[0].get("family", ""),
                                                              str(t[0].get("level", "")),
                                                              t[0].get("p", 0), t[0]["id"])):
            rank_lines.append(",".join(
                [str(r["id"]), r.get("family", ""), str(r.get("level", "")),
                 str(r.get("p", "")), ">".join(order)]
                + ["%.6f" % live[p] if p in live else "" for p in sub_ranked]))
        with open(os.path.join(args.out, "ranking_on_ectd_wins.csv"), "w") as fh:
            fh.write("\n".join(rank_lines) + "\n")
        print("\nwrote %s (%d rows)"
              % (os.path.join(args.out, "ranking_on_ectd_wins.csv"), len(rank_rows)))

        summary["ectd_wins_slice"] = {
            "instances": len(rank_rows),
            "note": "conditional slice: ECTD is at-or-best on every row by construction",
            "ranking": sub_ranked,
            "pooled_geomean_makespan": {p: round(sub_pooled[p], 2) for p in sub_ranked},
            "pct_over_ectd": {p: round(100.0 * (sub_pooled[p] - sub_best) / sub_best, 2)
                              for p in sub_ranked if sub_best},
            "mean_rank": {p: round(rank_sum[p] / float(n_rows), 4) for p in sub_ranked},
            "rank2_count": {p: second.get(p, 0) for p in sub_ranked},
        }
        with open(os.path.join(args.out, "summary.json"), "w") as fh:
            json.dump(summary, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
