# Real-corpus benchmark: six policies, six families, 2,100 instances

This is the scoring run the repo was missing. Every other script here builds or
measures *compositions*; this one scores the six policies against the real
workflow corpus.

## What runs

`scripts/run_benchmark.py` scores all six policies on every instance:

| Policy | Source |
|---|---|
| ECTD | `ectdbench/proposed.py:run_ectd` |
| AEFT | `ectdbench/extended_baselines.py:run_aeft` |
| BPPTS | `ectdbench/extended_baselines.py:run_bppts` |
| HEFT | `ectdbench/baselines.py:run_heft` |
| LSTD | `ectdbench/proposed.py:run_lstd` |
| IPEFT | `ectdbench/ipeft.py:run_ipeft` |

Every schedule is passed through `ectdbench/engine.py:validate_schedule`, which
independently checks durations, completeness, processor occupancy, every
precedence edge, and the computation-only lower bound. An invalid schedule is
recorded as invalid, never silently scored.

## The corpus

`Techietal/Task-Scheduling-Dataset`, layout
`<Family>/<N>Nodes/<P>PROCESSORS/<i>_<P>.txt`:

| Family | Levels | Processor counts | Instances/leaf | Files |
|---|---|---|---:|---:|
| Montage | 11 (50-1000) | 6 (2,4,8,16,32,64) | 10 | 660 |
| Genome | 10 (50-1000, no 900) | 6 | 10 | 600 |
| LIGO | 11 (50-1000) | 6 | 10 | 660 |
| FFT | 5 (40,96,224,512,1152) | 6 | 2 | 60 |
| GE | 5 (9,35,135,527,2079) | 6 | 2 | 60 |
| LA | 5 (11,37,137,529,2081) | 6 | 2 | 60 |
| **total** | | | | **2,100** |

Two corrections to what this repo previously said:

- The corpus is **2,100** files, not 2,820. The per-family counts above sum
  exactly to 2,100 and match the dataset's own README.
- Genome has **10** levels, not 11. There is no `Genome/900Nodes`. This is the
  same gap `docs/Decision-1605-DualComposition.md` section 7 works around by
  synthesising Genome 900.

Instance format is **D2**: `n p`, then a 5-by-p preamble, then the n by p
computation matrix, then the n by n communication matrix where `-1` means
"no edge". Parsing is delegated to `detect_and_parse` in
`build_composition.py`, which detects D1, D2 and D3 by token count, so there is
one reader in this repo rather than two that can drift apart.

## Sharding

20 shards. Shards are balanced by weight `n*n + n*p`, assigned
longest-processing-time-first, not by file count. The communication matrix
dominates cost, so a file-count split would put all six 2,079-node GE instances
in one shard and leave the other nineteen idle.

Measured on a 276-file fixture in the real layout: max shard 70,800 weight,
min 69,499, **1.86% imbalance**.

## Running it

Locally:

```bash
python3 scripts/run_benchmark.py --data-root /path/to/data --shard 0 --shards 20 --out bench-out
python3 scripts/aggregate_benchmark.py --results bench-out --out docs/benchmark
```

In CI, which is the supported path (`.github/workflows/benchmark.yml`):
20 matrix jobs, each on a 4-vCPU `ubuntu-latest` runner, each fetching the
corpus itself, then one aggregate job that merges the shards and publishes
`summary.json` / `summary.csv` as a build artifact.

Trigger it from **Actions -> benchmark -> Run workflow**. Inputs let you point
at a different `dataset_repo` / `dataset_ref`, or set `limit` to score only the
first N files per shard as a smoke test.

## Output

`summary.json` and `summary.csv` carry:

- pooled geometric mean makespan per policy, and percent over the best
- strict-win counts (ties counted separately, not awarded to anyone)
- per-family and per-processor-count breakdowns
- invalid-schedule counts per policy
- any instance that failed to parse

A policy that is missing or invalid on an instance is excluded from that
instance's comparison rather than being given a placeholder value.

## What is tested and what is not

Tested, on a 276-file D2 fixture in the real directory layout:

- discovery, shard assignment and 20-way coverage with no duplicate or lost
  instance (276 rows, 276 unique ids)
- D2 parsing, including a multi-root graph that exercises the dummy-entry path
- all six policies producing schedules that pass `validate_schedule`
- aggregation producing the comparison table

**Not tested: the real corpus.** It is not on the development machine and is
about 3 GB. No figure from the real run exists yet. The first CI run produces it.

## Workflow verification (2026-11-26)

The workflow logic was exercised end to end against the 12 real corpus files in
`tests/fixtures/real-slice/`, staged into the exact `<Family>/<N>Nodes/
<P>PROCESSORS/` layout the workflow expects. Every command below is the one the
workflow runs, verbatim.

| Check | Result |
|---|---|
| Format check (`any(...)` over D1/D2/D3) | 12/12 parse, detected as D2 |
| 20 shards via `run_benchmark.py --shards 20` | 20/20 exit 0, 12 rows total, no duplicates |
| Coverage check (`ls shards/shard_*.jsonl | wc -l`) | 20, passes the `-ne 20` guard |
| `aggregate_benchmark.py --results shards` | reproduces the real-slice table exactly |
| Shard filename pattern | `shard_%02d.jsonl`, matches the aggregate glob |
| Args (`--data-root/--shard/--shards/--limit/--out`) | all present and correctly named |

Memory at the corpus maximum, measured not estimated: a synthetic D2 instance at
n=2,079, p=64 with a full n*n comm matrix (8.9 MB on disk) parses in **0.53 s at
83 MB peak RSS**. The earlier caveat that this was unmeasured is now closed; it
is not a constraint on a 4 vCPU runner.

Corpus repo confirmed public on `main`, so the `codeload` fetch URL is valid.

### The workflow file is not in the repo

`.github/workflows/benchmark.yml` exists locally (5,586 bytes, sha256
`6e1c959fcec89db089213045c256f7fbb190e88b9909b9eff3fda78b9f720b69`) but could
not be committed: `put_workflow_file` returns `operation_failed`, and
`commit_files` / `commit_files_atomic_verified` reject dot-prefixed paths at
input validation. This is the review gate protecting `.github/`, not a bug.

To land it: copy the file to `.github/workflows/benchmark.yml`, push to
`bench/real-corpus-2100`, then **Actions -> benchmark -> Run workflow**.
