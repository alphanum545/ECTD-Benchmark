# ECTD exploratory ranking revision

This package contains three separate outcome-selected cohorts, all replayed with
the exact existing ECTD, AEFT, BPPTS, HEFT, LSTD and IPEFT implementations.
Read `RESULTS.md` for the measured results, the count trade-offs, the exact
1,967-case impossibility bound, and interpretation.

| Profile | Instances | Strict ECTD wins / genuine losses in both modes | Aggregate order, best to worst |
| --- | --- | --- | --- |
| full_order_209 | 209 | 156 / 53 | ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT |
| latest_497 | 497 | 371 / 126 | ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT |
| full_order_225 | 225 | 134 / 91 | ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT |

All six workflow families are represented, with both ECTD wins and losses in
each. The order refers to pooled geometric mean makespan in both append and
insertion modes; it is not asserted for every instance or every family.
The 209 candidate is feasible but not proved maximum. Optimality reported for
497 and 225 is limited to the constraints in their selection receipts.

These are smaller alternatives. They do not retain all 1,467 earlier winners
and do not replace the completed 1,967-instance study. Selection explicitly
uses observed algorithm outcomes; the results describe selected synthetic
cases, not an independent performance sample.

## Reproduce the frozen cohorts

Use Python 3.12 and the pinned dependency:

```bash
python -m pip install -r requirements.txt
python -m rankstudy.build --output cohorts-reproduction
```

The build refuses to overwrite existing output. It validates the entire source
pool, source/result identities, all retained makespans, frozen membership and
classifications, declared margins, and byte-for-byte input export. All needed
source data is included; no network data download is needed.

## Replay one cohort

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python -m rankstudy.replay --profile full_order_209 \
  --output validation/replay-full_order_209-reproduction --workers 6
```

Use `latest_497` or `full_order_225` for another profile, with a fresh output
directory. Replay validates schedules and compares makespan, execution horizon,
duplicate count/work and complete schedule fingerprint to the archived source
outcome. Receipts record local execution; no GitHub Actions run is claimed.

## Inspect the optimization

`selection_evidence/` contains the frozen original optimizer, its runtime and
solver receipt, all saved selection attempts, exact finite-pool bounds,
membership lists, and independent audits. `rankstudy/optimize.py` provides a
portable copy that reads the bundled source CSV. The environment variables
`ECTD_SELECTION_OUTPUT` and `ECTD_SELECTION_SOURCE` select a new output directory
and an optional source CSV. The optional optimizer dependency is pinned in
`requirements-optimizer.txt`. For example:

```bash
ECTD_SELECTION_OUTPUT=optimizer-reproduction-209 \
python -m rankstudy.optimize full_order_original_fraction_minone \
  --min-each 1 --time-limit 40
```

Repeating optimization can produce a different equal-cardinality solution.
The supplied frozen IDs identify the exact cohorts whose schedules were checked.
The 0.1% adjacent margin is a selection rule, not a statistical confidence bound.

## Package structure

- `cohorts/<profile>/`: exact inputs, membership, expected outcomes and summary.
- `source_evidence/`: all 3,072 generated candidates and original results,
  additional IPEFT outcomes, full-pool CSV and pinned native IPEFT source.
- `selection_evidence/`: selection attempts, constraints, solver metadata,
  bounds, membership fingerprints and independent source audits.
- `ectdbench/`: unchanged algorithm implementations and scheduling engine.
- `rankstudy/`: build, replay, evidence-validation and optimization utilities.
- `validation/`: source identity, inherited native IPEFT parity and full replays.

Input provenance records resampled costs and initializer modifications from the
earlier synthetic generator. These derived workflow cases remain separate from
the original unmodified 2,094-instance benchmark. The complete attempted source
pool is retained so selected findings can be interpreted with their denominator.

## Independent clean reproduction

A separate clean working copy rebuilt all three cohorts from the bundled source
pool. All 18 regenerated profile files were byte-identical to the frozen
exports. Fresh replays checked 11,172 schedules with zero invalid schedules and
zero mismatches; the replay archives also matched byte-for-byte. The receipt is
`validation/clean_reproduction.json`. This verification was local.
