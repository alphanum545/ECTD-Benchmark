"""Build the human-readable report from frozen cohort summaries and receipts."""
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('full_order_209', 'latest_497', 'full_order_225')
METHODS = ('ECTD', 'AEFT', 'BPPTS', 'HEFT', 'LSTD', 'IPEFT')
MODES = ('append', 'insertion')
FAMILIES = ('FFT', 'GE', 'Genome', 'LA', 'LIGO', 'Montage')
SUMMARY = {p: json.loads((ROOT / 'cohorts' / p / 'summary.json').read_text()) for p in PROFILES}
REPLAY = {p: json.loads((ROOT / 'validation' / ('replay-' + p) / 'run_metadata.json').read_text()) for p in PROFILES}
for p in PROFILES:
    assert REPLAY[p]['passed']
    assert REPLAY[p]['checked_schedules'] == 12 * SUMMARY[p]['selected']['instances']
    assert REPLAY[p]['invalid_schedules'] == REPLAY[p]['mismatched_schedules'] == 0
    assert not REPLAY[p]['changed_source_files']

def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(str(v) for v in r) + ' |' for r in rows])

def order(p, mode='append'):
    return ' > '.join(SUMMARY[p]['selected']['placements'][mode]['ranking_lowest_makespan_first'])

def means(p):
    s = SUMMARY[p]['selected']['placements']
    methods = s['append']['ranking_lowest_makespan_first']
    return table(['Algorithm', 'Append geometric makespan', 'Insertion geometric makespan'],
                 [[m] + [f'{s[mode]["geometric_makespans"][m]:.6f}' for mode in MODES] for m in methods])

def families(p):
    return table(['Family', 'Strict ECTD wins', 'Genuine ECTD losses', 'Total'],
                 [[f, SUMMARY[p]['families'][f]['wins'], SUMMARY[p]['families'][f]['losses'],
                   SUMMARY[p]['families'][f]['total']] for f in FAMILIES])

def wins(p):
    s = SUMMARY[p]['selected']['placements']
    return table(['Sole winner', 'Append instances', 'Insertion instances'],
                 [[m] + [s[mode]['sole_winners'][m] for mode in MODES] for m in METHODS] +
                 [['Tied best among competitors'] + [s[mode]['tied_best_instances'] for mode in MODES]])

source_csv = ROOT / 'source_evidence/full_pool_all_3072_results.csv'
with source_csv.open(newline='') as stream:
    raw = list(csv.DictReader(stream))
alias = {m: m + ('-ref' if m in ('AEFT', 'BPPTS', 'LSTD') else '') for m in METHODS}
values = {r['id']: {mode: {m: float(r[f'{mode}_{alias[m]}_makespan']) for m in METHODS} for mode in MODES} for r in raw}
def strict(a, b):
    return a < b and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)
fixed = [i for i, v in values.items() if all(all(strict(v[k]['ECTD'], v[k][m]) for m in METHODS if m != 'ECTD') for k in MODES)]
losses = [i for i, v in values.items() if all(any(strict(v[k][m], v[k]['ECTD']) for m in METHODS if m != 'ECTD') for k in MODES)]
assert len(fixed) == 1467 and len(losses) == 1112 and len(raw) == 3072
bounds = []
for mode in MODES:
    ds = sorted(math.log(v[mode]['BPPTS'] / v[mode]['LSTD']) for v in values.values())
    bounds.append([mode, f'{math.exp(math.fsum(ds[:1967]) / 1967):.9f}'])
fixed_bounds = []
for first, second in [('AEFT', 'LSTD'), ('BPPTS', 'LSTD'), ('HEFT', 'IPEFT')]:
    row = [first + ' / ' + second]
    for mode in MODES:
        d = lambda i: math.log(values[i][mode][first] / values[i][mode][second])
        row.append(f'{math.exp((math.fsum(d(i) for i in fixed) + math.fsum(sorted(d(i) for i in losses)[:500])) / 1967):.9f}')
    fixed_bounds.append(row)

overview = []
all_ids = set()
for p in PROFILES:
    s = SUMMARY[p]
    n = s['selected']['instances']
    w = s['retained_original_winners']
    overview.append([p, n, w, n - w, f'{100 * w / n:.2f}%', order(p)])
    with (ROOT / 'cohorts' / p / 'membership.csv').open(newline='') as stream:
        all_ids.update(r['id'] for r in csv.DictReader(stream))

parts = [
    '# ECTD ranking revision: verified exploratory alternatives',
    '**The requested aggregate ordering is achievable on smaller selected cohorts. It is not achievable on any 1,967 distinct instances from the saved 3,072-instance pool.** The original 1,467-winner + 500-loss cohort remains a separate completed study. None of the alternatives below preserves that composition.',
    'The closest match to both the full earlier order and the earlier approximately 75% ECTD win share is the **209-instance candidate: 156 strict ECTD wins and 53 genuine losses**. It has **ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in both placement modes. The 497-instance candidate offers more cases and meets the latest three explicit relationships, while placing LSTD before HEFT. All three alternatives have been fully replayed locally.',
    'Here, “better” and `>` mean a lower **pooled geometric mean makespan** on the identical selected cases. They do not mean the same ordering on every instance or within every workflow family. Makespans are synthetic cost units.',
    '## 1. Concrete choices and the count trade-off',
    table(['Profile', 'Instances', 'ECTD wins', 'ECTD losses', 'ECTD win share', 'Pooled order in both modes'], overview),
    'Each profile contains all six workflow families and both ECTD wins and genuine losses within each family. The profiles overlap; they are alternative selections, not three independent experiments to combine. The 209 profile omits 1,311 of the original 1,467 winners; the 497 profile omits 1,096; the 225 profile omits 1,333.',
    '## 2. Full earlier order, approximately 75% ECTD wins: 209 cases',
    '**ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in append and insertion. ECTD is the strict sole winner on 156 cases and is beaten on 53 cases in each mode, with zero ECTD tied-best cases. Every competing algorithm wins some individual cases.',
    means('full_order_209'),
    '### Composition across workflow families',
    families('full_order_209'),
    'Family representation is uneven: Montage has nine cases, including only one ECTD loss. This is a pooled comparison with each instance equally weighted in log space; it is not a family-balanced comparison.',
    '### Individual winners',
    wins('full_order_209'),
    'The tied-best rows involve competing methods; ECTD loses those cases. Thus this is a mixed set, with genuine successes for each other algorithm, despite ECTD winning approximately three quarters of the selected instances.',
    '### Size qualification',
    'This is a verified feasible 209-case solution. The solver reached its 40-second time limit; its upper bound was 212 and its reported gap was 1.4354%. **209 is not proved to be the largest feasible count.** No solver-optimality claim is needed to verify the actual selected results.',
    '## 3. Larger set meeting the latest explicit relationships: 497 cases',
    '**ECTD > AEFT > BPPTS > LSTD > HEFT > IPEFT** in both modes. This makes AEFT and BPPTS better than LSTD and places IPEFT last. It changes the earlier relative positions of HEFT and LSTD.',
    means('latest_497'),
    families('latest_497'),
    'ECTD has 371 strict wins and 126 genuine losses in each mode, or 74.6479% wins. Each family contains at least ten wins and ten losses. HiGHS reported 497 as the maximum only under the stated revised chain, the narrow win-share interval, the minimum family counts, and the 0.1% adjacent-margin constraint. It is not an unrestricted maximum over arbitrary sampling designs.',
    '## 4. Full earlier order with a smaller ECTD win share: 225 cases',
    '**ECTD > AEFT > BPPTS > HEFT > LSTD > IPEFT** in both modes, with 134 strict wins and 91 losses: 59.5556% ECTD wins. HiGHS reported this size as optimal under the saved full-chain, majority-win, minimum-one-win-and-loss-per-family, and 0.1%-margin constraints. The exact majority constraint is wins minus losses at least two.',
    means('full_order_225'),
    families('full_order_225'),
    'This profile provides 16 more cases than the 209 profile while moving the win/loss mixture farther from the earlier roughly 75/25 composition.',
    '## 5. Why changing the 500 additions cannot fix the 1,967-case set',
    'For any pair A and B, define `d_i = log(makespan_A_i / makespan_B_i)`. The geometric mean ratio on a subset S is `exp(sum(d_i for i in S) / len(S))`. Therefore, the smallest possible ratio on any fixed-size subset is obtained by taking the smallest corresponding log ratios. This computes an exact finite-pool bound; it does not rely on a heuristic optimizer.',
    'Even allowing **any 1,967 distinct cases** from all 3,072 candidates, removing all ECTD-win and workflow-family requirements, the best possible BPPTS/LSTD ratios are:',
    table(['Mode', 'Lowest possible BPPTS / LSTD ratio on any 1,967 cases'], bounds),
    'Both ratios exceed one. Hence BPPTS remains slower than LSTD even under its individually most favorable 1,967-case selection in either mode. A selection satisfying all the requested relationships is therefore impossible at that size within this saved pool.',
    'Keeping the specific 1,467 winners and adding any 500 of the 1,112 genuine losses gives even stronger blockers:',
    table(['Required comparison', 'Best possible append ratio', 'Best possible insertion ratio'], fixed_bounds),
    'Each row and mode is optimized separately, so these bounds are deliberately optimistic. Ratios above one disprove the desired relation; a ratio below one alone would not establish simultaneous feasibility. The source-level analysis also permits mixed/tied additions and checks arithmetic mean differences; those relaxations do not remove the main blockers. Detailed receipts are in `selection_evidence/exact_pairwise_bounds.json` and `selection_evidence/unrestricted_1967_impossibility.json`.',
    '## 6. Selection protocol and interpretation',
    'Only the membership changes. Every exported DAG line is copied byte-for-byte from the earlier candidate archive. The exact algorithm implementations and common scheduling engine are the same as in the completed 1,967-case study. Standard algorithm names are used in new outputs; legacy archive keys are retained solely for source traceability.',
    'The attempted source pool has 3,072 synthetic cases: 1,467 strict ECTD winners in both modes, 1,112 genuine ECTD losses in both modes, and 493 mixed or tied cases. The new optimizations select from the first two groups. “Strict win” means ECTD has a smaller makespan than all five comparators. “Genuine loss” means at least one comparator has a smaller makespan. Comparisons use relative tolerance 1e-12 and absolute tolerance 1e-9.',
    'Selection maximizes the count subject to the recorded ordering and composition constraints. For each adjacent pair, the aggregate requirement is `GM(first) / GM(second) <= 0.999`, equivalent to at least a 0.1% reduction relative to the slower method. The 209 and 497 profiles constrain the ECTD win share to [74.5805796%, 74.6805796%], near the earlier 1,467/1,967 proportion. The 225 profile requires a majority instead. Family minimums are one win and one loss for 209/225, and ten of each for 497.',
    'These are **outcome-selected exploratory cohorts**: the desired ranking was an explicit input to selection. The observed ordering and win fractions describe those selected cases; they are not estimates of general performance or results on an independent holdout. Several adjacent advantages are only about 0.1%, so “better” here describes a small measured aggregate difference, not established robustness or substantial superiority.',
    'The earlier generator preserves internal workflow graph structure but resamples costs and records positive initializer additions or promotions where applicable. The family names therefore refer to synthetic derived workflows, separate from the original unmodified 2,094-instance benchmark. All 3,072 attempted synthetic inputs and all recorded results remain in this package, together with the saved alternative and infeasible selection attempts.',
    '## 7. Validation and execution provenance',
    table(['Profile', 'Inputs replayed', 'Schedules checked', 'Invalid schedules', 'Mismatches'],
          [[p, REPLAY[p]['input_count'], REPLAY[p]['checked_schedules'], REPLAY[p]['invalid_schedules'], REPLAY[p]['mismatched_schedules']] for p in PROFILES]),
    f'The three replay runs checked **{sum(REPLAY[p]["checked_schedules"] for p in PROFILES):,} schedules**. The profiles contain {len(all_ids)} distinct input IDs in their union; repeated IDs across profiles are not additional independent instances. Every replay compared makespans, execution horizons, duplicate counts, duplicate work, and exact schedule fingerprints, and checked schedule feasibility. There were no changed executable source files during replay.',
    'The build validates all 3,072 source input hashes, one-to-one input/result identities, all 36,864 retained algorithm/mode makespans against both source archives and the CSV, and the original validity flags. Separate independent audits recomputed the selected membership, classifications, means, margins, and source correspondences for all three profiles.',
    'The inherited IPEFT native-source parity receipt covers 120 earlier checks and 11,822 task events with zero discrepancies. The native program supports append scheduling; insertion is the shared engine’s gap-placement sensitivity. That source-parity check was not rerun as a new experiment in this revision.',
    '**Execution was local. No GitHub Actions run was performed or claimed.** Replay receipts record the runtime, inputs, source hashes, counts, and results. Source identity evidence is in `validation/source_integrity.json`; individual replay receipts are in `validation/replay-<profile>/run_metadata.json`.',
    '## 8. Complete-pool comparison and family-level detail',
]

full = json.loads((ROOT / 'cohorts/build_summary.json').read_text())['full_pool']
parts.append(table(['Algorithm', 'Full-pool append geometric makespan', 'Full-pool insertion geometric makespan'],
                   [[m] + [f'{full["placements"][mode]["geometric_makespans"][m]:.6f}' for mode in MODES] for m in METHODS]))
parts.append('The complete-pool comparison keeps the attempted denominator visible. Family-level rankings below show why the pooled order must not be described as the order in every family. Within-family means use the same geometric-mean metric.')
for p in PROFILES:
    with (ROOT / 'cohorts' / p / 'membership.csv').open(newline='') as stream:
        members = list(csv.DictReader(stream))
    rows = []
    for f in FAMILIES:
        identifiers = [r['id'] for r in members if r['family'] == f]
        ranking = []
        for mode in MODES:
            gm = {m: math.exp(math.fsum(math.log(values[i][mode][m]) for i in identifiers) / len(identifiers)) for m in METHODS}
            ranking.append(' > '.join(sorted(METHODS, key=lambda m: gm[m])))
        rows.append([f, len(identifiers)] + ranking)
    parts += ['### ' + p, table(['Family', 'Instances', 'Append order', 'Insertion order'], rows)]
parts += [
    '## 9. Files and reproducibility',
    'Each `cohorts/<profile>/` directory contains the original input records in `inputs.jsonl.gz`, `membership.csv`, the six-method source outcomes in `expected_results.jsonl.gz`, and an exact `summary.json`. Frozen membership lists, optimization constraints, solver receipts, bounds and independent audits are under `selection_evidence/`. The full attempted pool is under `source_evidence/`.',
    'The builder reproduces frozen membership rather than depending on an optimizer to return the same equal-quality solution. Its inputs and outputs are fingerprinted. The original optimization script and a portable wrapper are also supplied for inspecting or repeating selection. See `README.md` for commands.',
    '### Implication for the requested 1,467 + 500 study',
    'These files make the feasible alternatives concrete, without treating a smaller set as the original 1,967-instance cohort. Retaining exactly 1,467 fixed winners plus 500 additional cases and obtaining the requested ordering would require a separately recorded search over newly generated and evaluated inputs. Existing saved candidates cannot deliver that combination, and new generation would not guarantee that it becomes feasible.'
]
(ROOT / 'RESULTS.md').write_text('\n\n'.join(parts) + '\n')

readme = '''# ECTD exploratory ranking revision

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
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \\
python -m rankstudy.replay --profile full_order_209 \\
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
ECTD_SELECTION_OUTPUT=optimizer-reproduction-209 \\
python -m rankstudy.optimize full_order_original_fraction_minone \\
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
'''
(ROOT / 'README.md').write_text(readme)
print(json.dumps({'report_bytes': (ROOT / 'RESULTS.md').stat().st_size,
                  'readme_bytes': (ROOT / 'README.md').stat().st_size,
                  'profile_union_inputs': len(all_ids),
                  'total_schedule_evaluations': sum(REPLAY[p]['checked_schedules'] for p in PROFILES)}))
