# ECTD ranking revision: verified exploratory alternatives

**The requested aggregate ordering is achievable on smaller selected cohorts. It is not achievable on any 1,967 distinct instances from the saved 3,072-instance pool.** The original 1,467-winner + 500-loss cohort remains a separate completed study. None of the alternatives below preserves that composition.

The closest match to both the full earlier order and the earlier approximately 75% ECTD win share is the **209-instance candidate: 156 strict ECTD wins and 53 genuine losses**. It has **ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in both placement modes. The 497-instance candidate offers more cases and meets the latest three explicit relationships, while placing LSTD before HEFT. All three alternatives have been fully replayed locally.

Here, “better” and `>` mean a lower **pooled geometric mean makespan** on the identical selected cases. They do not mean the same ordering on every instance or within every workflow family. Makespans are synthetic cost units.

## 1. Concrete choices and the count trade-off

| Profile | Instances | ECTD wins | ECTD losses | ECTD win share | Pooled order in both modes |
| --- | --- | --- | --- | --- | --- |
| full_order_209 | 209 | 156 | 53 | 74.64% | ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT |
| latest_497 | 497 | 371 | 126 | 74.65% | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT |
| full_order_225 | 225 | 134 | 91 | 59.56% | ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT |

Each profile contains all six workflow families and both ECTD wins and genuine losses within each family. The profiles overlap; they are alternative selections, not three independent experiments to combine. The 209 profile omits 1,311 of the original 1,467 winners; the 497 profile omits 1,096; the 225 profile omits 1,333.

## 2. Full earlier order, approximately 75% ECTD wins: 209 cases

**ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in append and insertion. ECTD is the strict sole winner on 156 cases and is beaten on 53 cases in each mode, with zero ECTD tied-best cases. Every competing algorithm wins some individual cases.

| Algorithm | Append geometric makespan | Insertion geometric makespan |
| --- | --- | --- |
| ECTD | 592.364448 | 582.665115 |
| AEFT | 632.064257 | 617.839300 |
| BPPTS | 651.744795 | 633.676923 |
| HEFT | 653.513639 | 642.577906 |
| LSTD | 654.295849 | 643.238812 |
| IPEFT | 655.002317 | 644.152919 |

### Composition across workflow families

| Family | Strict ECTD wins | Genuine ECTD losses | Total |
| --- | --- | --- | --- |
| FFT | 24 | 9 | 33 |
| GE | 45 | 9 | 54 |
| Genome | 26 | 25 | 51 |
| LA | 42 | 6 | 48 |
| LIGO | 11 | 3 | 14 |
| Montage | 8 | 1 | 9 |

Family representation is uneven: Montage has nine cases, including only one ECTD loss. This is a pooled comparison with each instance equally weighted in log space; it is not a family-balanced comparison.

### Individual winners

| Sole winner | Append instances | Insertion instances |
| --- | --- | --- |
| ECTD | 156 | 156 |
| AEFT | 9 | 15 |
| BPPTS | 15 | 8 |
| HEFT | 14 | 12 |
| LSTD | 7 | 10 |
| IPEFT | 4 | 3 |
| Tied best among competitors | 4 | 5 |

The tied-best rows involve competing methods; ECTD loses those cases. Thus this is a mixed set, with genuine successes for each other algorithm, despite ECTD winning approximately three quarters of the selected instances.

### Size qualification

This is a verified feasible 209-case solution. The solver reached its 40-second time limit; its upper bound was 212 and its reported gap was 1.4354%. **209 is not proved to be the largest feasible count.** No solver-optimality claim is needed to verify the actual selected results.

## 3. Larger set meeting the latest explicit relationships: 497 cases

**ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT** in both modes. This makes AEFT and BPPTS better than LSTD and places IPEFT last. It changes the earlier relative positions of HEFT and LSTD.

| Algorithm | Append geometric makespan | Insertion geometric makespan |
| --- | --- | --- |
| ECTD | 529.190904 | 523.660534 |
| AEFT | 574.482846 | 566.467979 |
| BPPTS | 575.069702 | 568.945531 |
| LSTD | 575.658011 | 569.533465 |
| HEFT | 607.860390 | 601.997871 |
| IPEFT | 608.529186 | 602.616526 |

| Family | Strict ECTD wins | Genuine ECTD losses | Total |
| --- | --- | --- | --- |
| FFT | 51 | 10 | 61 |
| GE | 83 | 16 | 99 |
| Genome | 51 | 54 | 105 |
| LA | 113 | 19 | 132 |
| LIGO | 47 | 17 | 64 |
| Montage | 26 | 10 | 36 |

ECTD has 371 strict wins and 126 genuine losses in each mode, or 74.6479% wins. Each family contains at least ten wins and ten losses. HiGHS reported 497 as the maximum only under the stated revised chain, the narrow win-share interval, the minimum family counts, and the 0.1% adjacent-margin constraint. It is not an unrestricted maximum over arbitrary sampling designs.

## 4. Full earlier order with a smaller ECTD win share: 225 cases

**ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in both modes, with 134 strict wins and 91 losses: 59.5556% ECTD wins. HiGHS reported this size as optimal under the saved full-chain, majority-win, minimum-one-win-and-loss-per-family, and 0.1%-margin constraints. The exact majority constraint is wins minus losses at least two.

| Algorithm | Append geometric makespan | Insertion geometric makespan |
| --- | --- | --- |
| ECTD | 599.901899 | 588.974098 |
| AEFT | 633.184995 | 616.262532 |
| BPPTS | 653.057077 | 634.268063 |
| HEFT | 653.770277 | 642.525301 |
| LSTD | 654.451430 | 643.194169 |
| IPEFT | 655.110996 | 643.841886 |

| Family | Strict ECTD wins | Genuine ECTD losses | Total |
| --- | --- | --- | --- |
| FFT | 18 | 15 | 33 |
| GE | 41 | 16 | 57 |
| Genome | 25 | 37 | 62 |
| LA | 34 | 13 | 47 |
| LIGO | 9 | 5 | 14 |
| Montage | 7 | 5 | 12 |

This profile provides 16 more cases than the 209 profile while moving the win/loss mixture farther from the earlier roughly 75/25 composition.

## 5. Why changing the 500 additions cannot fix the 1,967-case set

For any pair A and B, define `d_i = log(makespan_A_i / makespan_B_i)`. The geometric mean ratio on a subset S is `exp(sum(d_i for i in S) / len(S))`. Therefore, the smallest possible ratio on any fixed-size subset is obtained by taking the smallest corresponding log ratios. This computes an exact finite-pool bound; it does not rely on a heuristic optimizer.

Even allowing **any 1,967 distinct cases** from all 3,072 candidates, removing all ECTD-win and workflow-family requirements, the best possible BPPTS/LSTD ratios are:

| Mode | Lowest possible BPPTS / LSTD ratio on any 1,967 cases |
| --- | --- |
| append | 1.027011251 |
| insertion | 1.014995090 |

Both ratios exceed one. Hence BPPTS remains slower than LSTD even under its individually most favorable 1,967-case selection in either mode. A selection satisfying all the requested relationships is therefore impossible at that size within this saved pool.

Keeping the specific 1,467 winners and adding any 500 of the 1,112 genuine losses gives even stronger blockers:

| Required comparison | Best possible append ratio | Best possible insertion ratio |
| --- | --- | --- |
| AEFT / LSTD | 1.021182037 | 1.011102978 |
| BPPTS / LSTD | 1.065454829 | 1.049819542 |
| HEFT / IPEFT | 1.041453068 | 1.044001669 |

Each row and mode is optimized separately, so these bounds are deliberately optimistic. Ratios above one disprove the desired relation; a ratio below one alone would not establish simultaneous feasibility. The source-level analysis also permits mixed/tied additions and checks arithmetic mean differences; those relaxations do not remove the main blockers. Detailed receipts are in `selection_evidence/exact_pairwise_bounds.json` and `selection_evidence/unrestricted_1967_impossibility.json`.

## 6. Selection protocol and interpretation

Only the membership changes. Every exported DAG line is copied byte-for-byte from the earlier candidate archive. The exact algorithm implementations and common scheduling engine are the same as in the completed 1,967-case study. Standard algorithm names are used in new outputs; legacy archive keys are retained solely for source traceability.

The attempted source pool has 3,072 synthetic cases: 1,467 strict ECTD winners in both modes, 1,112 genuine ECTD losses in both modes, and 493 mixed or tied cases. The new optimizations select from the first two groups. “Strict win” means ECTD has a smaller makespan than all five comparators. “Genuine loss” means at least one comparator has a smaller makespan. Comparisons use relative tolerance 1e-12 and absolute tolerance 1e-9.

Selection maximizes the count subject to the recorded ordering and composition constraints. For each adjacent pair, the aggregate requirement is `GM(first) / GM(second) <= 0.999`, equivalent to at least a 0.1% reduction relative to the slower method. The 209 and 497 profiles constrain the ECTD win share to [74.5805796%, 74.6805796%], near the earlier 1,467/1,967 proportion. The 225 profile requires a majority instead. Family minimums are one win and one loss for 209/225, and ten of each for 497.

These are **outcome-selected exploratory cohorts**: the desired ranking was an explicit input to selection. The observed ordering and win fractions describe those selected cases; they are not estimates of general performance or results on an independent holdout. Several adjacent advantages are only about 0.1%, so “better” here describes a small measured aggregate difference, not established robustness or substantial superiority.

The earlier generator preserves internal workflow graph structure but resamples costs and records positive initializer additions or promotions where applicable. The family names therefore refer to synthetic derived workflows, separate from the original unmodified 2,094-instance benchmark. All 3,072 attempted synthetic inputs and all recorded results remain in this package, together with the saved alternative and infeasible selection attempts.

## 7. Validation and execution provenance

| Profile | Inputs replayed | Schedules checked | Invalid schedules | Mismatches |
| --- | --- | --- | --- | --- |
| full_order_209 | 209 | 2508 | 0 | 0 |
| latest_497 | 497 | 5964 | 0 | 0 |
| full_order_225 | 225 | 2700 | 0 | 0 |

The three replay runs checked **11,172 schedules**. The profiles contain 546 distinct input IDs in their union; repeated IDs across profiles are not additional independent instances. Every replay compared makespans, execution horizons, duplicate counts, duplicate work, and exact schedule fingerprints, and checked schedule feasibility. There were no changed executable source files during replay.

The build validates all 3,072 source input hashes, one-to-one input/result identities, all 36,864 retained algorithm/mode makespans against both source archives and the CSV, and the original validity flags. Separate independent audits recomputed the selected membership, classifications, means, margins, and source correspondences for all three profiles.

The inherited IPEFT native-source parity receipt covers 120 earlier checks and 11,822 task events with zero discrepancies. The native program supports append scheduling; insertion is the shared engine’s gap-placement sensitivity. That source-parity check was not rerun as a new experiment in this revision.

**Execution was local. No GitHub Actions run was performed or claimed.** Replay receipts record the runtime, inputs, source hashes, counts, and results. Source identity evidence is in `validation/source_integrity.json`; individual replay receipts are in `validation/replay-<profile>/run_metadata.json`.

## 8. Complete-pool comparison and family-level detail

| Algorithm | Full-pool append geometric makespan | Full-pool insertion geometric makespan |
| --- | --- | --- |
| ECTD | 495.153800 | 485.761766 |
| AEFT | 547.007605 | 534.570186 |
| BPPTS | 578.070245 | 557.541626 |
| HEFT | 577.401622 | 570.293559 |
| LSTD | 515.746185 | 509.531938 |
| IPEFT | 549.748906 | 541.918606 |

The complete-pool comparison keeps the attempted denominator visible. Family-level rankings below show why the pooled order must not be described as the order in every family. Within-family means use the same geometric-mean metric.

### full_order_209

| Family | Instances | Append order | Insertion order |
| --- | --- | --- | --- |
| FFT | 33 | ECTD > AEFT > HEFT > LSTD > IPEFT > BPPTS | ECTD > AEFT > HEFT > LSTD > IPEFT > BPPTS |
| GE | 54 | ECTD > AEFT > BPPTS > IPEFT > HEFT > LSTD | ECTD > AEFT > IPEFT > BPPTS > HEFT > LSTD |
| Genome | 51 | ECTD > AEFT > HEFT > LSTD > BPPTS > IPEFT | ECTD > AEFT > HEFT > BPPTS > LSTD > IPEFT |
| LA | 48 | ECTD > AEFT > LSTD > BPPTS > HEFT > IPEFT | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT |
| LIGO | 14 | ECTD > LSTD > HEFT > AEFT > IPEFT > BPPTS | ECTD > LSTD > AEFT > HEFT > BPPTS > IPEFT |
| Montage | 9 | ECTD > HEFT > LSTD > AEFT > IPEFT > BPPTS | ECTD > HEFT > LSTD > AEFT > IPEFT > BPPTS |

### latest_497

| Family | Instances | Append order | Insertion order |
| --- | --- | --- | --- |
| FFT | 61 | ECTD > AEFT > LSTD > BPPTS > HEFT > IPEFT | ECTD > AEFT > LSTD > BPPTS > IPEFT > HEFT |
| GE | 99 | ECTD > AEFT > BPPTS > IPEFT > LSTD > HEFT | ECTD > AEFT > BPPTS > IPEFT > LSTD > HEFT |
| Genome | 105 | ECTD > BPPTS > LSTD > AEFT > HEFT > IPEFT | ECTD > LSTD > BPPTS > AEFT > HEFT > IPEFT |
| LA | 132 | ECTD > AEFT > BPPTS > LSTD > IPEFT > HEFT | ECTD > AEFT > BPPTS > LSTD > IPEFT > HEFT |
| LIGO | 64 | ECTD > LSTD > BPPTS > AEFT > HEFT > IPEFT | ECTD > LSTD > BPPTS > AEFT > HEFT > IPEFT |
| Montage | 36 | ECTD > LSTD > AEFT > HEFT > BPPTS > IPEFT | ECTD > LSTD > AEFT > HEFT > IPEFT > BPPTS |

### full_order_225

| Family | Instances | Append order | Insertion order |
| --- | --- | --- | --- |
| FFT | 33 | ECTD > AEFT > HEFT > LSTD > IPEFT > BPPTS | ECTD > AEFT > HEFT > LSTD > IPEFT > BPPTS |
| GE | 57 | ECTD > AEFT > BPPTS > IPEFT > HEFT > LSTD | ECTD > AEFT > IPEFT > BPPTS > HEFT > LSTD |
| Genome | 62 | ECTD > HEFT > AEFT > LSTD > BPPTS > IPEFT | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT |
| LA | 47 | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT |
| LIGO | 14 | ECTD > LSTD > HEFT > AEFT > IPEFT > BPPTS | ECTD > AEFT > LSTD > HEFT > BPPTS > IPEFT |
| Montage | 12 | ECTD > HEFT > LSTD > AEFT > IPEFT > BPPTS | ECTD > HEFT > LSTD > AEFT > IPEFT > BPPTS |

## 9. Files and reproducibility

Each `cohorts/<profile>/` directory contains the original input records in `inputs.jsonl.gz`, `membership.csv`, the six-method source outcomes in `expected_results.jsonl.gz`, and an exact `summary.json`. Frozen membership lists, optimization constraints, solver receipts, bounds and independent audits are under `selection_evidence/`. The full attempted pool is under `source_evidence/`.

The builder reproduces frozen membership rather than depending on an optimizer to return the same equal-quality solution. Its inputs and outputs are fingerprinted. The original optimization script and a portable wrapper are also supplied for inspecting or repeating selection. See `README.md` for commands.

### Implication for the requested 1,467 + 500 study

These files make the feasible alternatives concrete, without treating a smaller set as the original 1,967-instance cohort. Retaining exactly 1,467 fixed winners plus 500 additional cases and obtaining the requested ordering would require a separately recorded search over newly generated and evaluated inputs. Existing saved candidates cannot deliver that combination, and new generation would not guarantee that it becomes feasible.
