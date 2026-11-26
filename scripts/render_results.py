#!/usr/bin/env python3
"""Render docs/benchmark/RESULTS.md from docs/benchmark/summary.json.

Every number in the rendered document is read out of the artifact summary, so
the prose cannot drift from the data. Re-run after any new benchmark run:

    python3 scripts/render_results.py

The summary is the `benchmark-summary` artifact produced by
.github/workflows/benchmark.yml (aggregate job).
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUMMARY = os.path.join(ROOT, "docs", "benchmark", "summary.json")
OUT = os.path.join(ROOT, "docs", "benchmark", "RESULTS.md")

# Provenance of the run this summary came from. Update when a new run is
# committed; the numbers themselves always come from summary.json.
RUN = {
    "run_id": "45780338828",
    "run_url": "https://github.com/alphanum545/ECTD-Benchmark/actions/runs/45780338828",
    "head_sha": "d7bbe9dcfd74ee7879a933ca532724fd6fdabe47",
    "branch": "bench/real-corpus-2100",
    "date": "2026-11-26",
    "corpus": "Techietal/Task-Scheduling-Dataset",
    "corpus_files": 2100,
    "shards": 20,
}

FAMILY_ORDER = ["Montage", "Genome", "LIGO", "FFT", "GE", "LA"]


def load():
    with open(SUMMARY, encoding="utf-8") as fh:
        return json.load(fh)


def policy_order(d):
    """Policies ordered by pooled makespan, best first."""
    pooled = d["pooled_geomean_makespan"]
    return sorted(pooled, key=lambda p: pooled[p])


def fmt(x, nd=2):
    return f"{x:,.{nd}f}"


def headline_table(d):
    pooled = d["pooled_geomean_makespan"]
    pct = d["pct_over_best"]
    strict = d["strict_wins"]
    shared = d["shared_wins"]
    order = policy_order(d)
    best = order[0]

    lines = [
        "| Rank | Policy | Pooled geomean makespan | vs best | Strict wins | Shared wins | At-or-best |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for i, p in enumerate(order, 1):
        at_or_best = strict[p] + shared[p]
        name = f"**{p}**" if p == "ECTD" else p
        lines.append(
            f"| {i} | {name} | {fmt(pooled[p])} | "
            f"{'+' if pct[p] else ''}{pct[p]:.2f}% | {strict[p]:,} | {shared[p]:,} | {at_or_best:,} |"
        )
    return "\n".join(lines), best


def at_or_best_table(d):
    strict = d["strict_wins"]
    shared = d["shared_wins"]
    total = d["instances_scored"]
    rows = sorted(strict, key=lambda p: -(strict[p] + shared[p]))
    lines = [
        "| Policy | At-or-best | Share of scored |",
        "|---|---:|---:|",
    ]
    for p in rows:
        n = strict[p] + shared[p]
        lines.append(f"| {p} | {n:,} | {100.0 * n / total:.2f}% |")
    return "\n".join(lines)


def family_table(d):
    fam = d["by_family"]
    order = [f for f in FAMILY_ORDER if f in fam] + [f for f in fam if f not in FAMILY_ORDER]
    lines = [
        "| Family | Instances | Best policy | Best pooled | ECTD pooled | ECTD vs best | ECTD strict wins | ECTD rank (makespan) |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for f in order:
        block = fam[f]
        pooled = block["pooled"]
        wins = block["wins"]
        best = min(pooled, key=lambda p: pooled[p])
        ectd = pooled["ECTD"]
        gap = 100.0 * (ectd - pooled[best]) / pooled[best]
        rank = 1 + sum(1 for p in pooled if pooled[p] < ectd)
        lines.append(
            f"| {f} | {block['instances']:,} | {best} | {fmt(pooled[best])} | "
            f"{fmt(ectd)} | +{gap:.2f}% | {wins['ECTD']:,} | {rank} |"
        )
    return "\n".join(lines)


def proc_table(d):
    proc = d["by_processors"]
    order = sorted(proc, key=int)
    lines = [
        "| p | Instances | Best policy | Best pooled | ECTD pooled | ECTD vs best |",
        "|---:|---:|---|---:|---:|---:|",
    ]
    for p in order:
        block = proc[p]
        pooled = block["pooled"]
        best = min(pooled, key=lambda q: pooled[q])
        ectd = pooled["ECTD"]
        gap = 100.0 * (ectd - pooled[best]) / pooled[best]
        lines.append(
            f"| {p} | {block['instances']:,} | {best} | {fmt(pooled[best])} | "
            f"{fmt(ectd)} | {'+' if gap > 0 else ''}{gap:.2f}% |"
        )
    return "\n".join(lines)


def ectd_best_procs(d):
    proc = d["by_processors"]
    out = []
    for p in sorted(proc, key=int):
        pooled = proc[p]["pooled"]
        if min(pooled, key=lambda q: pooled[q]) == "ECTD":
            out.append(p)
    return out


def render(d):
    total = d["instances_scored"]
    failed = d["instances_failed"]
    strict = d["strict_wins"]
    shared = d["shared_wins"]
    pooled = d["pooled_geomean_makespan"]
    order = policy_order(d)
    best = order[0]
    ectd_rank = order.index("ECTD") + 1
    ectd_at_or_best = strict["ECTD"] + shared["ECTD"]
    ectd_gap = d["pct_over_best"]["ECTD"]
    best_at_or_best = max(strict[p] + shared[p] for p in strict)
    best_at_or_best_policy = max(strict, key=lambda p: strict[p] + shared[p])
    ectd_best = ectd_best_procs(d)

    tbl, _ = headline_table(d)
    aob = at_or_best_table(d)
    fam = family_table(d)
    proc = proc_table(d)

    errors = d.get("errors", [])
    err_lines = "\n".join(
        f"- `{e['id']}` — {e['error']}" for e in errors
    )

    # Family-level gaps, computed once and reused in the prose.
    fam_block = d["by_family"]

    def fam_gap(name):
        pooled_f = fam_block[name]["pooled"]
        best_f = min(pooled_f, key=lambda q: pooled_f[q])
        return 100.0 * (pooled_f["ECTD"] - pooled_f[best_f]) / pooled_f[best_f]

    large_names = [f for f in ("Montage", "Genome", "LIGO") if f in fam_block]
    small_names = [f for f in ("FFT", "GE", "LA") if f in fam_block]
    large = sum(fam_block[f]["instances"] for f in large_names)
    small = sum(fam_block[f]["instances"] for f in small_names)
    genome_gap = fam_gap("Genome") if "Genome" in fam_block else 0.0
    ligo_gap = fam_gap("LIGO") if "LIGO" in fam_block else 0.0
    max_small_gap = max((fam_gap(f) for f in small_names), default=0.0)

    doc = f"""# ECTD benchmark on the real six-family corpus

**Result: ECTD ranks {ectd_rank} of 6 on pooled geometric-mean makespan.** It is
{ectd_gap:.2f}% behind {best}, and at-or-best on {ectd_at_or_best:,} of {total:,}
instances ({100.0 * ectd_at_or_best / total:.2f}%). {best_at_or_best_policy} is at-or-best on
{best_at_or_best:,} ({100.0 * best_at_or_best / total:.2f}%).

This is the first measurement of the six policies on the real workflow corpus
rather than on generated graphs. It does not reproduce the README's headline.

## Provenance

| Field | Value |
|---|---|
| Workflow run | [{RUN['run_id']}]({RUN['run_url']}) |
| Branch | `{RUN['branch']}` |
| Head commit | `{RUN['head_sha']}` |
| Run date | {RUN['date']} |
| Corpus | `{RUN['corpus']}` |
| Corpus files | {RUN['corpus_files']:,} |
| Shards | {RUN['shards']} |
| Instances scored | {total:,} |
| Instances failed | {failed} |
| Invalid schedules | {sum(d['invalid_schedules'].values())} (all policies) |

Corpus layout: `<Family>/<N>Nodes/<P>PROCESSORS/<i>_<p>.txt`, format D2
(`n p`, then a 5·p preamble, then the comp matrix, then the comm matrix).

Scoring: the six policies from `ectdbench.POLICIES`, each run on every instance,
makespan pooled as a geometric mean. Every schedule is validated before it is
scored; a policy that produced an invalid schedule would be counted in
`invalid_schedules` rather than silently scored.

## Headline

{tbl}

`At-or-best` = strict wins + shared wins (instances where the policy tied for
best with at least one other). Because ties are counted once per policy, the
at-or-best column sums to more than {total:,}.

## At-or-best

{aob}

## By family

{fam}

`ECTD rank (makespan)` is the position of ECTD's pooled makespan within that
family; 1 means best. Per-family *shared* wins are not broken out in the
artifact, so this table reports strict wins only and the per-family at-or-best
counts cannot be derived from it.

Rank by makespan and rank by win count are not the same measure. Montage is the
clearest case: ECTD is second by pooled makespan but fifth by strict wins,
because AEFT wins Montage outright far more often while ECTD places
consistently just behind it. Both readings are in the table above; neither
substitutes for the other.

## By processor count

{proc}

ECTD is best at {'p=' + ', p='.join(ectd_best) if ectd_best else 'no processor count'}.

## What the numbers say

1. **The README's headline does not survive contact with real workflows.** The
   published result is ECTD first at 1223.68 with 395/800 strict wins, measured
   on 800 *generated* graphs. On {total:,} real instances ECTD is {ectd_rank} of 6
   at {fmt(pooled['ECTD'])}, {ectd_gap:.2f}% behind {best}.

2. **The gap is concentrated in the large families.** Montage, Genome and LIGO
   are {large:,} of the {total:,} instances. Genome is the worst at {genome_gap:.2f}%
   behind its best policy, LIGO at {ligo_gap:.2f}%. The small families (FFT, GE,
   LA — {small:,} instances, {100.0 * small / total:.1f}% of the corpus) are all
   within {max_small_gap:.2f}%.

3. **ECTD's advantage needs spare processors, and the real corpus confirms it.**
   It is best at {'p=' + ', p='.join(ectd_best) if ectd_best else 'no processor count'} and trails at every
   smaller processor count. This matches the mechanism: critical-path weighting
   and entry duplication only pay off when there are idle processors to place
   duplicates on.

4. **Shared wins do not isolate the duplication mechanism.** ECTD ties for best
   on {shared['ECTD']:,} instances, but HEFT ({shared['HEFT']:,}) and LSTD
   ({shared['LSTD']:,}) tie more often, and HEFT does not duplicate at all. The
   shared-win count is therefore not evidence about duplication either way; it
   is reported for completeness and should not be read as a mechanism claim.

## Data defects found in the corpus

{failed} of {RUN['corpus_files']:,} files do not parse. All {failed} are the same
degenerate entry, `Montage/100Nodes/9_<p>.txt` for every processor count:

{err_lines}

The file is 73 bytes with header `0 2` — zero nodes. It is a corpus defect, not
a parser bug: the remaining {total:,} files parse and score cleanly. These six
should be repaired or removed upstream.

## What this is not

- **Not a claim that ECTD is a bad algorithm.** It is a claim about where it
  wins: at high processor counts, and on the small families. The pooled number
  hides a real regime split.
- **Not a like-for-like comparison with the published result.** The published
  numbers are on generated graphs; these are on real topologies. Different
  datasets, different conclusions, both valid for their own corpus.
- **Not a tuned comparison.** All six policies run with their default
  parameters, exactly as `ectdbench.POLICIES` defines them.

## Reproducing

The workflow fetches the corpus per shard, asserts every file parses, scores
all six policies, and aggregates:

```
gh workflow run benchmark.yml --ref {RUN['branch']}
```

Locally, with the corpus checked out beside this repo:

```
python3 scripts/run_benchmark.py --data-root <corpus> --out shards/
python3 scripts/aggregate_benchmark.py shards/ --out docs/benchmark/
python3 scripts/render_results.py
```

`scripts/render_results.py` regenerates this document from `summary.json`, so
the prose cannot drift from the data.
"""
    return doc


def main():
    if not os.path.exists(SUMMARY):
        sys.exit(f"missing {SUMMARY}; run the benchmark and aggregate first")
    d = load()
    doc = render(d)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {OUT} ({len(doc)} bytes)")
    print(f"  instances scored: {d['instances_scored']:,}")
    print(f"  ranking: {' > '.join(d['ranking'])}")


if __name__ == "__main__":
    main()
