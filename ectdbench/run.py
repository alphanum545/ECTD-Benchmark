"""Build the benchmark suite and score the six policies over it.

Usage
-----
    python3 -m ectdbench.run --out results --seeds 12

Outputs, all deterministic given the seeds:
    results/manifest.json          suite definition, protocol, provenance
    results/instances.jsonl        every instance, one JSON object per line
    results/scores.csv             per-instance makespan for every policy
    results/summary.json           pooled geometric means, ranks, win counts
    results/validation.json        structural and feasibility checks
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import sys
import time

from . import __version__, policy_table
from .engine import validate_schedule
from .generator import (
    CCR_LEVELS,
    FAMILIES,
    GROUPS,
    build_instance,
    measure_ccr,
    validate_structure,
)
from .model import Problem

# The ranking this suite is built to probe. Recorded in the manifest so that the
# constraint is visible in the artifact rather than implicit in the cohort.
TARGET_ORDER = ("ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT")

# IPEFT's source placement mode is append-only; the other five are scored in
# insertion mode. Both modes are recorded for every policy so the sensitivity is
# visible rather than assumed.
PLACEMENT = {
    "ECTD": "insertion",
    "AEFT": "insertion",
    "BPPTS": "insertion",
    "HEFT": "insertion",
    "LSTD": "insertion",
    "IPEFT": "append",
}


def geometric_mean(values):
    values = [v for v in values if v > 0]
    if not values:
        return float("nan")
    return math.exp(sum(math.log(v) for v in values) / len(values))


def build_suite(seeds, target=None, ccr_levels=None):
    """Yield every instance for the given seed range, in a fixed order.

    With ``target`` set, keep advancing the seed until that many instances have
    been produced. The order is deterministic either way: seed, then family,
    then group, then CCR level.

    With ``ccr_levels`` set, each (family, group, seed) combination is emitted
    once per level, so the suite becomes a full factorial over family, group,
    seed and communication intensity. That is what makes the CCR axis a
    controlled variable rather than a property that happens to vary.
    """
    levels = tuple(ccr_levels) if ccr_levels else (None,)
    produced = 0
    seed = seeds[0]
    while True:
        for family in FAMILIES:
            for group in GROUPS:
                for level in levels:
                    if target is not None and produced >= target:
                        return
                    yield build_instance(family, group, seed, ccr=level)
                    produced += 1
        seed += 1
        if target is None and seed > seeds[-1]:
            return


def score_instance(instance, policies, placement):
    problem = Problem(
        instance["costs"],
        [(u, v, c) for u, v, c in instance["edges"]],
        name=instance["id"],
    )
    row = {}
    checks = {}
    for name, fn in policies.items():
        insertion = placement[name] == "insertion"
        schedule = fn(problem, insertion=insertion)
        report = validate_schedule(problem, schedule)
        row[name] = schedule.makespan
        checks[name] = report
    return row, checks


def _score_worker(task):
    """Score one instance in a worker process.

    Module level so it is picklable under both fork and spawn. Each worker
    builds its own policy table on first use, which keeps the parent's table out
    of the pickle and avoids copying it per task.
    """
    instance, placement = task
    policies = _score_worker.policies
    if policies is None:
        policies = policy_table()
        _score_worker.policies = policies
    structure = validate_structure(instance)
    if not structure["valid"]:
        return instance, None, None, structure["problems"]
    row, checks = score_instance(instance, policies, placement)
    return instance, row, checks, []


_score_worker.policies = None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build and score the ECTD benchmark suite.")
    parser.add_argument("--out", default="results", help="output directory")
    parser.add_argument("--seeds", type=int, default=12, help="number of seeds per family")
    parser.add_argument("--seed-start", type=int, default=1, help="first seed value")
    parser.add_argument("--instances", type=int, default=None,
                        help="build exactly this many instances, advancing seeds as needed")
    parser.add_argument("--ccr", action="store_true",
                        help="stratify the suite over CCR_LEVELS instead of using "
                             "whatever ratio the generator produces")
    parser.add_argument("--jobs", type=int, default=1,
                        help="worker processes; 0 uses every available CPU")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    policies = policy_table()
    ccr_levels = list(CCR_LEVELS) if args.ccr else None

    started = time.time()
    instances = []
    score_rows = []
    validation = {"structure_failures": [], "feasibility_failures": [], "checked": 0}

    # The suite is generated in a fixed canonical order, and every result carries
    # its position in that order. Workers finish out of order, so results are put
    # back by index before anything is written; a parallel run and a serial run
    # then produce identical artifacts.
    canonical = {}
    for index, inst in enumerate(
            build_suite(seeds, target=args.instances, ccr_levels=ccr_levels)):
        canonical[inst["id"]] = index

    jobs = args.jobs if args.jobs > 0 else (os.cpu_count() or 1)
    tasks = ((inst, PLACEMENT) for inst in
             build_suite(seeds, target=args.instances, ccr_levels=ccr_levels))

    def absorb(result):
        instance, row, checks, problems = result
        if problems:
            validation["structure_failures"].append(
                {"id": instance["id"], "problems": problems})
            return
        for name, report in checks.items():
            validation["checked"] += 1
            if not report["valid"]:
                validation["feasibility_failures"].append(
                    {"id": instance["id"], "policy": name, "errors": report["errors"]})
        instances.append(instance)
        score_rows.append({"id": instance["id"], "family": instance["family"],
                           "group": instance["group"], "seed": instance["seed"],
                           "n": instance["n"], "p": instance["p"],
                           "ccr": instance["ccr"],
                           "ccr_target": instance["ccr_target"],
                           "scores": row})

    if jobs == 1:
        for task in tasks:
            absorb(_score_worker(task))
            if not args.quiet and len(instances) % 40 == 0:
                print("  scored %d instances" % len(instances), file=sys.stderr)
    else:
        # imap_unordered keeps memory flat: results are consumed as workers
        # finish rather than materialising the whole suite up front. Because
        # workers finish out of order, the rows are re-sorted into the suite's
        # canonical order before anything is written, so a parallel run and a
        # serial run produce identical artifacts.
        methods = mp.get_all_start_methods()
        ctx = mp.get_context("fork" if "fork" in methods else "spawn")
        with ctx.Pool(processes=min(jobs, os.cpu_count() or 1)) as pool:
            for result in pool.imap_unordered(_score_worker, tasks, chunksize=1):
                absorb(result)
                if not args.quiet and len(instances) % 40 == 0:
                    print("  scored %d instances" % len(instances), file=sys.stderr)
    elapsed = time.time() - started

    # Put every row back at its canonical index.
    score_rows.sort(key=lambda r: canonical[r["id"]])
    instances.sort(key=lambda inst: canonical[inst["id"]])

    # ---- pooled geometric means, overall and per family ----
    def pooled(rows):
        return {name: geometric_mean([r["scores"][name] for r in rows])
                for name in policies}

    overall = pooled(score_rows)
    by_family = {fam: pooled([r for r in score_rows if r["family"] == fam])
                 for fam in FAMILIES}
    by_group = {grp: pooled([r for r in score_rows if r["group"] == grp])
                for grp in GROUPS}

    def ranked(means):
        return sorted(means, key=lambda k: (means[k], k))

    # Per-CCR-stratum pooled means. This is the axis the suite is stratified on,
    # so it is reported first-class rather than as a post-hoc cut.
    def ccr_key(row):
        target = row["ccr_target"]
        return target if target is not None else "native"

    strata = sorted({ccr_key(r) for r in score_rows}, key=lambda v: (v == "native", v))
    by_ccr = {}
    for level in strata:
        rows = [r for r in score_rows if ccr_key(r) == level]
        by_ccr[str(level)] = {
            "instances": len(rows),
            "means": pooled(rows),
            "rank": ranked(pooled(rows)),
            "median_measured_ccr": sorted(r["ccr"] for r in rows)[len(rows) // 2],
        }

    overall_rank = ranked(overall)
    family_rank = {fam: ranked(m) for fam, m in by_family.items()}
    group_rank = {grp: ranked(m) for grp, m in by_group.items()}

    # ---- pairwise win/tie/loss against the best policy on each instance ----
    # A policy wins an instance only if it is the unique best; it ties only if
    # another policy matches it exactly. Counting a sole best as a tie would
    # report zero wins for every policy, which is what a naive <= test does.
    win_table = {}
    for name in policies:
        wins = ties = losses = 0
        for r in score_rows:
            best = min(r["scores"].values())
            value = r["scores"][name]
            if value > best + 1e-9:
                losses += 1
            elif sum(1 for other in policies
                     if abs(r["scores"][other] - best) <= 1e-9) > 1:
                ties += 1
            else:
                wins += 1
        win_table[name] = {"strict_wins": wins, "tied_best": ties, "losses": losses}

    # ---- adjacent gaps in the target order, and in the observed order ----
    def adjacent_gaps(order, means):
        out = []
        for upper, lower in zip(order, order[1:]):
            a, b = means[upper], means[lower]
            out.append({"upper": upper, "lower": lower,
                        "relative_gap_pct": round((b - a) / a * 100.0, 6)})
        return out

    target_gaps = adjacent_gaps(TARGET_ORDER, overall)
    observed_gaps = adjacent_gaps(overall_rank, overall)

    # ---- how often the target order is reproduced on any single instance ----
    target_reproduced = 0
    for r in score_rows:
        order = sorted(policies, key=lambda k: (r["scores"][k], k))
        if tuple(order) == TARGET_ORDER:
            target_reproduced += 1

    manifest = {
        "suite": "ECTD benchmark, constructed instance suite",
        "package_version": __version__,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provenance": {
            "policies": "standard-library ports of ectdbench/*.py from "
                        "alphanum545/ECTD-Benchmark branch research/ranking-revision-2026-11-23",
            "instances": "newly generated by ectdbench/generator.py; NOT the original "
                         "3,072-instance pool, which is unpublished",
            "selection": "no instance selection, filtering or cohort construction is "
                         "applied. Every generated instance that passes structural "
                         "validation is scored.",
        },
        "target_order": list(TARGET_ORDER),
        "target_order_status": "recorded as the hypothesis under test, not as a result. "
                               "The suite is scored and ranked without reference to it.",
        "placement": PLACEMENT,
        "seeds": seeds,
        "families": list(FAMILIES),
        "groups": list(GROUPS),
        "ccr_levels": list(CCR_LEVELS) if args.ccr else None,
        "ccr_definition": "mean edge communication delay divided by mean execution "
                          "cost, measured per instance and recorded in the "
                          "instance record and in scores.csv",
        "ccr_stratified": bool(args.ccr),
        "instances": len(score_rows),
        "policies": list(policies),
        "runtime_seconds": round(elapsed, 3),
        "jobs": jobs,
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "numpy": "not used (standard library only)"},
    }

    # ---- entry-duplication activation: did the mechanism ever fire? ----
    # ECTD's entry-duplication term only has an effect when the graph has a real
    # single entry. If this is zero the motif was inert and the comparison is
    # not testing what it claims to test.
    duplication_active = 0
    for inst in instances:
        problem = Problem(inst["costs"],
                          [(u, v, c) for u, v, c in inst["edges"]],
                          name=inst["id"])
        if problem.dummy_entry is None:
            duplication_active += 1

    summary = {
        "instances": len(score_rows),
        "pooled_geometric_makespan": {k: round(v, 6) for k, v in overall.items()},
        "observed_rank": overall_rank,
        "target_rank": list(TARGET_ORDER),
        "target_matches_observed": overall_rank == list(TARGET_ORDER),
        "target_order_reproduced_on_instances": target_reproduced,
        "adjacent_gaps_target_order": target_gaps,
        "adjacent_gaps_observed_order": observed_gaps,
        "by_family": {f: {"means": {k: round(v, 6) for k, v in m.items()},
                          "rank": family_rank[f]} for f, m in by_family.items()},
        "by_group": {g: {"means": {k: round(v, 6) for k, v in m.items()},
                         "rank": group_rank[g]} for g, m in by_group.items()},
        "by_ccr": {k: {"instances": v["instances"],
                       "means": {n: round(x, 6) for n, x in v["means"].items()},
                       "rank": v["rank"],
                       "median_measured_ccr": v["median_measured_ccr"]}
                   for k, v in by_ccr.items()},
        "win_tie_loss_vs_best": win_table,
        "single_entry_instances": duplication_active,
        "entry_duplication_eligible": duplication_active == len(score_rows),
    }

    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    with open(os.path.join(args.out, "validation.json"), "w") as fh:
        json.dump(validation, fh, indent=2, sort_keys=True)
    with open(os.path.join(args.out, "instances.jsonl"), "w") as fh:
        for inst in instances:
            fh.write(json.dumps(inst, sort_keys=True) + "\n")
    with open(os.path.join(args.out, "scores.csv"), "w") as fh:
        header = (["id", "family", "group", "seed", "n", "p", "ccr", "ccr_target"]
                  + list(policies))
        fh.write(",".join(header) + "\n")
        for r in score_rows:
            fh.write(",".join(
                [r["id"], r["family"], r["group"], str(r["seed"]), str(r["n"]),
                 str(r["p"]), "%.6f" % r["ccr"],
                 "" if r["ccr_target"] is None else "%g" % r["ccr_target"]]
                + ["%.6f" % r["scores"][name] for name in policies]) + "\n")

    digest = hashlib.sha256(
        json.dumps([r["id"] for r in score_rows], sort_keys=True).encode()
    ).hexdigest()
    manifest["suite_sha256"] = digest
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    if not args.quiet:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
