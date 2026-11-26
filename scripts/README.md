# Measurement scripts — workspace layout requirement

These four scripts produced the numbers behind
[`../Decision-1605-DualComposition.md`](../Decision-1605-DualComposition.md).
They are kept here so the measurements can be reproduced and re-run, not because
they run standalone from this repo.

## They need the parent workspace

Every script resolves paths one level **above** this repo:

```python
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # <- the parent workspace, not this repo
```

and then reads:

| Path | What it is |
|---|---|
| `<ROOT>/scheduling-benchmark/data/<Family>/<N>Nodes/<P>PROCESSORS/*.txt` | 2,820 real source instances |
| `<ROOT>/ectd-real/ectd_selected_400.csv` | the 400-row base set |
| `<ROOT>/ECTD-Benchmark/ectdbench` | the six policies |

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

**A fresh clone of this repo alone will not run them.** The source data and the
400-row base set are not in this repo. If you are resuming on a cloud machine,
either bring those three directories across or point `ROOT` at wherever they live.

## What each script does

| Script | Purpose | Output |
|---|---|---|
| `measure_cell_rates.py` | ECTD win rate per (family, level, p) across 235 cells, 2 sources × 12 seeds | `../docs/measurements/cell_rates.json` |
| `probe_ladder.py` | Tests the first 4 ladder rungs on the 104 dead cells | `../docs/measurements/ladder_probe.json` |
| `probe_ladder2.py` | Tests 4 further rungs on the 27 cells that survived the first pass | `../docs/measurements/ladder_probe2.json` |
| `compare_search.py` | Escalating ladder vs free random search: candidates needed and drift from source | `../docs/measurements/search_compare.json` |

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

**Ladder coverage** — all 104 dead cells fill, but only 6 at the baseline rung:

| Rung | σ | comm_scale | Cells filled |
|---:|---:|---:|---:|
| 1 | 0.18 | ×1 | 6 |
| 2 | 0.35 | ×4 | 47 |
| 3 | 0.6 | ×4 | 9 |
| 4 | 0.6 | ×8 | 15 |
| 5 | 0.6 | ×16 | 15 |
| 6 | 1.0 | ×8 | 0 |
| 7 | 1.0 | ×16 | 1 |
| 8 | 1.0 | ×32 | 8 |
| 9 | 1.0 | ×64 | 3 |

**Ladder vs free search** — ladder fills 5/5 test cells at drift 0.65–0.68;
free search fills 3/5 at drift 1.74–1.79.
