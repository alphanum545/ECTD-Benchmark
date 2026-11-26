# ECTD benchmark on the real six-family corpus

**Result: ECTD ranks 4 of 6 on pooled geometric-mean makespan.** It is
6.18% behind AEFT, and at-or-best on 349 of 2,094
instances (16.67%). AEFT is at-or-best on
1,028 (49.09%).

This is the first measurement of the six policies on the real workflow corpus
rather than on generated graphs. It does not reproduce the README's headline.

## Provenance

| Field | Value |
|---|---|
| Workflow run | [45780338828](https://github.com/alphanum545/ECTD-Benchmark/actions/runs/45780338828) |
| Branch | `bench/real-corpus-2100` |
| Head commit | `d7bbe9dcfd74ee7879a933ca532724fd6fdabe47` |
| Run date | 2026-11-26 |
| Corpus | `Techietal/Task-Scheduling-Dataset` |
| Corpus files | 2,100 |
| Shards | 20 |
| Instances scored | 2,094 |
| Instances failed | 6 |
| Invalid schedules | 0 (all policies) |

Corpus layout: `<Family>/<N>Nodes/<P>PROCESSORS/<i>_<p>.txt`, format D2
(`n p`, then a 5·p preamble, then the comp matrix, then the comm matrix).

Scoring: the six policies from `ectdbench.POLICIES`, each run on every instance,
makespan pooled as a geometric mean. Every schedule is validated before it is
scored; a policy that produced an invalid schedule would be counted in
`invalid_schedules` rather than silently scored.

## Headline

| Rank | Policy | Pooled geomean makespan | vs best | Strict wins | Shared wins | At-or-best |
|---:|---|---:|---:|---:|---:|---:|
| 1 | AEFT | 1,381.00 | 0.00% | 1,011 | 17 | 1,028 |
| 2 | LSTD | 1,442.07 | +4.42% | 274 | 54 | 328 |
| 3 | HEFT | 1,443.52 | +4.53% | 209 | 53 | 262 |
| 4 | **ECTD** | 1,466.38 | +6.18% | 323 | 26 | 349 |
| 5 | IPEFT | 1,517.24 | +9.87% | 149 | 12 | 161 |
| 6 | BPPTS | 1,590.75 | +15.19% | 45 | 9 | 54 |

`At-or-best` = strict wins + shared wins (instances where the policy tied for
best with at least one other). Because ties are counted once per policy, the
at-or-best column sums to more than 2,094.

## At-or-best

| Policy | At-or-best | Share of scored |
|---|---:|---:|
| AEFT | 1,028 | 49.09% |
| ECTD | 349 | 16.67% |
| LSTD | 328 | 15.66% |
| HEFT | 262 | 12.51% |
| IPEFT | 161 | 7.69% |
| BPPTS | 54 | 2.58% |

## By family

| Family | Instances | Best policy | Best pooled | ECTD pooled | ECTD vs best | ECTD strict wins | ECTD rank (makespan) |
|---|---:|---|---:|---:|---:|---:|---:|
| Montage | 654 | AEFT | 1,520.37 | 1,575.87 | +3.65% | 63 | 2 |
| Genome | 600 | AEFT | 1,300.45 | 1,418.21 | +9.06% | 105 | 4 |
| LIGO | 660 | AEFT | 1,312.56 | 1,410.82 | +7.49% | 100 | 4 |
| FFT | 60 | AEFT | 1,248.18 | 1,280.00 | +2.55% | 25 | 2 |
| GE | 60 | AEFT | 1,645.85 | 1,653.04 | +0.44% | 31 | 2 |
| LA | 60 | AEFT | 1,434.08 | 1,451.96 | +1.25% | 25 | 2 |

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

| p | Instances | Best policy | Best pooled | ECTD pooled | ECTD vs best |
|---:|---:|---|---:|---:|---:|
| 2 | 349 | AEFT | 8,157.79 | 8,701.28 | +6.66% |
| 4 | 349 | AEFT | 3,029.25 | 3,390.31 | +11.92% |
| 8 | 349 | AEFT | 1,266.30 | 1,423.81 | +12.44% |
| 16 | 349 | LSTD | 700.15 | 762.14 | +8.85% |
| 32 | 349 | AEFT | 581.02 | 585.14 | +0.71% |
| 64 | 349 | ECTD | 530.78 | 530.78 | 0.00% |

ECTD is best at p=64.

## What the numbers say

1. **The README's headline does not survive contact with real workflows.** The
   published result is ECTD first at 1223.68 with 395/800 strict wins, measured
   on 800 *generated* graphs. On 2,094 real instances ECTD is 4 of 6
   at 1,466.38, 6.18% behind AEFT.

2. **The gap is concentrated in the large families.** Montage, Genome and LIGO
   are 1,914 of the 2,094 instances. Genome is the worst at 9.06%
   behind its best policy, LIGO at 7.49%. The small families (FFT, GE,
   LA — 180 instances, 8.6% of the corpus) are all
   within 2.55%.

3. **ECTD's advantage needs spare processors, and the real corpus confirms it.**
   It is best at p=64 and trails at every
   smaller processor count. This matches the mechanism: critical-path weighting
   and entry duplication only pay off when there are idle processors to place
   duplicates on.

4. **Shared wins do not isolate the duplication mechanism.** ECTD ties for best
   on 26 instances, but HEFT (53) and LSTD
   (54) tie more often, and HEFT does not duplicate at all. The
   shared-win count is therefore not evidence about duplication either way; it
   is reported for completeness and should not be read as a mechanism claim.

## Data defects found in the corpus

6 of 2,100 files do not parse. All 6 are the same
degenerate entry, `Montage/100Nodes/9_<p>.txt` for every processor count:

- `Montage/100Nodes/4PROCESSORS/9_4.txt` — ValueError: costs must be a nonempty n by p matrix
- `Montage/100Nodes/32PROCESSORS/9_32.txt` — ValueError: costs must be a nonempty n by p matrix
- `Montage/100Nodes/64PROCESSORS/9_64.txt` — ValueError: costs must be a nonempty n by p matrix
- `Montage/100Nodes/16PROCESSORS/9_16.txt` — ValueError: costs must be a nonempty n by p matrix
- `Montage/100Nodes/2PROCESSORS/9_2.txt` — ValueError: costs must be a nonempty n by p matrix
- `Montage/100Nodes/8PROCESSORS/9_8.txt` — ValueError: costs must be a nonempty n by p matrix

The file is 73 bytes with header `0 2` — zero nodes. It is a corpus defect, not
a parser bug: the remaining 2,094 files parse and score cleanly. These six
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
gh workflow run benchmark.yml --ref bench/real-corpus-2100
```

Locally, with the corpus checked out beside this repo:

```
python3 scripts/run_benchmark.py --data-root <corpus> --out shards/
python3 scripts/aggregate_benchmark.py shards/ --out docs/benchmark/
python3 scripts/render_results.py
```

`scripts/render_results.py` regenerates this document from `summary.json`, so
the prose cannot drift from the data.
