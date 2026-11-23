"""Independent source-level audit of the separately selected 497-case alternative."""
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
ALGOS = ('ECTD', 'AEFT', 'BPPTS', 'LSTD', 'HEFT', 'IPEFT')
ALIASES = {'ECTD': 'ECTD', 'AEFT': 'AEFT-ref', 'BPPTS': 'BPPTS-ref',
           'LSTD': 'LSTD-ref', 'HEFT': 'HEFT', 'IPEFT': 'IPEFT'}
MODES = ('append', 'insertion')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def strictly_less(a,b):
    return a < b and not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)

def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def read_gzip(path):
    with gzip.open(path, 'rt') as f:
        return {r['id']: r for r in map(json.loads, f)}

def value(r,mode,alg):
    return float(r[f'{mode}_{ALIASES[alg]}_makespan'])

def classify(r):
    win,loss=[],[]
    for mode in MODES:
        e=value(r,mode,'ECTD')
        others=[value(r,mode,a) for a in ALGOS[1:]]
        win.append(all(strictly_less(e,a) for a in others))
        loss.append(any(strictly_less(a,e) for a in others))
    return 'ectd_strict_both' if all(win) else 'ectd_loss_both' if all(loss) else 'other'

def main():
    checks=[]
    def check(name, condition):
        checks.append({'check':name,'passed':bool(condition)})
        if not condition:
            raise AssertionError(name)
    source_path=SOURCE/'full_pool_all_3072_results.csv'
    records=read_csv(source_path)
    index={r['id']:r for r in records}
    selected_ids=json.loads((HERE/'revised_order_near_original_fraction_ids.json').read_text())
    claimed=json.loads((HERE/'revised_order_near_original_fraction_analysis.json').read_text())
    membership=read_csv(HERE/'revised_order_near_original_fraction_membership.csv')
    current=json.loads((ROOT/'ectd_mixed_1967/cohort/summary.json').read_text())
    check('pool has3072 uniqueIDs',len(records)==len(index)==3072)
    check('selected has497 distinctIDs',len(selected_ids)==len(set(selected_ids))==497)
    check('selectedIDs present in source',set(selected_ids)<=set(index))
    selected=[index[i] for i in selected_ids]
    check('distinct input hashes',len({r['input_sha256'] for r in selected})==497)
    groups=Counter(classify(r) for r in selected)
    check('371 strict both-mode wins and126 genuine both-mode losses',dict(groups)=={'ectd_strict_both':371,'ectd_loss_both':126})
    check('CSV hash matches selector receipt',sha(source_path)==claimed['source_sha256'])
    check('CSV hash matches frozen study receipt',sha(source_path)==current['source_files_sha256'][source_path.name])
    idhash=hashlib.sha256('\n'.join(sorted(selected_ids)).encode()).hexdigest()
    check('ID hash matches selector receipt',idhash==claimed['selection']['ids_sha256'])
    check('membership matches selectedIDset',len(membership)==len({r['id'] for r in membership})==497 and {r['id'] for r in membership}==set(selected_ids))
    check('membership family/group/inputhash agree with CSV',all(r['family']==index[r['id']]['family'] and r['group']==classify(index[r['id']]) and r['input_sha256']==index[r['id']]['input_sha256'] for r in membership))
    family_counts={f:{'wins':sum(r['family']==f and classify(r)=='ectd_strict_both' for r in selected),
                      'losses':sum(r['family']==f and classify(r)=='ectd_loss_both' for r in selected),
                      'total':sum(r['family']==f for r in selected)} for f in sorted({r['family'] for r in records})}
    check('all six families include at least10wins and10losses',len(family_counts)==6 and all(v['wins']>=10 and v['losses']>=10 for v in family_counts.values()))
    check('family counts match selector receipt',family_counts==claimed['selection']['families'])
    wf=371/497
    low,high=claimed['constraints']['winner_fraction_range']
    check('winner fraction within declared range',low<=wf<=high)
    placements={}
    for mode in MODES:
        means={a:math.exp(math.fsum(math.log(value(r,mode,a)) for r in selected)/497) for a in ALGOS}
        order=sorted(ALGOS,key=means.get)
        margins={f'{a}<{b}':100*(1-means[a]/means[b]) for a,b in zip(ALGOS,ALGOS[1:])}
        check(f'{mode} exact requested revised aggregate order',order==list(ALGOS))
        check(f'{mode} adjacent margins at least0.1percent',all(v>=0.1 for v in margins.values()))
        check(f'{mode} means match selector receipt',all(math.isclose(means[a],claimed['selection']['placements'][mode]['geomeans'][a],rel_tol=1e-12,abs_tol=1e-9) for a in ALGOS))
        check(f'{mode} margins match selector receipt',all(math.isclose(v,claimed['selection']['placements'][mode]['margins_percent'][pair],rel_tol=1e-10,abs_tol=1e-9) for pair,v in margins.items()))
        sole=Counter({a:0 for a in ALGOS});tied=0
        for r in selected:
            vals={a:value(r,mode,a) for a in ALGOS};best=min(vals.values())
            win=[a for a in ALGOS if math.isclose(vals[a],best,rel_tol=1e-12,abs_tol=1e-9)]
            if len(win)==1:sole[win[0]]+=1
            else:tied+=1
        placements[mode]={'geomeans':means,'order':order,'adjacent_improvement_percent':margins,'sole_winners':dict(sole),'tied_best_instances':tied}
    original=read_gzip(SOURCE/'original_results.jsonl.gz')
    ipeft=read_gzip(SOURCE/'ipeft_pool_results.jsonl.gz')
    source_hashes={name:sha(SOURCE/name) for name in ('full_pool_all_3072_results.csv','original_results.jsonl.gz','ipeft_pool_results.jsonl.gz')}
    check('allthree archives match frozen source hashes',all(source_hashes[name]==current['source_files_sha256'][name] for name in source_hashes))
    compared=0
    for row in selected:
        i=row['id'];o=original[i];p=ipeft[i]
        assert row['input_sha256']==o['input_sha256']==p['source_sha256']
        assert row['family']==o['family']==p['family']
        for mode in MODES:
            for alg in ALGOS:
                result=p['modes'][mode] if alg=='IPEFT' else o['placements'][mode][ALIASES[alg]]
                assert result['valid'] is True and not result.get('errors')
                assert value(row,mode,alg)==float(result['makespan'])
                compared+=1
    check('all5964selected makespans exactly match valid archive schedules',compared==5964)
    output={'status':'passed','audited_source_path':str(source_path),'source_sha256':source_hashes,
            'selected_count':497,'distinct_input_hash_count':497,'classification_counts':dict(groups),
            'winner_fraction':wf,'ids_sha256':idhash,'family_counts':family_counts,'placements':placements,
            'source_schedule_outcomes_compared':compared,'checks':checks,
            'margin_definition':'100 * (1 - geometric_mean(faster) / geometric_mean(slower)); each adjacent pair must be at least0.1percent in each mode.',
            'scope':'Independent source-level audit. The497-case alternative drops1096 of the original1467 fixed winners, retains371winners, and selects126losses. It does not preserve the requested1467+500composition. Original1967study files were not changed.',
            'limitations':['Outcome-selected synthetic exploratory subset; not representative or independent confirmation.',
                           'Aggregate order only; individual-case orders may differ.',
                           'Several adjacent aggregate margins are about0.1percent; this audit does not establish robustness.',
                           'This audit verifies selected saved outcomes, not schedule replay or solver optimality. Root performs replay separately.']}
    out=HERE/'revised_candidate_independent_audit.json'
    out.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ('checks','limitations')},indent=2))
    print('Auditchecks:',len(checks),'Output:',out)

if __name__=='__main__':main()
