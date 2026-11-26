# Verification of the committed measurement artifacts

**Date:** 2026-11-26
**Scope:** `docs/measurements/*.json` checked against every quantitative claim in
`docs/Decision-1605-DualComposition.md` (branch `docs/decision-1605-dual-composition`).
**Method:** the JSON was read from the branch and every table in the decision
record was recomputed from it. No claim below rests on the doc's own arithmetic.

---

## 1. What holds up

### `cell_rates.json` — 235 cells, 5,640 candidates

24 candidates per cell (2 sources x 12 seeds). Reproduces **exactly**:

| Check | Doc | Measured |
|---|---|---|
| Cells | 235 | 235 |
| Candidates | 5,640 | 5,640 |
| Live by p (4/8/16/32/64) | 13/15/25/35/43 of 47 | identical |

The §4.0 table reproduces to the decimal, all ten rows:

| Set | p=4 | p=8 | p=16 | p=32 | p=64 |
|---|---:|---:|---:|---:|---:|
| Set 1 live cells | 7/32 | 6/32 | 13/32 | 21/32 | 29/32 |
| Set 1 pooled | 4.4% | 6.4% | 11.6% | 21.5% | 31.8% |
| Set 2 live cells | 6/15 | 9/15 | 12/15 | 14/15 | 14/15 |
| Set 2 pooled | 18.1% | 40.0% | 47.2% | 61.7% | 68.1% |

Set 1 live 76/160, Set 2 live 55/75, total 131/235, **dead 104**. This is the
strongest artifact in the repo and the §4.0 narrative is sound.

### `ladder_probe.json` — rungs 1-4

| Rung | sigma | comm_scale | Doc | Measured |
|---:|---:|---:|---:|---:|
| 1 | 0.18 | x1 | 6 | 6 |
| 2 | 0.35 | x4 | 47 | 47 |
| 3 | 0.6 | x4 | 9 | 9 |
| 4 | 0.6 | x8 | 15 | 15 |
| — | — | unfilled | 27 | 27 |

Exact. 104 records, sums correctly.

### `ladder_probe2.json` — rungs 5-8

| Rung | sigma | comm_scale | Doc | Measured |
|---:|---:|---:|---:|---:|
| 5 | 0.6 | x16 | 15 | 15 |
| 6 | 1.0 | x8 | 0 | 0 |
| 7 | 1.0 | x16 | 1 | 1 |
| 8 | 1.0 | x32 | 8 | 8 |

Exact. 27 records, sums correctly.

### `search_compare.json` — drift comparison

Ladder drift 0.6490-0.6802 (doc: 0.65-0.68), free-search drift 1.7384-1.7860
(doc: 1.74-1.79), free search fills 3/5 (doc: 3/5). Sound.

---

## 2. What does not hold up

### 2.1 Rung 9 does not exist

The doc's ladder table had a ninth row — sigma 1.0, comm_scale x64, **3 cells
filled** — and the text stated:

> "All 104 dead cells fill. The last three (Genome 1000@p4, LIGO 1000@p4,
> LIGO 900@p4) needed x64, where they reach 48-65% win rate."

`ladder_probe2.json` records those exact three cells as:

| Cell | wins | cand | step |
|---|---:|---:|---:|
| Genome 1000Nodes @p4 | 0 | 0 | 0 |
| LIGO 1000Nodes @p4 | 0 | 0 | 0 |
| LIGO 900Nodes @p4 | 0 | 0 | 0 |

`cand=0` means no candidate was scored. `step=0` means the cell never filled.
The doc's rung-9 row of "3" was the probe's **residue** — the three cells that
never filled — relabelled as "filled at x64". The 48-65% win rate has no
support in any committed artifact.

Rungs 1-8 account for 101 cells. The residue is 3. 101 + 3 = 104.

### 2.2 Two artifacts contradict each other on the same three cells

`search_compare.json`, ladder arm:

| Cell | cands | drift | verdict |
|---|---:|---:|---|
| LIGO 900@p4 | 4 | 0.6716 | filled |
| Genome 1000@p4 | 1 | 0.6490 | filled |
| LIGO 1000@p4 | 1 | 0.6712 | filled |

`ladder_probe2.json`, same three cells: never filled, 0 candidates.

Three of the five cells in `search_compare`'s ladder arm are exactly the three
that `ladder_probe2` records as unfillable. Same repo, same cells, opposite
results. One of the two is wrong, and the doc's "all 104 fill" depended on the
one that contradicts the ladder probe.

`search_compare.json` records no rung labels, so it cannot support "needed x64"
either way.

**Unresolved.** This needs a re-run of both scripts on the same three cells
before either artifact is cited again.

### 2.3 §2's family-level table was from a superseded measurement

Every row mismatched `cell_rates.json`. Largest gaps:

| Family | p | Doc (old) | Measured | Diff |
|---|---:|---:|---:|---:|
| LA | 8 | 83.3% | 30.8% | -52.5pp |
| GE | 16 | 93.3% | 62.5% | -30.8pp |
| FFT | 8 | 3.3% | 26.7% | +23.4pp |
| Genome | 16 | 0.0% | 19.2% | +19.2pp |

§4.0 itself says "Any earlier family-level map is too coarse and must not be
used." §2 used it anyway, and §5's side-by-side still carried its 81 dead cells.
Both are now replaced with the per-cell data.

### 2.4 "Confirmed at 60 candidates per cell" had no artifact

§2 claimed Genome p=4/p=8 and LIGO p=4/p=8 "produced 0 wins in 60".
`cell_rates.json` is 24 candidates per cell. No 60-candidate measurement is
committed. The claim was also contradicted by the data that does exist:

| Family | p | Wins | Rate |
|---|---:|---:|---:|
| Genome | 4 | 3/240 | 1.2% |
| Genome | 8 | 26/240 | 10.8% |
| LIGO | 4 | 7/264 | 2.7% |
| LIGO | 8 | 12/264 | 4.5% |

None of these is zero. Claim removed.

### 2.5 §8's "why not full randomization" table did not match `cell_rates.json`

| Cell | Doc "source resample" | `cell_rates.json` |
|---|---:|---:|
| LIGO 800@p64 | 80% | 7/24 = 29% |
| Genome 500@p32 | 33% | 16/24 = 67% |
| FFT 224@p64 | 87% | 18/24 = 75% |

The conclusion (full randomization destroys the edge-cost pattern) may well be
right, but these three figures were not from the committed measurement. The
"source resample" column is now restated from `cell_rates.json`; the "full
random" column is marked uncommitted and should be regenerated.

### 2.6 Small arithmetic errors

- "26 need x16 or beyond" — the doc's own table summed to **27** (15+1+8+3).
  After dropping rung 9 it is **24** (15+1+8).
- "552 of 1,605 instances in dead cells" — computed from 81 cells. At 104 dead
  cells it is 84x7 + 20x6 = **708** (44.1%, not 34%). If Genome 900's 5
  unmeasured cells also come up dead, 743.
- Dead-cell bound "~5% at 60 draws" — at 24 draws the rule of three gives
  **~12%**.

### 2.7 The lattice does not close

| Source | Per-cell quota | Total |
|---|---|---:|
| §3 lattice | 165x7 + 75x6 | 1,605 |
| §8 build loop | 165x8 + 75x7 | **1,845** |

240 instances apart. §3's quota is 6W+1A (Set 1) and 5W+1A (Set 2). §8 said
7W+1A and 6W+1A. The stated target of 1,404W/201A is 1,605 split 7:1 and
rounded — a global target that no uniform per-cell quota can produce, since
7:1 over 7 instances per cell needs 6.125 winners.

**Left OPEN in the decision record. Blocks the build.**

---

## 3. Consequence for the A-vs-B decision

The entire distinction in §4.3 and §5 was:

> "A is the honest-coverage variant; B is the guaranteed-fill variant."

B does not guarantee fill. It fills **101 of 104** cells. The three short cells
are all Set 1, so B delivers **1,584 of 1,605** instances, 21 short — and needs
the same waiver mechanism as A, just for 3 cells instead of 98.

A is worse than the record implied. At sigma=0.18 only 6 of 104 dead cells are
live (4 Set 1, 2 Set 2), so A fills 4x7 + 2x6 = 40 instances of the 708 sitting
in dead cells, waives **668**, and delivers **937 of 1,605**.

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| Cells filled | 6 of 104 | 101 of 104 |
| Instances delivered | 937 | 1,584 |
| Waived | 668 | 21 |

The §6 comparison criteria are still the right ones. The premise they are
applied to was not: this is a coverage-vs-fidelity trade, not
honesty-vs-guarantee.

### The three unfillable cells share a structure

Genome 1000@p4, LIGO 1000@p4, LIGO 900@p4 — the largest level of each family at
the smallest machine. That is the regime where ECTD's critical-path weighting
has no spare processors to exploit, which is the same mechanism §2 correctly
identifies as the cause of the dead cells. It is a real boundary, not noise.

Reporting "B fills 101/104, and the 3 that resist are the p=4 large-n corner"
is a stronger and more defensible result than asserting a guarantee the
artifacts do not show.

---

## 4. Corrections applied

1. Rung-9 row deleted. Restated as: rungs 1-8 fill 101 of 104; 3 cells
   (Genome 1000@p4, LIGO 1000@p4, LIGO 900@p4) resist every rung tested.
2. §2's family-level table replaced with the per-cell data from
   `cell_rates.json`. §5's 81 dead cells corrected to 104.
3. "0 wins in 60" claim removed; dead-cell bound corrected to ~12% at 24 draws.
4. §8 randomization table restated from `cell_rates.json`; "full random" column
   marked uncommitted.
5. 26 -> 24 cells at x16 or beyond; 552 -> 708 instances in dead cells.
6. A and B delivery counts stated explicitly (937 and 1,584).
7. Lattice arithmetic marked OPEN and blocking.

## 5. Still outstanding

- **Resolve the `search_compare` / `ladder_probe2` contradiction.** Re-run both
  on Genome 1000@p4, LIGO 1000@p4, LIGO 900@p4. Requires the parent-workspace
  data, which is not in this repo.
- **Settle the lattice:** 1,605 at 6W+1A/5W+1A, or 1,845 at 7W+1A/6W+1A.
- **Regenerate and commit the "full random" arm** of the randomization probe.
- **Measure Genome 900's 5 cells.** They have never been probed and are the only
  level with no real source file behind it.
