# Decision record: build BOTH 1,605 compositions

**Status:** APPROVED — both variants to be built and compared.
**Date:** 2026-11-25 (rev. 2026-11-26: Variant B redefined, see §4)
**Decided by:** user
**Supersedes:** the single-variant plan in `docs/InstanceExpansionPlan.md` §4.4

> **Location note.** This record lives in the `ECTD-Benchmark` repo. The data it
> references (`ectd-real/ectd_selected_400.csv`, `scheduling-benchmark/data/`)
> sits in the parent workspace, one level above this repo's root. Paths are
> written workspace-relative.

---

## 1. The decision

We are building **two** 1,605-instance datasets from the same 400-file base set,
differing only in how they treat the 81 "dead" cells where ECTD has never won:

| | Variant A — FORCE | Variant B — DROP |
|---|---|---|
| Dead cells | forced with heavy candidate draw | excluded from the lattice |
| Purpose | maximum coverage, full 5×p grid | maximum honesty, 7:1 true in every cell |
| Built | pending | pending |

Both are built. Neither is discarded. At the end we compare them and keep the
better one. **This document is the record of that commitment** so the decision
survives across sessions and is not silently collapsed into one variant.

---

## 2. Why there is a choice at all

The lattice requires **7 ECTD wins per cell** (Set 1) and **6** (Set 2). Measured
ECTD win rates on real topologies with the value-re-draw method:

| Family | p=4 | p=8 | p=16 | p=32 | p=64 |
|---|---:|---:|---:|---:|---:|
| Montage | 25.0% | 20.0% | 6.7% | 10.0% | 6.7% |
| Genome | **0.0%** | **0.0%** | **0.0%** | 46.7% | 56.7% |
| LIGO | **0.0%** | **0.0%** | **0.0%** | 10.0% | 16.7% |
| FFT | **0.0%** | 3.3% | 50.0% | 50.0% | 73.3% |
| GE | 20.0% | 73.3% | 93.3% | 90.0% | 73.3% |
| LA | **0.0%** | 83.3% | 73.3% | 66.7% | 63.3% |

Confirmed at 60 candidates per cell: Genome p=4/p=8 and LIGO p=4/p=8 produced
**0 wins in 60**. Mean advantage −13% to −18%.

"0 in 60" means the true rate is under ~5% (rule of three), not literally zero.
So forcing is expensive and uncertain, not impossible.

**Cause:** ECTD's advantage comes from critical-path weighting and entry
duplication. Both need spare processors to pay off. At p=4/p=8 the machine is
nearly serial and AEFT wins consistently. This is a property of the algorithm,
not a defect in the data.

**Dead cell inventory:** 81 of 240 cells (34%), holding 552 of 1,605 instances.

| Family | Cells | Viable | Dead | Instances | In dead cells |
|---|---:|---:|---:|---:|---:|
| Montage | 55 | 55 | 0 | 385 | 0 |
| Genome | 55 | 22 | 33 | 385 | 231 |
| LIGO | 55 | 22 | 33 | 385 | 231 |
| FFT | 25 | 15 | 10 | 150 | 60 |
| GE | 25 | 25 | 0 | 150 | 0 |
| LA | 25 | 20 | 5 | 150 | 30 |
| **Total** | **240** | **159** | **81** | **1,605** | **552** |

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

**Build rule:** every cell must yield its full quota. Dead cells get a hard draw
cap; if a cell cannot fill, it is recorded as a **waiver** in the manifest rather
than silently backfilled.

**Expected cost:** viable cells ≈ 4,059 candidates. Dead cells add 11k–57k
depending on the true rate (5% → 0.3 min; 1% → 1.3 min on 8 workers). Total
runtime is minutes, not hours.

**Known risk:** some dead cells may still come up short. 552 instances carry a
bias we cannot verify per-cell. If a cell fails, the global 7:1 must be
recomputed and the label corrected — it must not be asserted as 7:1 when it isn't.

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

Every dead cell becomes live. **Mechanism:** raising communication cost relative
to computation rewards ECTD's critical-path weighting. ECTD's advantage is
modelling when communication dominates, so amplifying comm cost puts the instance
into the regime where the algorithm's premise holds. This is a deliberate,
recorded manipulation, not a neutral re-draw.

**Approved ladder** — tried in order per cell until the quota fills:

| Step | σ | comm_scale | Status |
|---:|---:|---:|---|
| 1 | 0.18 | ×1 | baseline, unchanged |
| 2 | 0.35 | ×4 | mild |
| 3 | 0.6 | ×4 | moderate |
| 4 | 0.6 | ×8 | strong |

Most cells fill at step 1. Only the ~5 hard cells need steps 2–4.

**Lattice:** unchanged from Variant A — 240 cells, 1,605 instances, 5 p values in
both sets, family equality holds.

**Mandatory recording:** the knob step used must be written per instance in the
manifest. Any result drawn from a ×4 or ×8 cell must be reported separately from a
×1 cell, because the instance is no longer in the same communication regime as its
source.

### 4.3 What now separates A from B

Both variants now keep all 5 p values and all 240 cells. They differ only in how
hard they push:

| | A — FORCE | B — KNOB LADDER |
|---|---|---|
| Cells | 240 | 240 |
| p per set | 5 / 5 | 5 / 5 |
| Dead cells | forced, may waive | forced via ladder |
| Value re-draw | σ=0.18 only | escalates to σ=0.6 / ×8 |
| Fidelity to source | high | degrades in ~5 cells |
| 7:1 | target, may waive | target, should hold |

A stays faithful to the source cost distribution and accepts waivers where a cell
cannot fill. B guarantees the fill by moving the instance into a
communication-heavy regime. **A is the honest-coverage variant; B is the
guaranteed-fill variant.** The comparison in §6 decides which is preferable.

---

## 5. Side-by-side

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| Total instances | 1,605 | 1,605 |
| Cells | 240 | 240 |
| Family equality | holds | holds |
| p per set (S1 / S2) | 5 / 5 | 5 / 5 |
| Dead cells | 81 forced | 81 forced |
| Value re-draw | σ=0.18 only | escalates to σ=0.6 / ×8 |
| 7:1 true in every cell | target, may waive | target, should hold |
| Low-p regime present | yes | yes |
| Fidelity to source costs | high | degrades in ~5 cells |
| Main risk | unfilled cells / waivers | instances no longer in source regime |

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

Both variants now cover the same cells, so coverage is no longer a differentiator.
The real trade is **fill guarantee (B) versus source fidelity (A)**.

---

## 7. Build order

1. Build **A (1,605, σ=0.18 only)** first — it establishes the pipeline and
   produces the waiver list, which is exactly the set of cells B must escalate.
2. Build **B (1,605, knob ladder)** second, reusing the same builder with the
   ladder enabled and the knob step recorded per instance.
3. Compare per §6.
4. Record the outcome in this file under a new "Outcome" section.

Both outputs must be kept side by side and clearly labelled. Do not overwrite one
with the other.

---

## 8. Provenance

- Base set: `ectd-real/ectd_selected_400.csv` (400 rows, 349 winners / 51 added)
- Win rates: measured 2026-11-25/26 on real topologies with value re-draw, σ=0.18,
  2 sources × 12 seeds per cell, 235 cells, 5,640 candidates
  (`scripts/measure_cell_rates.py` → `scripts/out/cell_rates.json`)
- Knob sweep: 2026-11-26 on the 6 hardest dead cells, σ ∈ {0.18, 0.35, 0.6, 1.0}
  × comm_scale ∈ {1, 2, 4, 8}
- Lattice arithmetic: `N = 165·r1 + 75·r2` (Set 1 / Set 2), derived from
  3 families × tasks × 5 p × r
- Dead-cell definition: 0 ECTD wins in the measured candidates (95% upper bound
  ≈ 5% at 60 draws)
- Related: `docs/InstanceExpansionPlan.md`, `ectd_real/make_instances.py`,
  `ectd_real/gen_new.py`, `scripts/measure_cell_rates.py`
