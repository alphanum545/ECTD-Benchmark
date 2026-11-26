# Measurement scripts — workspace layout requirement

These scripts produced the numbers behind
[`../docs/Decision-1605-DualComposition.md`](../docs/Decision-1605-DualComposition.md).
They are kept here so the measurements can be reproduced and re-run. The four
measurement scripts need the source corpus; `genome900.py` and the builder run
without it.

## Where the data has to be

Every script resolves paths through `scripts/_paths.py`, which searches the
plausible locations instead of assuming one. It looks for:

| What | Where it looks, in order |
|---|---|
| the `ectdbench` package | the repo root, then `<parent>/ECTD-Benchmark`, then `scripts/` |
| the corpus | `$ECTD_DATA_ROOT`, then `<parent>/scheduling-benchmark/data`, then `<repo>/scheduling-benchmark/data` |

and then reads:

| Path | What it is |
|---|---|
| `<data>/<Family>/<N>Nodes/<P>PROCESSORS/*.txt` | 2,820 real source instances |
| `<data>` sibling `ectd-real/ectd_selected_400.csv` | the 400-row base set (provenance only — no script reads it) |
| `<repo>/ectdbench` | the six policies |

So the expected layout is:

```
<workspace>/
├── ECTD-Benchmark/          <- this repo
│   ├── ectdbench/           <- policies (imported by every script)
│   └── scripts/             <- these measurement scripts
├── ectd-real/
│   └── ectd_selected_400.csv
└── scheduling-benchmark/
    └── data/                <- 2,820 source .txt files, ~3.1 GB
```

**A fresh clone of this repo alone will not run them.** The source data is not in
this repo. If you are resuming on a cloud machine, either bring those directories
across or set `ECTD_DATA_ROOT` to wherever the corpus lives.

> **Corpus precedence.** `make_synth_sources.py` writes a 90-file synthetic
> fixture to `<repo>/scheduling-benchmark/data`. If the real corpus is also
> present at `<workspace>/scheduling-benchmark/data`, the real one wins, because
> `_paths.py` checks the parent before the local fixture. Building a 1,845-instance
> composition from the fixture would produce numbers that mean nothing, so the
> order matters. `ECTD_DATA_ROOT` overrides both.

> **The 400-row set is provenance, not input.** No script opens
> `ectd_selected_400.csv`. Its load-bearing role is the 349/51 = 6.8431:1 ratio
> that anchors the 1,845 lattice (§2). You do not need it to build; you need it
> to defend the ratio.

## What each script does

| Script | Purpose | Output |
|---|---|---|
| `measure_cell_rates.py` | ECTD win rate per (family, level, p) across 235 cells, 2 sources × 12 seeds | `../docs/measurements/cell_rates.json` |
| `probe_ladder.py` | Tests ladder rungs 1–4 on the 104 dead cells | `../docs/measurements/ladder_probe.json` |
| `probe_ladder2.py` | Tests rungs 5–8 on the 27 cells that survived the first pass | `../docs/measurements/ladder_probe2.json` |
| `compare_search.py` | Escalating ladder (σ=1.0, ×64) vs free random search: candidates needed and drift from source | `../docs/measurements/search_compare.json` |
| `genome900.py` | Reconstructs the Genome 900 source DAG (§7) and asserts n=901, 2,729 edges, CCR 0.51 | `compositions/_sources/` |
| `_paths.py` | Shared path resolution; not run directly | — |

## Reproducing the headline numbers

```bash
# 1. win rates per cell (~60 s on 8 workers)
python3 scripts/measure_cell_rates.py

# 2. ladder coverage on dead cells (~90 s)
python3 scripts/probe_ladder.py
python3 scripts/probe_ladder2.py

# 3. ladder vs free search (~2 min)
python3 scripts/compare_search.py
```

All four are deterministic: fixed seeds, so re-running reproduces the committed
JSON exactly.

## Results the committed JSON records

**Cell win rates** — 235 cells, 5,640 candidates. Live cells by processor count:

| p | Live cells |
|---|---:|
| 4 | 13/47 |
| 8 | 15/47 |
| 16 | 25/47 |
| 32 | 35/47 |
| 64 | 43/47 |

**Ladder coverage** — all 104 dead cells fill. Only 6 fill at the baseline rung;
27 need ×16 or beyond.

| Rung | σ | comm_scale | Cells filled | Artifact |
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

> **Note on rung 9.** `probe_ladder2.py` stops at ×32, so it records the three
> cells rung 9 fills as `wins=0, cand=0` — never filled *within the rungs it
> tested*. Rung 9's evidence is in `compare_search.json`, whose ladder arm is
> hardcoded to σ=1.0 / ×64. Rungs 1–8 fill 101 cells; their residue is exactly
> the 3 that rung 9 fills. See `../measurements/VERIFICATION.md` §2.

**Ladder vs free search** — ladder fills 5/5 test cells at drift 0.65–0.68;
free search fills 3/5 at drift 1.74–1.79.
