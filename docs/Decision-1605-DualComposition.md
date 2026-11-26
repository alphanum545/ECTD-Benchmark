# Decision record: build BOTH 1,605 compositions

**Status:** APPROVED — both variants to be built and compared.
**Date:** 2026-11-25 (rev. 2026-11-26: Variant B redefined, see §4)
**Decided by:** user
**Supersedes:** the single-variant plan in `docs/InstanceExpansionPlan.md` §4.4

> **Rev. 2026-11-26b — measurement reconciliation.** Every quantitative claim in
> this record was re-derived from the committed `docs/measurements/*.json`. The
> rung-9 row, the 81-dead-cell inventory, the 552-instance count, the
> 60-candidate confirmation and the §8 randomization table did not survive.
> Corrected figures and the evidence are in
> [`measurements/VERIFICATION.md`](measurements/VERIFICATION.md). The lattice
> arithmetic (§3 vs §8) is still **open** and blocks the build.

> **Location note.** This record lives in the `ECTD-Benchmark` repo. The data it
> references (`ectd-real/ectd_selected_400.csv`, `scheduling-benchmark/data/`)
> sits in the parent workspace, one level above this repo's root. Paths are
> written workspace-relative.

---

## 1. The decision

We are building **two** 1,605-instance datasets from the same 400-file base set,
differing only in how they treat the 104 "dead" cells where ECTD has never won
in 24 measured candidates:

| | Variant A — FORCE | Variant B — KNOB LADDER |
|---|---|---|
| Dead cells | forced at σ=0.18, waivers where a cell cannot fill | forced by escalating σ and comm_scale |
| Purpose | source fidelity | coverage |
| Built | pending | pending |

Both are built. Neither is discarded. At the end we compare them and keep the
better one. **This document is the record of that commitment** so the decision
survives across sessions and is not silently collapsed into one variant.

---

## 2. Why there is a choice at all

The lattice requires a fixed number of ECTD wins per cell — 6 in Set 1 and 5 in
Set 2 under §3's 1,605 arithmetic (see the OPEN note in §8). Measured ECTD win
rates on real topologies with the value-re-draw method, from
`docs/measurements/cell_rates.json` (24 candidates per cell: 2 sources × 12
seeds, 235 cells, 5,640 candidates):

| Family | p=4 | p=8 | p=16 | p=32 | p=64 |
|---|---:|---:|---:|---:|---:|
| Montage | 9.1% | 4.2% | 7.2% | 8.0% | 11.0% |
| Genome | 1.2% | 10.8% | 19.2% | 43.3% | 52.5% |
| LIGO | 2.7% | 4.5% | 9.1% | 15.2% | 33.7% |
| FFT | 4.2% | 26.7% | 40.0% | 63.3% | 78.3% |
| GE | 30.0% | 62.5% | 62.5% | 70.0% | 71.7% |
| LA | 20.0% | 30.8% | 39.2% | 51.7% | 54.2% |

These are pooled across each family's levels, and the per-cell spread is wide.
§4.0 is the authoritative per-cell view; this table is orientation only.

**Cause:** ECTD's advantage comes from critical-path weighting and entry
duplication. Both need spare processors to pay off. At p=4/p=8 the machine is
nearly serial and AEFT wins consistently. This is a property of the algorithm,
not a defect in the data.

**Dead cell inventory:** 104 of 235 measured cells (44%), holding 708 of 1,605
instances. Genome 900's 5 cells are unmeasured (§8) and are excluded.

| Family | Cells | Measured | Dead | Viable | Instances | In dead cells |
|---|---:|---:|---:|---:|---:|---:|
| Montage | 55 | 55 | 31 | 24 | 385 | 217 |
| Genome | 55 | 50 | 22 | 28 | 385 | 154 |
| LIGO | 55 | 55 | 31 | 24 | 385 | 217 |
| FFT | 25 | 25 | 10 | 15 | 150 | 60 |
| GE | 25 | 25 | 3 | 22 | 150 | 18 |
| LA | 25 | 25 | 7 | 18 | 150 | 42 |
| **Total** | **240** | **235** | **104** | **131** | **1,605** | **708** |

If Genome 900's 5 unmeasured cells also come up dead, that becomes 109 dead
cells and 743 instances.

---

## 3. Variant A — FORCE

**Lattice:** unchanged from the approved 1,605 plan.

```
Set 1 (D1): 3 families × 11 tasks × 5 p × 7 = 1155   (385/family)
Set 2 (D2): 3 families ×  5 tasks × 5 p × 6 =  450   (150/family)
TOTAL: 1605        cells: 240 (165 + 75)
```

| Family | Format | Tasks | p | Workflows/cell | Cells | Instances |
|---|---|---:|---:|---:|---:|---:|
| Montage | D1 | 11 | 5 | 7 | 55 | 385 |
| Genome | D1 | 11 | 5 | 7 | 55 | 385 |
| LIGO | D1 | 11 | 5 | 7 | 55 | 385 |
| FFT | D2 | 5 | 5 | 6 | 25 | 150 |
| GE | D2 | 5 | 5 | 6 | 25 | 150 |
| LA | D2 | 5 | 5 | 6 | 25 | 150 |

**Properties:** family equality holds · full 5-value p grid in both sets ·
all 240 cells present · target ratio 1,404W / 201A = 6.985:1

> **The 7:1 target is global, not per-cell.** 1,404W/201A is 1,605 split 7:1 and
> rounded. No uniform per-cell quota produces it: 7:1 over 7 instances per cell
> needs 6.125 winners, and over 6 instances needs 5.25. The per-cell quotas in
> §3 (6W+1A / 5W+1A) give 1,365W/240A = 5.69:1. The §8 quotas (7W+1A / 6W+1A)
> give 1,605W/240A = 6.69:1. See the OPEN note in §8.

**Build rule:** every cell must yield its full quota. Dead cells get a hard draw
cap; if a cell cannot fill, it is recorded as a **waiver** in the manifest rather
than silently backfilled.

**Expected cost:** viable cells ≈ 4,059 candidates. Dead cells add 11k–57k
depending on the true rate (5% → 0.3 min; 1% → 1.3 min on 8 workers). Total
runtime is minutes, not hours.

**Known risk — and it is large.** At σ=0.18 the measurement finds only 6 of the
104 dead cells live (24 candidates each). A's realised fill count depends on the
draw cap, but the measured expectation is 6 cells — 4 Set 1 cells × 7 plus 2
Set 2 cells × 6 = 40 instances — leaving **668 waived** and **937 of 1,605
delivered**. The global ratio must be recomputed on what is actually built and
the label corrected; it must not be asserted as 7:1 when it isn't.

---

## 4. Variant B — DROP

**Revision 2026-11-26.** Variant B was originally "drop the dead cells and use only
the processor values that survive." A full per-cell measurement (235 cells, 5,640
candidates) plus a knob sweep changed that. The measurement is in §4.0 and the
revised definition is in §4.2. The original reading is kept in §4.1 as superseded
history, because the reasoning still matters for anyone re-deriving this.

### 4.0 What the full measurement found

Win rate per (family, level, p), 2 sources × 12 seeds per cell:

| Set | p=4 | p=8 | p=16 | p=32 | p=64 |
|---|---:|---:|---:|---:|---:|
| Set 1 — live cells | 7/32 | 6/32 | 13/32 | 21/32 | **29/32** |
| Set 1 — pooled rate | 4.4% | 6.4% | 11.6% | 21.5% | 31.8% |
| Set 2 — live cells | 6/15 | 9/15 | 12/15 | 14/15 | **14/15** |
| Set 2 — pooled rate | 18.1% | 40.0% | 47.2% | 61.7% | 68.1% |

Viability is **level-dependent, not family-dependent**: Genome p=8 reads 83% at
level 50 but 0% at level 200. Any earlier family-level map is too coarse and must
not be used.

Dead cells at the high-p end — the only regime that matters for a reduced grid:

- **p=32:** Montage 400/600/700/900/1000 · LIGO 500/600/700/800/900/1000 · FFT 1152
- **p=64:** Montage 600/900/1000 · LA 11

**No processor value is live in every cell of either set.** p=64 is closest
(3 dead cells in Set 1, 1 in Set 2), but it is not universal. So "drop to a common
p" cannot reach 5 values, and reaches only 2 in Set 1 and 3 in Set 2.

### 4.1 Superseded: drop to common p (originally Variant B)

Recorded for completeness. Not the approved definition.

- **B1, drop per family:** Montage keeps 5 p, Genome keeps 2. 99 + 60 cells,
  1,053 instances, but per-family counts become 385 / 154 / 154 — **breaks family
  equality**, the invariant the lattice exists to enforce. Rejected.
- **B2, drop to common p per set:** Set 1 → p={32,64}, 66 cells; Set 2 →
  p={16,32,64}, 45 cells; 111 cells total. At r1=12, r2=18 → 1,602 instances.
  Family equality holds, 7:1 honest everywhere, but Set 1 loses p=4/8/16 and Set 2
  loses p=4/8. The low-parallelism regime disappears from the dataset entirely.

B2 was the approved reading until the knob sweep in §4.0 showed the dead cells can
be filled instead of dropped.

### 4.2 Approved: keep all 5 p, force dead cells with a knob ladder

Value changes flip dead cells. Two knobs were swept on the hardest cells —
**σ** (spread of the value re-draw) and **comm_scale** (communication-cost
multiplier). Baseline is σ=0.18, ×1.

| Cell | Base | σ0.35 ×4 | σ0.6 ×4 | σ1.0 ×4 | σ0.6 ×8 |
|---|---:|---:|---:|---:|---:|
| Montage 900 @p64 | 10% | 40% | 60% | 20% | 40% |
| Montage 1000 @p64 | 10% | 10% | 40% | 40% | 30% |
| LIGO 900 @p32 | 0% | 10% | 20% | 10% | **100%** |
| LIGO 1000 @p32 | 0% | 60% | 80% | 50% | 80% |
| FFT 1152 @p32 | 0% | 50% | 90% | 100% | 80% |

The "Base" column is the sweep's own 10-candidate baseline, not the 24-candidate
`cell_rates.json` figure: Montage 900@p64 and 1000@p64 read 10% here (1 win in
10) but 0/24 in `cell_rates.json`. Both are consistent with a true rate near
zero; 10 draws cannot distinguish them.

Every dead cell becomes live. **Mechanism:** raising communication cost relative
to computation rewards ECTD's critical-path weighting. ECTD's advantage is
modelling when communication dominates, so amplifying comm cost puts the instance
into the regime where the algorithm's premise holds. This is a deliberate,
recorded manipulation, not a neutral re-draw.

**Approved ladder** — tried in order per cell until the quota fills. **Eight
rungs, not four.** Measurement on all 104 dead cells showed the original 4-rung
ladder left 27 cells unfilled; four further rungs were needed and filled 24 of
them.

| Rung | σ | comm_scale | Cells filled here |
|---:|---:|---:|---:|
| 1 | 0.18 | ×1 | 6 |
| 2 | 0.35 | ×4 | 47 |
| 3 | 0.6 | ×4 | 9 |
| 4 | 0.6 | ×8 | 15 |
| 5 | 0.6 | ×16 | 15 |
| 6 | 1.0 | ×8 | 0 |
| 7 | 1.0 | ×16 | 1 |
| 8 | 1.0 | ×32 | 8 |

**101 of 104 dead cells fill.** Three resist every rung tested:

| Cell | Baseline wins | Ladder result |
|---|---:|---|
| Genome 1000 @p4 | 0/24 | never filled (`wins=0, cand=0`) |
| LIGO 1000 @p4 | 0/24 | never filled (`wins=0, cand=0`) |
| LIGO 900 @p4 | 0/24 | never filled (`wins=0, cand=0`) |

All three are the largest level of their family at the smallest machine. That is
the same regime §2 identifies as the cause of the dead cells: at p=4 with n≥900
there are no spare processors for critical-path weighting to exploit. It is a
boundary of the method, not a search failure, and it should be reported as one.

Distribution: only **6 of 104** dead cells fill at baseline. 95 need escalation,
and 24 need ×16 or beyond. Those 24 are the instances that are no longer in their
source communication regime.

**Cap 20 candidates per rung, then escalate.** Tested on the hardest cell: a
40-candidate cap took 247 candidates and 14.0 s; a 20-candidate cap took 131
candidates and 7.5 s and still filled. Grinding a low rung that produces nothing
wastes half the budget.

**Lattice:** unchanged from Variant A — 240 cells, 1,605 instances, 5 p values in
both sets, family equality holds.

**Mandatory recording:** the rung used must be written per instance in the
manifest. Any result drawn from a ×4 or higher cell must be reported separately
from a ×1 cell, because the instance is no longer in the same communication
regime as its source.

### 4.3 What now separates A from B

Both variants now keep all 5 p values and all 240 cells. They differ only in how
hard they push:

| | A — FORCE | B — KNOB LADDER |
|---|---|---|
| Cells | 240 | 240 |
| p per set | 5 / 5 | 5 / 5 |
| Dead cells | forced, may waive | forced via ladder |
| Cells filled | 6 of 104 | 101 of 104 |
| Instances delivered | 937 of 1,605 | 1,584 of 1,605 |
| Value re-draw | σ=0.18 only | escalates to σ=1.0 / ×32 |
| Fidelity to source | high | degrades in 24 cells |
| 7:1 | target, may waive | target, may waive in 3 cells |

A stays faithful to the source cost distribution and accepts waivers where a cell
cannot fill. B pushes most cells over the line by moving the instance into a
communication-heavy regime, and waives the three that resist every rung.

**Neither variant is a guaranteed fill.** B delivers 1,584 of 1,605 instances, 21
short, and needs the same waiver mechanism as A — for 3 cells instead of 98.
**A is the high-fidelity variant; B is the high-coverage variant.** The
comparison in §6 decides which is preferable.

---

## 5. Side-by-side

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| Target instances | 1,605 | 1,605 |
| Delivered instances | 937 | 1,584 |
| Cells | 240 | 240 |
| Family equality | holds | holds |
| p per set (S1 / S2) | 5 / 5 | 5 / 5 |
| Dead cells | 104 forced | 104 forced |
| Cells filled | 6 of 104 | 101 of 104 |
| Value re-draw | σ=0.18 only | escalates to σ=1.0 / ×32 |
| 7:1 true in every cell | target, may waive | target, may waive in 3 cells |
| Low-p regime present | yes | yes |
| Fidelity to source costs | high | degrades in 24 cells |
| Main risk | 668 waived instances | 24 cells outside source regime |

---

## 6. What "better result" will be judged on

To be decided when both exist, but the comparison should at minimum report:

1. **Ratio integrity** — actual winners:added vs the 7:1 target, per set and per family.
2. **Waiver count** — how many cells in Variant A failed to fill their quota.
3. **Knob usage** — how many instances in Variant B needed σ>0.18 or ×>1, and which cells.
4. **Per-cell win-rate spread** — variance of realised win rate across cells.
5. **Coverage** — which (family, task, p) combinations each variant can speak to.
6. **Downstream stability** — whether the ECTD-vs-baseline ranking holds in both.
7. **Fidelity** — how far Variant B's escalated cells drift from their source cost
   distribution, reported separately from the ×1 cells.

Both variants now target the same cells, so the lattice is not a differentiator.
The real trade is **coverage (B) versus source fidelity (A)**, and it is much
larger than §4.3 first suggested: A waives 668 instances, B waives 21.

---

## 8. Build method — the part a fresh session needs

**The method is resampling in a loop. Nothing more.** "Deterministic" means only
that the seed is fixed, so the same seed produces the same file every run.

```python
comp[r][c] = source_comp[r][c % p_src] * lognormal(0, sigma)
comm[u][v] = source_comm[u][v] * scale        # -1 stays -1, always
```

Then score the six policies, keep the draw if it advances the cell's quota, repeat.

### Per-cell loop

```
for rung in LADDER:                      # 8 rungs, see §4.2
    for candidate in range(20):          # cap 20 per rung
        resample comp and comm from source
        score all 6 policies
        if ECTD wins and winners < quota_w:  keep
        if ECTD loses and added < 1:        keep
    if quota met: stop, record rung
```

> **OPEN — lattice arithmetic, resolve before building.** §3 gives
> 165×7 + 75×6 = 1,605, i.e. **6W+1A** (Set 1) and **5W+1A** (Set 2). The loop
> above was previously written as 7W+1A and 6W+1A, which is 165×8 + 75×7 =
> **1,845**. The two cannot both be right. The 1,404W/201A target in §3 is 1,605
> split 7:1 and rounded, and no uniform per-cell quota can produce it. Pick one
> before the builder is written.

Set 1 cells need **6 winners + 1 added** (7 instances). Set 2 cells need
**5 winners + 1 added** (6 instances). *These are the §3 quotas; if the §8 quota
is adopted instead, every total in this document scales to 1,845.*

### Measured cost

| Scale | Time |
|---|---|
| One candidate (one resample + 6 policies) | 19 ms (n=200) · 145 ms (n=997) · 516 ms (n=2079) |
| One cell (35 candidates, Montage 200@p32) | 0.7 s |
| Whole build (240 cells) | ~3 min single-core, ~30 s on 8 workers |

**"Workers" means Python processes, not LLM subagents.** `multiprocessing.Pool`
with 8 processes, each filling a different cell. No prompts, no credits, no
reasoning — the same code the main process runs.

Subagents were evaluated and rejected: 1,920 LLM calls at ~15 s each is ~8 hours,
non-deterministic, for work a CPU does in 3 minutes.

### Why not full randomization

Randomizing every comp and comm value independently was tested and **fails**.
Neither column is in a committed artifact: the "full random" figures come from
the original probe, and the "source resample" column did not match
`cell_rates.json`. Restated here from that file:

| Cell | Source resample (`cell_rates.json`) | Full random (uncommitted) |
|---|---:|---:|
| LIGO 800 @p64 | 29% (7/24) | **0%** |
| Genome 500 @p32 | 67% (16/24) | 13% |
| FFT 224 @p64 | 75% (18/24) | 53% |
| dead cells @p4 | 0% | 0% |

The direction is consistent — full randomization collapses the high-p cells —
but the "full random" column should be regenerated and committed before it is
cited. Random values erase *which* edges are expensive, and that pattern is
exactly what ECTD's critical-path weighting exploits. The escalating ladder
preserves it and fills 5/5 test cells at drift 0.65–0.68; free search filled 3/5
at drift 1.74–1.79.

> **Caveat on the 5/5.** `search_compare.json` records the ladder arm as filling
> all five test cells, but `ladder_probe2.json` records three of those five
> (Genome 1000@p4, LIGO 1000@p4, LIGO 900@p4) as never filling. The two
> artifacts contradict each other on the same cells. Until that is resolved, the
> ladder's fill advantage over free search should be quoted as "at least 2/5,
> possibly 5/5" — the drift comparison is unaffected.

### Structure preservation — verified

The `-1` pattern is never touched. Round-trip verified byte-identical:

| File | `-1` entries | Round-trip |
|---|---:|---|
| LIGO 1000 @p4 | 998,758 | identical |
| Genome 500 @p32 | 246,418 | identical |

End-to-end test: filled a cell (7W+1A in 28 candidates), wrote D3, re-parsed —
comp matrix identical, comm matrix identical, `-1` count identical.

### Genome 900 is synthesised

Genome has 10 real levels; Montage and LIGO have 11. To make Set 1 uniform at 11,
Genome's 900 is built with `_genome` from `ectd_real/gen_new.py`: n=901, 2,729
edges, CCR 0.51, validates and scores. **It is the only level with no real source
file behind it.** Its 5 cells were never measured and must be probed at build time.

---

## 9. Build order

1. Build **A (1,605, σ=0.18 only)** first — it establishes the pipeline and
   produces the waiver list, which is exactly the set of cells B must escalate.
2. Build **B (1,605, knob ladder)** second, reusing the same builder with the
   ladder enabled and the rung recorded per instance.
3. Compare per §6.
4. Record the outcome in this file under a new "Outcome" section.

Both outputs must be kept side by side and clearly labelled. Do not overwrite one
with the other.

---

## 10. Provenance

- Base set: `ectd-real/ectd_selected_400.csv` (400 rows, 349 winners / 51 added)
- Win rates: measured 2026-11-25/26 on real topologies with value re-draw, σ=0.18,
  2 sources × 12 seeds per cell, 235 cells, 5,640 candidates
  (`scripts/measure_cell_rates.py` → `docs/measurements/cell_rates.json`)
- Knob sweep: 2026-11-26 on the 6 hardest dead cells, σ ∈ {0.18, 0.35, 0.6, 1.0}
  × comm_scale ∈ {1, 2, 4, 8}
- Ladder probe: `scripts/probe_ladder.py` (104 cells, 4 rungs) →
  `docs/measurements/ladder_probe.json`; `scripts/probe_ladder2.py` (27 stubborn
  cells, 4 more rungs) → `docs/measurements/ladder_probe2.json`
- Ladder vs free search: `scripts/compare_search.py` →
  `docs/measurements/search_compare.json`
- Reconciliation: `docs/measurements/VERIFICATION.md` (2026-11-26) — every figure
  above re-derived from the committed JSON
- Lattice arithmetic: `N = 165·r1 + 75·r2` (Set 1 / Set 2), derived from
  3 families × tasks × 5 p × r
- Dead-cell definition: 0 ECTD wins in 24 measured candidates (95% upper bound
  ≈ 12% at 24 draws)
- Related: `docs/InstanceExpansionPlan.md`, `ectd_real/make_instances.py`,
  `ectd_real/gen_new.py`, `scripts/measure_cell_rates.py`,
  `scripts/probe_ladder.py`, `scripts/probe_ladder2.py`, `scripts/compare_search.py`
