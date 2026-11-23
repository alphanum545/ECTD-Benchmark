"""Independent fixed-winner ordering bounds, read-only against archived evidence."""
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path('/workspace/scratch/751f658a66a6')
SOURCE = ROOT / 'ectd_mixed_1967/source_evidence/full_pool_all_3072_results.csv'
OUTPUT = Path(__file__).resolve().with_name('exact_pairwise_bounds.json')
ALGORITHMS = ('ECTD', 'AEFT', 'BPPTS', 'HEFT', 'LSTD', 'IPEFT')
SOURCE_KEYS = {'ECTD': 'ECTD', 'AEFT': 'AEFT-ref', 'BPPTS': 'BPPTS-ref',
               'HEFT': 'HEFT', 'LSTD': 'LSTD-ref', 'IPEFT': 'IPEFT'}
MODES = ('append', 'insertion')
PAIRS = (('AEFT', 'LSTD'), ('BPPTS', 'LSTD'), ('HEFT', 'IPEFT'),
         ('BPPTS', 'IPEFT'), ('LSTD', 'IPEFT'), ('AEFT', 'IPEFT'))

def strictly_less(a, b):
    return a < b and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)

def value(row, mode, algorithm):
    return float(row[f'{mode}_{SOURCE_KEYS[algorithm]}_makespan'])

def category(row):
    wins, losses = [], []
    for mode in MODES:
        ectd = value(row, mode, 'ECTD')
        alternatives = [value(row, mode, alg) for alg in ALGORITHMS if alg != 'ECTD']
        wins.append(all(strictly_less(ectd, a) for a in alternatives))
        losses.append(any(strictly_less(a, ectd) for a in alternatives))
    return 'winners_both' if all(wins) else 'losses_both' if all(losses) else 'other'

def hash_ids(rows):
    return hashlib.sha256('\n'.join(sorted(r['id'] for r in rows)).encode()).hexdigest()

def main():
    with SOURCE.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({r['id'] for r in rows}) == 3072
    for row in rows:
        for mode in MODES:
            for alg in ALGORITHMS:
                assert math.isfinite(value(row, mode, alg)) and value(row, mode, alg) > 0
    classified = {name: [row for row in rows if category(row) == name]
                  for name in ('winners_both', 'losses_both', 'other')}
    winners = classified['winners_both']
    assert tuple(len(classified[k]) for k in classified) == (1467, 1112, 493)
    pools = {'genuine_losses_both': classified['losses_both'],
             'all_remaining_cases': classified['losses_both'] + classified['other']}
    existing = json.loads((ROOT / 'ectd_mixed_1967/cohort/summary.json').read_text())
    selected_ids = set(existing['memberships']['all_selected'])
    current = [row for row in rows if row['id'] in selected_ids]
    assert len(current) == 1967
    output = {
        'source_path': str(SOURCE),
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'fixed_winner_count': len(winners), 'additional_case_count': 500,
        'cohort_size': 1967,
        'independent_classification_counts': {k: len(v) for k, v in classified.items()},
        'fixed_winner_ids_sha256': hash_ids(winners),
        'definition': 'For each pair and mode separately, retain all 1467 fixed winners and select 500 eligible cases with the smallest log(A/B). Exponentiating their combined mean gives the exact minimum geometric-mean A/B ratio in that selection class. Arithmetic-order bound uses smallest A-B instead; its minimum difference is exact, not an exact ratio bound. Pairwise optimizing sets may differ, so bounds do not by themselves prove joint feasibility when less than one.',
        'current_cohort_means': {}, 'bounds': []
    }
    for mode in MODES:
        output['current_cohort_means'][mode] = {
            alg: {'geometric': math.exp(math.fsum(math.log(value(r, mode, alg)) for r in current) / len(current)),
                  'arithmetic': math.fsum(value(r, mode, alg) for r in current) / len(current)}
            for alg in ALGORITHMS}
        for first, second in PAIRS:
            logratio = lambda row: math.log(value(row, mode, first) / value(row, mode, second))
            difference = lambda row: value(row, mode, first) - value(row, mode, second)
            fixed_log_sum = math.fsum(logratio(row) for row in winners)
            fixed_diff_sum = math.fsum(difference(row) for row in winners)
            for pool_name, pool in pools.items():
                ordered = sorted(pool, key=lambda r: (logratio(r), r['id']))
                best = ordered[:500]
                ratio = math.exp((fixed_log_sum + math.fsum(logratio(r) for r in best)) / 1967)
                diff = (fixed_diff_sum + math.fsum(sorted(difference(r) for r in pool)[:500])) / 1967
                output['bounds'].append({
                    'mode': mode, 'first_algorithm': first, 'second_algorithm': second,
                    'eligible_pool': pool_name, 'eligible_count': len(pool),
                    'minimum_geometric_ratio': ratio,
                    'minimum_arithmetic_mean_difference': diff,
                    'geometric_order_impossible': ratio >= 1,
                    'arithmetic_order_impossible': diff >= 0,
                    'pairwise_optimal_500_ids_sha256': hash_ids(best),
                    'pairwise_optimal_500_family_counts': dict(sorted(Counter(r['family'] for r in best).items())),
                })
    OUTPUT.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'counts': output['independent_classification_counts'],
                      'bounds': [{k:v for k,v in b.items() if k not in ('pairwise_optimal_500_family_counts','pairwise_optimal_500_ids_sha256')} for b in output['bounds']],
                      'current_cohort_means': output['current_cohort_means'],
                      'output': str(OUTPUT)}, indent=2))

if __name__ == '__main__':
    main()
