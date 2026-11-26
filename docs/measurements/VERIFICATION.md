# Verification of the committed measurement artifacts

**Date:** 2026-11-26 (rev. c — rung 9 restored, lattice settled at 1,845)
**Scope:** `docs/measurements/*.json` checked against every quantitative claim in
`docs/Decision-1605-DualComposition.md` (branch `docs/decision-1605-dual-composition`).
**Method:** the JSON was read from the branch and every table in the decision
record was recomputed from it. No claim below rests on the doc's own arithmetic.

> **Rev. c correction.** Rev. b of this file concluded that rung 9 did not exist
> and that two artifacts contradicted each other. Both conclusions were wrong.
> The cause is documented in §2.1 and §2.2 below, kept rather than deleted
> because the error is instructive: a probe that stops at ×32 records `cand=0`
> for a cell it never tested at ×64, and that is not evidence of unfillability.

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
(doc: 1.74-1.79), free search fills 3/5 (doc: 3/5), ladder fills 5/5. Sound.

---

## 2. The rung-9 question, resolved

### 2.1 Rung 9 exists — and rev. b was wrong to delete it

Rev. b read `ladder_probe2.json`'s three rows with `wins=0, cand=0` as proof the
cells were unfillable, and removed rung 9 from the decision record. That was a
misreading. `cand=0` means **no candidate was scored at any rung that script
tested** — and `probe_ladder2.py` stops at ×32:

```python
LADDER = [(0.6, 16.0), (1.0, 8.0), (1.0, 16.0), (1.0, 32.0)]   # rungs 5-8
```

Rung 9 (σ=1.0, ×64) is not in that list. The probe could not have found it.

`compare_search.py` does test it. Its ladder arm is hardcoded:

```python
nc, edges = ladder_candidate(compc, commc, n, ps, p, rng, 1.0, 64.0)
```

and it fills all three cells:

| Cell | Candidates to fill | Drift |
|---|---:|---:|
| Genome 1000 @p4 | 1 | 0.6490 |
| LIGO 1000 @p4 | 1 | 0.6712 |
| LIGO 900 @p4 | 4 | 0.6716 |

Rungs 1-8 fill 101 cells. Their residue is exactly 3. Rung 9 fills 3. 101 + 3 =
104. The ladder is **nine rungs and fills every dead cell.**

### 2.2 The "contradiction" was two different experiments

Rev. b reported `search_compare.json` and `ladder_probe2.json` as contradicting
each other on the same three cells. They are not the same experiment: one runs at
×64, the other stops at ×32. Both artifacts are correct, and the decision
record's rev. b caveat ("at least 2/5, possibly 5/5") is withdrawn — the 5/5
stands.

### 2.3 What is still unsupported

The original rung-9 row claimed the three cells "reach 48-65% win rate" at ×64.
No committed artifact reports a win rate for them. `compare_search.json` records
candidates-to-first-win, not a rate, and 1 candidate is not a rate. The claim is
withdrawn; the decision record now states fill only, and says the realised rate
must be recorded at build time.

---

## 3. What does not hold up (unchanged from rev. b)

### 3.1 §2's family-level table is from a superseded measurement

Every row mismatched `cell_rates.json`. Largest gaps:

| Family | p | Old doc | Measured | Diff |
|---|---:|---:|---:|---:|
| LA | 8 | 83.3% | 30.8% | -52.5pp |
| GE | 16 | 93.3% | 62.5% | -30.8pp |
| FFT | 8 | 3.3% | 26.7% | +23.4pp |
| Genome | 16 | 0.0% | 19.2% | +19.2pp |

§4.0 itself says "Any earlier family-level map is too coarse and must not be
used." §2 used it anyway. **Fixed in rev. c** — §2 now carries the recomputed
pooled table.

### 3.2 "Confirmed at 60 candidates per cell" has no artifact

The old §2 claimed Genome p=4/p=8 and LIGO p=4/p=8 "produced 0 wins in 60".
`cell_rates.json` is 24 candidates per cell. No 60-candidate measurement is
committed, and the claim is contradicted by the data that exists:

| Family | p | Wins | Rate |
|---|---:|---:|---:|
| Genome | 4 | 3/240 | 1.2% |
| Genome | 8 | 26/240 | 10.8% |
| LIGO | 4 | 7/264 | 2.7% |
| LIGO | 8 | 12/264 | 4.5% |

None of these is zero. **Fixed in rev. c** — claim removed.

### 3.3 §8's "why not full randomization" table did not match `cell_rates.json`

| Cell | Old doc "source resample" | `cell_rates.json` |
|---|---:|---:|
| LIGO 800@p64 | 80% | 7/24 = 29% |
| Genome 500@p32 | 33% | 16/24 = 67% |
| FFT 224@p64 | 87% | 18/24 = 75% |

The conclusion (full randomization destroys the edge-cost pattern) is supported
by `search_compare.json` independently. **Fixed in rev. c** — table restated from
`cell_rates.json`, "full random" column marked uncommitted.

### 3.4 Small arithmetic errors

- "26 need x16 or beyond" — the ladder table sums to **27** (15+1+8+3). Fixed.
- "552 of 1,605 instances in dead cells" — computed from 81 cells. At 104 dead
  cells and the 1,845 lattice it is **812 of 1,845** (44.0%). Fixed.
- "81 dead cells" in §5 — 104. Fixed.

### 3.5 The lattice did not close

| Source | Per-cell quota | Total |
|---|---|---:|
| Old §3 lattice | 165x7 + 75x6 | 1,605 |
| Old §8 build loop | 165x8 + 75x7 | **1,845** |

**Settled at 1,845** (r1=8, r2=7). The deciding evidence:

| | 1,605 lattice | 1,845 lattice |
|---|---:|---:|
| Set 1 per-cell ratio | 6:1 | **7:1 exact** |
| Pooled winners:added | 1,365/240 = 5.6875:1 | **1,605/240 = 6.6875:1** |
| Base set ratio | 349/51 = 6.8431:1 | 349/51 = 6.8431:1 |
| Distance from base set | 1.156 | **0.156** |

Set 1's quota is exactly 7:1 under 1,845, which is the ratio the design is named
for. And 1,605 is precisely the *winner* count of the 1,845 lattice — the old
total was almost certainly the winner count mistaken for a grand total. The
"1,404W/201A" target is withdrawn: it is 1,605 split 7:1 and rounded, and no
uniform per-cell quota produces it.

---

## 4. Consequence for the A-vs-B decision

Restated at 1,845:

| | A — FORCE | B — KNOB LADDER |
|---|---:|---:|
| Target | 1,845 | 1,845 |
| Delivered | 1,079 | 1,845 |
| Waived | 766 | 0 |
| Cells filled (of 104 dead) | 6 | 104 |
| Cells outside source regime | 0 | 27 |

**B is a guaranteed fill; A is not.** Rev. b's framing ("neither is a guaranteed
fill") was a consequence of deleting rung 9. With rung 9 restored, B delivers
every instance and needs no waiver mechanism at all.

That makes the trade sharper and simpler than any previous revision stated:
**A is 58.5% coverage at full source fidelity. B is 100% coverage with 27 cells
(26%) pushed outside their source communication regime.** The §6 comparison
criteria are unchanged and still the right ones.

### The three rung-9 cells share a structure

Genome 1000@p4, LIGO 1000@p4, LIGO 900@p4 — the largest level of each family at
the smallest machine. That is the regime where ECTD's critical-path weighting has
no spare processors to exploit, which is the same mechanism §2 identifies as the
cause of the dead cells. They need the most extreme knob setting in the ladder
(σ=1.0, ×64) to fill, and they fill in 1-4 candidates once it is applied. It is a
real boundary, and the build should report these three cells separately.

---

## 5. Outstanding

1. **Regenerate and commit the "full random" column** of §7's randomization
   table. The direction is supported; the specific figures are not committed.
2. **Probe Genome 900's 5 unmeasured cells** at build time. They are excluded
   from every count here; if all 5 are dead the totals become 109 cells and 852
   instances.
3. **Record the realised win rate for the three rung-9 cells** during the build.
   The withdrawn 48-65% figure should not be replaced by an assumption.
4. **Decide whether 27 escalated cells is acceptable** for Variant B. This is the
   real cost of B's coverage and it is a judgement call, not a measurement.
