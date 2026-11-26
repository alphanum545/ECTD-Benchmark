# Builder — `build_composition.py`

Implements the build method in
[`../docs/Decision-1605-DualComposition.md`](../docs/Decision-1605-DualComposition.md)
§7. Builds both 1,845-instance compositions from the same 400-file base set.

## What it does

For each of the 240 lattice cells, resample the source cost matrix and score all
six policies. Keep a draw if it advances the cell's quota. Stop when the quota
fills.

```
comp[r][c] = source_comp[r][c % p_src] * lognormal(0, sigma)
comm[u][v] = source_comm[u][v] * scale        # -1 stays -1, always
```

| | Variant A — FORCE | Variant B — KNOB LADDER |
|---|---|---|
| Rungs | rung 1 only (σ=0.18, ×1) | all nine, escalating |
| Budget per cell | 24 candidates | 20 per rung, then escalate |
| Short cell | recorded as a waiver | should not happen |

Quotas: Set 1 cells need 7 winners + 1 added, Set 2 cells 6 + 1.
165×8 + 75×7 = **1,845**.

## Run it

```bash
python3 scripts/build_composition.py --self-check          # arithmetic + format invariants
python3 scripts/build_composition.py --variant both        # the real build
python3 scripts/build_composition.py --variant B --limit-cells 8   # smoke test
python3 scripts/verify_composition.py compositions/variant_B       # gate
```

Output goes to `compositions/variant_A/` and `compositions/variant_B/`, each with
`manifest.json` and an `instances/` tree mirroring the source layout.

## Why Variant A's budget is 24

"Dead" is defined in the record as **0 ECTD wins in 24 measured candidates**.
A cell that cannot fill in 24 draws is dead by exactly the rule the dead-cell
inventory was built on. Using a larger budget would make A fill cells the
inventory calls dead, and the waiver list would stop meaning anything.

## What the manifest records

Per instance: `rung`, `sigma`, `comm_scale`, `candidate`, `makespan`,
`margin_pct`, `drift`, `neg_entries`, and the exact `source` file it came from.

Per cell: quota, filled, `met`, `waived`, `rung_used`, `rung_hist`, candidates.

Top level: delivered/winners/added/waived, `realised_ratio` overall and per set
and per family, `rung_usage`, `escalated_instances`,
`cells_outside_source_regime`.

`realised_ratio` is computed from what was actually built. It is never asserted
from the target.

## Two things this deliberately does not claim

**The rung distribution will not match §4.2's table.** The probe used its own
seed strings; this builder uses `build|<cell>|<variant>|<rung>|<cand>`. The
probe's job was to show the ladder *can* fill every dead cell. The builder's job
is to record what the build *did*. Both belong in the record, and the builder
does not tune its seeds to reproduce the probe.

**A short cell is never backfilled.** If A cannot fill a cell, the manifest says
so and reports the shortfall. The realised ratio is then whatever it is.

## Source resolution

One source DAG per level, evaluated at all five p values — the same choice
`measure_cell_rates.py` makes, which is what makes the measured dead-cell
inventory apply to this build. The source comp matrix has its own column count
and is tiled to the target p by `c % ps`; the comm matrix and its `-1` pattern
belong to the DAG and do not depend on p.

Picking a different source per p would silently break the correspondence with
the measurements. Don't.

`ECTD_DATA_ROOT` overrides corpus discovery when the data is not in either of
the two conventional locations.

## Scale

Measured on the 90-cell synthetic fixture, 8 workers: Variant A 26 s, Variant B
41 s. The real 240-cell build is larger instances (up to 2,079 nodes) and is
estimated at a few minutes; the record's §7 figure of ~3 min single-core was for
a smaller mean n. Treat the real timing as unmeasured until the real run.
