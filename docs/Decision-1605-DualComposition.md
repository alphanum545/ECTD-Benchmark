# Decision record: build BOTH compositions (1,845 instances)

**Status:** APPROVED — both variants to be built and compared.
**Date:** 2026-11-25 (rev. 2026-11-26c: lattice settled at 1,845, rung 9 restored)
**Decided by:** user
**Supersedes:** the single-variant plan in `docs/InstanceExpansionPlan.md` §4.4

> **Rev. 2026-11-26c — lattice settled, rung 9 restored.** The lattice is fixed at
> **1,845** instances (165×8 + 75×7), so Set 1 runs **7W+1A** and Set 2 runs
> **6W+1A**. Every instance count below is recomputed from that, not scaled from
> the old 1,605 figures. Two corrections to rev. 2026-11-26b:
>
> 1. **Rung 9 exists.** `scripts/compare_search.py` hardcodes σ=1.0 / ×64 and
>    fills the three cells rev. 26b called unfillable in 1, 1 and 4 candidates.
>    The apparent contradiction with `ladder_probe2.json` is not a contradiction:
>    that probe stops at ×32 and never tested rung 9. Both artifacts are correct.
> 2. The **"48–65% win rate at ×64"** figure still has no artifact behind it and
>    is withdrawn. What the artifacts support is *fill*, not a rate.
>
> Full reconciliation in [`measurements/VERIFICATION.md`](measurements/VERIFICATION.md).

> **On the filename.** "1605" is the **winner** count of the 1,845 lattice, not the
> instance count — which is very likely how the arithmetic went wrong in the first
> place. The filename is kept for link stability; the title is not.

> **Location note.** This record lives in the `ECTD-Benchmark` repo. The data it
> references (`ectd-real/ectd_selected_400.csv`, `scheduling-benchmark/data/`)
> sits in the parent workspace, one level above this repo's root. Paths are
> written workspace-relative.

---

## 1. The decision

We are building **two** 1,845-instance datasets from the same 400-file base set,
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

The lattice requires a fixed number of ECTD wins per cell — **7 in Set 1 and 6
in Set 2** under the 1,845 arithmetic. Measured ECTD win rates on real topologies
with the value-re-draw method, from `docs/measurements/cell_rates.json` (24
candidates per cell: 2 sources × 12 seeds, 235 cells, 5,640 candidates):

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

**Dead cell inventory:** 104 of 235 measured cells (44%), holding **812 of 1,845
instances (44.0%)**. Genome 900's 5 cells are unmeasured (§7) and are excluded.

| Family | Cells | Measured | Dead | Viable | Instances | In dead cells |
|---|---:|---:|---:|---:|---:|---:|
| Montage | 55 | 55 | 31 | 24 | 440 | 248 |
| Genome | 55 | 50 | 22 | 28 | 440 | 176 |
| LIGO | 55 | 55 | 31 | 24 | 440 | 248 |
| FFT | 25 | 25 | 10 | 15 | 175 | 70 |
| GE | 25 | 25 | 3 | 22 | 175 | 21 |
| LA | 25 | 25 | 7 | 18 | 175 | 49 |
| **Total** | **240** | **235** | **104** | **131** | **1,845** | **812** |

If Genome 900's 5 unmeasured cells also come up dead, that becomes 109 dead
cells and 852 instances.

---

## 3. Variant A — FORCE

**Lattice:** 1,845 instances, 240 cells.

```
Set 1 (D1): 3 families × 11 tasks × 5 p × 8 = 1320   (440/family, 7W+1A)
Set 2 (D2): 3 families ×  5 tasks × 5 p × 7 =  525   (175/family, 6W+1A)
TOTAL: 1845        cells: 240 (165 + 75)
```

| Family | Format | Tasks | p | Workflows/cell | Cells | Instances |
|---|---|---:|---:|---:|---:|---:|
| Montage | D1 | 11 | 5 | 8 | 55 | 440 |
| Genome | D1 | 11 | 5 | 8 | 55 | 440 |
| LIGO | D1 | 11 | 5 | 8 | 55 | 440 |
| FFT | D2 | 5 | 5 | 7 | 25 | 175 |
| GE | D2 | 5 | 5 | 7 | 25 | 175 |
| LA | D2 | 5 | 5 | 7 | 25 | 175 |

**Properties:** family equality holds · full 5-value p grid in both sets ·
all 240 cells present · target ratio **1,605W / 240A = 6.6875:1**

> **Why 1,845 and not 1,605.** The two readings were 165×7 + 75×6 = 1,605
> (6W+1A / 5W+1A) and 165×8 + 75×7 = 1,845 (7W+1A / 6W+1A). The 1,845 lattice is
> the one that matches the stated design intent, on three counts:
>
> - **Set 1's per-cell ratio is exactly 7:1** (7 winners, 1 added). That is the
>   ratio the whole design is named for. The 1,605 lattice gives 6:1 in Set 1.
> - **Pooled ratio lands near the base set.** 1,605/240 = 6.6875:1 against the
>   base set's 349/51 = 6.8431:1 — a gap of 0.16. The 1,605 lattice gives
>   1,365/240 = 5.6875:1, a gap of 1.16.
> - **1,605 is exactly the winner count of the 1,845 lattice.** The old total was
>   almost certainly the winner count read as a grand total.
>
> The old "1,404W / 201A" target is withdrawn: it is 1,605 split 7:1 and rounded,
> and no uniform per-cell quota produces it.

**Build rule:** every cell must yield its full quota. Dead cells get a hard draw
cap; if a cell cannot fill, it is recorded as a **waiver** in the manifest rather
than silently backfilled.

**Known risk — and it is large.** At σ=0.18 the measurement finds only 6 of the
104 dead cells live (24 candidates each). Those six are four Set 1 cells
(Montage 1000@p64, Montage 100@p16, Montage 100@p8, Montage 300@p8) and two
Set 2 cells (FFT 96@p4, LA 11@p64). So A fills 4×8 + 2×7 = **46** instances in
dead cells, leaves **766 waived**, and delivers **1,079 of 1,845** (58.5%).

The global ratio must be recomputed on what is actually built and the label
corrected; it must not be asserted as 7:1 when it isn't.

---

## 4. Variant B — KNOB LADDER

**Revision 2026-11-26.** Variant B was originally "drop the dead cells and use
only the processor values that survive." A full per-cell measurement (235 cells,
5,640 candidates) plus a knob sweep changed that. The measurement is in §4.0 and
the revised definition is in §4.2. The original reading is kept in §4.1 as
superseded history, because the reasoning still matters for anyone re-deriving
this.

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
  1,053 instances, but per-family counts become 440 / 176 / 176 — **breaks family
  equality**, the invariant the lattice exists to enforce. Rejected.
- **B2, drop to common p per set:** Set 1 → p={32,64}, 66 cells; Set 2 →
  p={16,32,64}, 45 cells; 111 cells total. At r1=8, r2=7 → 528 + 315 = 843
  instances. Family equality holds, 7:1 honest everywhere, but Set 1 loses
  p=4/8/16 and Set 2 loses p=4/8. The low-parallelism regime disappears from the
  dataset entirely.

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

**Approved ladder** — tried in order per cell until the quota fills. **Nine
rungs.** The original 4-rung ladder left 27 cells unfilled; rungs 5–8 filled 24
of them; rung 9 filled the last 3.

| Rung | σ | comm_scale | Cells filled here | Source |
|---:|---:|---:|---:|---|
| 1 | 0.18 | ×1 | 6 | `ladder_probe.json` |
| 2 | 0.35 | ×4 | 47 | `ladder_probe.json` |
| 3 | 0.6 | ×4 | 9 | `ladder_probe.json` |
| 4 | 0.6 | ×8 | 15 | `ladder_probe.json` |
| 5 | 0.6 | ×16 | 15 | `ladder_probe2.json` |
| 6 | 1.0 | ×8 | 0 | `ladder_probe2.json` |
| 7 | 1.0 | ×16 | 1 | `ladder_probe2.json` |
| 8 | 1.0 | ×32 | 8 | `ladder_probe2.json` |
| 9 | 1.0 | ×64 | 3 | `search_compare.json` |

**104 of 104 dead cells fill.** Rungs 1–8 account for 101 cells, and their
residue is exactly the three that rung 9 fills.

> **Why rung 9's evidence comes from a different script.** `probe_ladder2.py`
> stops at ×32, so it records those three cells as `wins=0, cand=0` — never
> filled *within the rungs it tested*. `compare_search.py` hardcodes
> σ=1.0 / ×64 as its "ladder" arm and fills all three:
>
> | Cell | Candidates to fill | Drift |
> |---|---:|---:|
> | Genome 1000 @p4 | 1 | 0.649 |
> | LIGO 1000 @p4 | 1 | 0.671 |
> | LIGO 900 @p4 | 4 | 0.672 |
>
> These are not contradictory results on the same experiment. They are the same
> experiment at two different rungs, and the ×32 probe's zeros are the reason
> rung 9 was added. An earlier revision of this record read the `cand=0` rows as
> "unfillable" and deleted rung 9; that was wrong, and the correction is recorded
> in `measurements/VERIFICATION.md` §2.1.
>
> **What is still not supported:** the withdrawn claim that the three cells
> "reach 48–65% win rate" at ×64. No committed artifact reports a win rate for
> them. What is established is that a win was found, in 1, 1 and 4 candidates.
> A single win is not a rate, and the build should record the realised rate
> rather than assume one.

Distribution: only **6 of 104** dead cells fill at baseline. 98 need escalation,
and **27 need ×16 or beyond**. Those 27 are the instances that are no longer in
their source communication regime.

**Cap 20 candidates per rung, then escalate.** Tested on the hardest cell: a
40-candidate cap took 247 candidates and 14.0 s; a 20-candidate cap took 131
candidates and 7.5 s and still filled. Grinding a low rung that produces nothing
wastes half the budget.

**Lattice:** 240 cells, 1,845 instances, 5 p values in both sets, family
equality holds.

**Mandatory recording:** the rung used must be written per instance in the
manifest. Any result drawn from a ×4 or higher cell must be reported separately
from a ×1 cell, because the instance is no longer in the same communication
regime as its source.

### 4.3 What now separates A from B

Both variants keep all 5 p values and all 240 cells. They differ only in how hard
they push:

| | A — FORCE | B — KNOB LADDER |
|---|---|---|
| Cells | 240 | 240 |
| p per set | 5 / 5 | 5 / 5 |
| Dead cells | forced, may waive | forced via ladder |
| Cells filled | 6 of 104 | 104 of 104 |
| Instances delivered | 1,079 of 1,845 | 1,845 of 1,845 |
| Value re-draw | σ=0.18 only | escalates to σ=1.0 / ×64 |
| Fidelity to source | high | degrades in 27 cells |
| 7:1 | target, may waive | target, holds |

A stays faithful to the source cost distribution and accepts waivers where a cell
cannot fill. B pushes every cell over the line by moving the instance into a
communication-heavy regime.

**B is a guaranteed fill; A is not.** B delivers all 1,845 instances with no
waivers. A delivers 1,079 and waives 766 — 41.5% of the dataset. **A is the
high-fidelity variant; B is the high-coverage variant.** The comparison in §6
decides which is preferable.

---

## 5. Side-by-side

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| Target instances | 1,845 | 1,845 |
| Delivered instances | 1,079 | 1,845 |
| Waived instances | 766 | 0 |
| Cells | 240 | 240 |
| Family equality | holds | holds |
| p per set (S1 / S2) | 5 / 5 | 5 / 5 |
| Dead cells | 104 forced | 104 forced |
| Cells filled | 6 of 104 | 104 of 104 |
| Value re-draw | σ=0.18 only | escalates to σ=1.0 / ×64 |
| 7:1 true in every cell | target, may waive | holds |
| Low-p regime present | yes | yes |
| Fidelity to source costs | high | degrades in 27 cells |
| Main risk | 766 waived instances | 27 cells outside source regime |

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

Both variants target the same cells, so the lattice is not a differentiator.
The real trade is **coverage (B) versus source fidelity (A)**, and it is stark:
A waives 766 instances, B waives none.

---

## 7. Build method — the part a fresh session needs

**The method is resampling in a loop. Nothing more.** "Deterministic" means only
that the seed is fixed, so the same seed produces the same file every run.

```python
comp[r][c] = source_comp[r][c % p_src] * lognormal(0, sigma)
comm[u][v] = source_comm[u][v] * scale        # -1 stays -1, always
```

Then score the six policies, keep the draw if it advances the cell's quota, repeat.

### Per-cell loop

```
for rung in LADDER:                      # 9 rungs, see §4.2
    for candidate in range(20):          # cap 20 per rung
        resample comp and comm from source
        score all 6 policies
        if ECTD wins and winners < quota_w:  keep
        if ECTD loses and added < 1:        keep
    if quota met: stop, record rung
```

**Quotas — settled.** Set 1 cells need **7 winners + 1 added** (8 instances).
Set 2 cells need **6 winners + 1 added** (7 instances). 165×8 + 75×7 = **1,845**.
The competing reading (6W+1A / 5W+1A = 1,605) is withdrawn; §3 records why.

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
exactly what ECTD's critical-path weighting exploits.

**The ladder's advantage over free search is real and measured.** From
`search_compare.json`, same five cells, same 60-candidate budget:

| | Cells filled | Drift from source |
|---|---:|---|
| Escalating ladder (σ=1.0, ×64) | **5 of 5** | 0.649–0.680 |
| Free random search | 3 of 5 | 1.738–1.786 |

Free search fails outright on LIGO 900@p4 and LIGO 1000@p4 (0 wins in 60
candidates each), and where it does fill it drifts 2.6× further from the source
values. The ladder preserves the edge-cost pattern; free search destroys it.

> **Earlier caveat withdrawn.** Rev. 26b flagged a contradiction between
> `search_compare.json` and `ladder_probe2.json` on the same three cells and
> downgraded this to "at least 2/5, possibly 5/5". There is no contradiction:
> the probe stops at ×32 and the comparison runs at ×64. See §4.2. The 5/5
> stands.

### Structure preservation — verified

The `-1` pattern is never touched. Round-trip verified byte-identical:

| File | `-1` entries | Round-trip |
|---|---:|---|
| LIGO 1000 @p4 | 998,758 | identical |
| Genome 500 @p32 | 246,418 | identical |

End-to-end test: filled a cell (8 instances in 28 candidates), wrote D3,
re-parsed — comp matrix identical, comm matrix identical, `-1` count identical.

### Genome 900 is synthesised

Genome has 10 real levels; Montage and LIGO have 11. To make Set 1 uniform at 11,
Genome's 900 is synthesised: n=901, 2,729 edges, CCR 0.51, validates and scores.
**It is the only level with no real source file behind it.** Its 5 cells were
never measured and must be probed at build time.

**The original generator is not available.** This section previously said the
level is built with `_genome` from `ectd_real/gen_new.py`. That file is
referenced here and in §9 but **is not in this repo and was never committed**, so
it cannot be run. `scripts/genome900.py` reconstructs a DAG satisfying the three
declared properties instead, and verifies them rather than asserting them:

| Property | Target | Reconstructed |
|---|---:|---:|
| nodes | 901 | 901 |
| edges | 2,729 | 2,729 |
| CCR | 0.51 | 0.5103 |

Topology: one entry task → 450 stage-1 → 445 stage-2 (window 4) → 5 tail nodes
(99 parents each, chained). 450 + 1,780 + 495 + 4 = 2,729.

**The single entry task is load-bearing, not cosmetic.** A first reconstruction
had 450 independent stage-1 roots and no entry. It had the right node and edge
counts and a valid DAG, and then filled **0 of 7** winners at p=4 across all nine
ladder rungs in 180 candidates. `Problem` normalises a multi-root graph by
inserting a zero-cost dummy entry, and a dummy entry has nothing to duplicate —
so entry duplication, the mechanism ECTD is built on, was inert. With one real
entry the same cell fills 7/7 at rung 9. Any future regeneration of this level
must keep a single real entry.

Every instance built from this source is marked `synthesised: true` in the
manifest under `synthesised_sources`, so the five Genome-900 cells can never be
mistaken for measured corpus data.

---

## 8. Build order

1. Build **A (1,845, σ=0.18 only)** first — it establishes the pipeline and
   produces the waiver list, which is exactly the set of cells B must escalate.
2. Build **B (1,845, knob ladder)** second, reusing the same builder with the
   ladder enabled and the rung recorded per instance.
3. Compare per §6.
4. Record the outcome in this file under a new "Outcome" section.

Both outputs must be kept side by side and clearly labelled. Do not overwrite one
with the other.

### 8.1 Builder status (2026-11-26, rev. b)

**The builder exists and is tested; neither variant has been built on the real
corpus yet.**

- `scripts/build_composition.py` — both variants, nine-rung ladder, per-instance
  rung recorded, waivers recorded rather than backfilled.
  `--self-check` verifies the lattice arithmetic, `-1` preservation and the D3
  round-trip.
- `scripts/verify_composition.py` — the gate. Re-parses every instance, checks
  the `-1` pattern against the exact source the manifest names, validates all
  six schedules, confirms each winner/added label, and checks the recorded rung
  against the knobs actually applied.
- `scripts/make_synth_sources.py` — synthetic D3 fixture at the real directory
  depth, so the pipeline runs without the 3.1 GB corpus.
- `scripts/genome900.py` — the Genome 900 reconstruction (§7), with its declared
  properties asserted in `main()`.
- `scripts/_paths.py` — one place that resolves the package and the corpus, so
  every script runs from any working directory.

**Path resolution was broken and is now fixed.** The scripts previously computed
`ROOT = os.path.dirname(HERE)`, commented "the parent workspace". That is only
true if the script sits at the repo root; these sit in `scripts/`, so `ROOT` was
the repo and the package path became `<repo>/ECTD-Benchmark/ECTD-Benchmark`,
which does not exist. They appeared to work only when launched from the repo
root, because the current directory happened to be on `sys.path`. The three
measurement scripts also wrote to `scripts/out/` rather than the committed
`docs/measurements/`. Both are fixed; `_paths.py` now searches the plausible
locations and honours `ECTD_DATA_ROOT`.

**What has been verified, on the synthetic fixture only:** 95 cells (the fixture
has 3 levels per family, not the real 10–11), 1,287 instances across both
variants, every instance re-parsed and validated under all six policies.

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| delivered | 578 | 709 |
| winners / added | 490 / 88 | 614 / 95 |
| waived | 137 | 6 |
| cells filled | 65 of 95 | 94 of 95 |
| realised ratio | 5.5682 | 6.4632 |
| rung usage | all rung 1 | 1:558, 2:86, 3:23, 4:21, 5:13, 9:8 |

The A-vs-B behaviour is confirmed qualitatively — A waives heavily, B fills — but
**no figure in §3, §4 or §5 is a build result.** They remain predictions from the
measurement artifacts. The fixture numbers above are a pipeline test, not a
forecast of the real build: the fixture's levels are small (9–224 nodes) and its
DAGs are synthetic, so its win rates have nothing to do with the real corpus.

**What has not been done:** the real run. It needs the corpus and the 400-row
base set, neither of which is in this repo. Until it runs, `delivered`,
`waived`, `realised_ratio` and `cells_outside_source_regime` are unmeasured.

**One thing the real run will settle that the probes could not:** the rung
distribution. §4.2's per-rung table comes from the probes, which used their own
seed strings. The builder uses `build|<cell>|<variant>|<rung>|<cand>` and will
produce its own distribution. Neither is wrong; they are different draws. The
manifest's `rung_usage` is the number to quote for the built dataset, and the
probe table must not be presented as the build's rung distribution.


---

## 9. Provenance

- Base set: `ectd-real/ectd_selected_400.csv` (400 rows, 349 winners / 51 added)
- Win rates: measured 2026-11-25/26 on real topologies with value re-draw, σ=0.18,
  2 sources × 12 seeds per cell, 235 cells, 5,640 candidates
  (`scripts/measure_cell_rates.py` → `docs/measurements/cell_rates.json`)
- Knob sweep: 2026-11-26 on the 6 hardest dead cells, σ ∈ {0.18, 0.35, 0.6, 1.0}
  × comm_scale ∈ {1, 2, 4, 8}
- Ladder probe: `scripts/probe_ladder.py` (104 cells, rungs 1–4) →
  `docs/measurements/ladder_probe.json`; `scripts/probe_ladder2.py` (27 stubborn
  cells, rungs 5–8) → `docs/measurements/ladder_probe2.json`
- Rung 9: `scripts/compare_search.py` (σ=1.0, ×64) →
  `docs/measurements/search_compare.json`
- Reconciliation: `docs/measurements/VERIFICATION.md` (2026-11-26) — every figure
  above re-derived from the committed JSON
- Lattice arithmetic: `N = 165·r1 + 75·r2` (Set 1 / Set 2), r1=8, r2=7
- Dead-cell definition: 0 ECTD wins in 24 measured candidates (95% upper bound
  ≈ 12% at 24 draws)
- Related: `docs/InstanceExpansionPlan.md`, `ectd_real/make_instances.py`,
  `ectd_real/gen_new.py`, `scripts/measure_cell_rates.py`,
  `scripts/probe_ladder.py`, `scripts/probe_ladder2.py`, `scripts/compare_search.py`
