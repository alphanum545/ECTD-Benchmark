"""Audit saved full-order alternatives against immutable sources, without solving."""
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path('/workspace/scratch/751f658a66a6')
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'ectd_mixed_1967/source_evidence'
ALGOS = ('ECTD', 'AEFT', 'BPPTS', 'HEFT', 'LSTD', 'IPEFT')
ALIASES = {'ECTD': 'ECTD', 'AEFT': 'AEFT-ref', 'BPPTS': 'BPPTS-ref',
           'LSTD': 'LSTD-ref', 'HEFT': 'HEFT', 'IPEFT': 'IPEFT'}
MODES = ('append', 'insertion')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def strictly_less(a,b): return a < b and not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
def read_csv(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def read_gzip(path):
    with gzip.open(path,'rt') as f:return {r['id']:r for r in map(json.loads,f)}
def value(r,mode,alg): return float(r[f'{mode}_{ALIASES[alg]}_makespan'])
def classify(r):
    win,loss=[],[]
    for mode in MODES:
        e=value(r,mode,'ECTD');others=[value(r,mode,a) for a in ALGOS[1:]]
        win.append(all(strictly_less(e,a) for a in others))
        loss.append(any(strictly_less(a,e) for a in others))
    return 'ectd_strict_both' if all(win) else 'ectd_loss_both' if all(loss) else 'other'

def audit(name,count,wins,losses,index,source_hashes,original,ipeft,frozen):
    checks=[]
    def check(label,condition):
        checks.append({'check':label,'passed':bool(condition)})
        if not condition:raise AssertionError(label)
    selected_ids=json.loads((HERE/f'{name}_ids.json').read_text())
    claimed=json.loads((HERE/f'{name}_analysis.json').read_text())
    membership=read_csv(HERE/f'{name}_membership.csv')
    check(f'{count} distinct instance IDs',len(selected_ids)==len(set(selected_ids))==count)
    check('All instance IDs present in original source',set(selected_ids)<=set(index))
    selected=[index[i] for i in selected_ids]
    check(f'{count} distinct input hashes',len({r['input_sha256'] for r in selected})==count)
    groups=Counter(classify(r) for r in selected)
    check('Expected strict both-mode win/loss composition',dict(groups)=={'ectd_strict_both':wins,'ectd_loss_both':losses})
    check('CSV source hash matches selector receipt',source_hashes['full_pool_all_3072_results.csv']==claimed['source_sha256'])
    check('All source archive hashes match frozen study',all(source_hashes[k]==frozen['source_files_sha256'][k] for k in source_hashes))
    idhash=hashlib.sha256('\n'.join(sorted(selected_ids)).encode()).hexdigest()
    check('Membership hash matches selector receipt',idhash==claimed['selection']['ids_sha256'])
    check('Membership CSV matches selected IDs',len(membership)==len({r['id'] for r in membership})==count and {r['id'] for r in membership}==set(selected_ids))
    check('Membership family/group/input hash agrees with source',all(r['family']==index[r['id']]['family'] and r['group']==classify(index[r['id']]) and r['input_sha256']==index[r['id']]['input_sha256'] for r in membership))
    families={f:{'wins':sum(r['family']==f and classify(r)=='ectd_strict_both' for r in selected),
                 'losses':sum(r['family']==f and classify(r)=='ectd_loss_both' for r in selected),
                 'total':sum(r['family']==f for r in selected)} for f in sorted({r['family'] for r in index.values()})}
    check('Six families with at least one win and one loss each',len(families)==6 and all(v['wins']>=1 and v['losses']>=1 for v in families.values()))
    check('Family counts match selector receipt',families==claimed['selection']['families'])
    wf=wins/count;fraction_range=claimed['constraints']['winner_fraction_range']
    check('ECTD wins strict majority',wf>0.5)
    if fraction_range:
        check('Winner fraction falls within declared interval',fraction_range[0]<=wf<=fraction_range[1])
    placements={}
    for mode in MODES:
        means={a:math.exp(math.fsum(math.log(value(r,mode,a)) for r in selected)/count) for a in ALGOS}
        order=sorted(ALGOS,key=means.get)
        margins={f'{a}<{b}':100*(1-means[a]/means[b]) for a,b in zip(ALGOS,ALGOS[1:])}
        check(f'{mode}: full requested aggregate order',order==list(ALGOS))
        check(f'{mode}: adjacent improvements at least 0.1 percent',all(v>=0.1 for v in margins.values()))
        check(f'{mode}: means match selector receipt',all(math.isclose(means[a],claimed['selection']['placements'][mode]['geomeans'][a],rel_tol=1e-12,abs_tol=1e-9) for a in ALGOS))
        check(f'{mode}: margins match selector receipt',all(math.isclose(v,claimed['selection']['placements'][mode]['margins_percent'][p],rel_tol=1e-10,abs_tol=1e-9) for p,v in margins.items()))
        sole=Counter({a:0 for a in ALGOS});tied=0
        for r in selected:
            vals={a:value(r,mode,a) for a in ALGOS};best=min(vals.values())
            leaders=[a for a in ALGOS if math.isclose(vals[a],best,rel_tol=1e-12,abs_tol=1e-9)]
            if len(leaders)==1:sole[leaders[0]]+=1
            else:tied+=1
        placements[mode]={'geomeans':means,'order':order,'adjacent_improvement_percent':margins,'sole_winners':dict(sole),'tied_best_instances':tied}
    compared=0
    for r in selected:
        i=r['id'];o=original[i];p=ipeft[i]
        assert r['input_sha256']==o['input_sha256']==p['source_sha256']
        assert r['family']==o['family']==p['family']
        for mode in MODES:
            for alg in ALGOS:
                result=p['modes'][mode] if alg=='IPEFT' else o['placements'][mode][ALIASES[alg]]
                assert result['valid'] is True and not result.get('errors')
                assert value(r,mode,alg)==float(result['makespan'])
                compared+=1
    check('Every selected makespan exactly matches a valid archived outcome',compared==count*12)
    limitations=['Outcome-selected synthetic exploratory subset; not an independent or representative confirmation.',
                 'Aggregate order only; individual instance rankings can differ.',
                 'Several adjacent margins are close to 0.1 percent, so robustness is not established.',
                 'Source-level feasibility audit only; this audit does not replay schedules or independently prove solver optimality.']
    if count==209:
        check('209 selector receipt records time limit rather than optimality',claimed['solver']['status']==1 and claimed['solver']['success'] is False)
        limitations.append('209 is a feasible saved incumbent. The solver reached its time limit, so this count must not be claimed as maximal.')
    else:
        check('225 selector receipt records optimum for its stated constraints',claimed['solver']['status']==0 and claimed['solver']['success'] is True and claimed['solver']['mip_gap']==0.0)
        limitations.append('225 is reported optimal only for the exact saved constraint set, including pool eligibility, at least one winner/loss per family, majority ECTD wins, and the 0.1 percent full-order margins. This audit verifies feasibility without independently certifying optimality.')
    output={'status':'passed','candidate':name,'source_sha256':source_hashes,'selected_count':count,
            'distinct_input_hash_count':count,'classification_counts':dict(groups),'winner_fraction':wf,
            'ids_sha256':idhash,'family_counts':families,'placements':placements,
            'source_schedule_outcomes_compared':compared,'checks':checks,
            'margin_definition':'100 * (1 - geometric_mean(faster) / geometric_mean(slower)); every adjacent pair must improve by at least 0.1 percent in each mode.',
            'solver_receipt':claimed['solver'],
            'scope':f'Separate {count}-instance alternative; retains {wins} of the original 1467 winners and selects {losses} genuine both-mode losses. Does not preserve the 1467+500 composition. Original 1967-instance study remains unchanged.',
            'limitations':limitations}
    path=HERE/f'{name}_independent_audit.json';path.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    return {'candidate':name,'status':'passed','checks':len(checks),'count':count,'wins':wins,'losses':losses,
            'source_outcomes_compared':compared,'families':families,'placements':placements,'path':str(path)}

def main():
    rows=read_csv(SOURCE/'full_pool_all_3072_results.csv');index={r['id']:r for r in rows}
    assert len(rows)==len(index)==3072
    hashes={name:sha(SOURCE/name) for name in ('full_pool_all_3072_results.csv','original_results.jsonl.gz','ipeft_pool_results.jsonl.gz')}
    original=read_gzip(SOURCE/'original_results.jsonl.gz');ipeft=read_gzip(SOURCE/'ipeft_pool_results.jsonl.gz')
    frozen=json.loads((ROOT/'ectd_mixed_1967/cohort/summary.json').read_text())
    for args in [('full_order_original_fraction_minone',209,156,53),('full_order_majority',225,134,91)]:
        print(json.dumps(audit(*args,index,hashes,original,ipeft,frozen),indent=2))

if __name__=='__main__':main()
