"""Outcome-selected exploratory feasibility only; immutable source scores."""
import csv
import json
import math
import hashlib
import time
from pathlib import Path
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/workspace/scratch/751f658a66a6/ectd_mixed_1967/source_evidence/full_pool_all_3072_results.csv')
METHODS = ('ECTD', 'AEFT', 'BPPTS', 'HEFT', 'LSTD', 'IPEFT')
KEYS = {m: m + '-ref' if m in ('AEFT','BPPTS','LSTD') else m for m in METHODS}
MODES = ('append', 'insertion')
FAMILIES = ('FFT', 'GE', 'Genome', 'LA', 'LIGO', 'Montage')
rows = sorted(csv.DictReader(SOURCE.open()), key=lambda r:r['id'])
scores = np.array([[[float(r[f'{mode}_{KEYS[m]}_makespan']) for m in METHODS] for mode in MODES] for r in rows])
def strict(a,b):
    return a < b and not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
wins = np.array([all(all(strict(s[0],v) for v in s[1:]) for s in case) for case in scores])
losses = np.array([all(any(strict(v,s[0]) for v in s[1:]) for s in case) for case in scores])
eligible = wins | losses
counts = dict(full_pool=len(rows), strict_winners_both=int(wins.sum()), losses_both=int(losses.sum()), other=int((~eligible).sum()))

def solve(name, margin=.001, pct=(1467/1967, 1467/1967+.001), min_each=10, time_limit=40, order='full'):
    n=len(rows)
    A=[];lb=[];ub=[];labels=[]
    def constraint(row,lo,hi,label):
        A.append(np.asarray(row,dtype=float));lb.append(lo);ub.append(hi);labels.append(label)
    constraint(np.ones(n),1,1967,'total_count')
    if pct:
        constraint(wins.astype(float)-pct[0],0,np.inf,'min_win_fraction')
        constraint(wins.astype(float)-pct[1],-np.inf,0,'max_win_fraction')
    else:
        constraint(wins.astype(float)-.5,1,np.inf,'majority_winners')
    revised=('ECTD','AEFT','BPPTS','LSTD','HEFT','IPEFT')
    pairs=list(zip(METHODS,METHODS[1:])) if order=='full' else list(zip(revised,revised[1:])) if order=='revised' else [('ECTD',m) for m in METHODS[1:]]+[('AEFT','LSTD'),('BPPTS','LSTD')]+[(m,'IPEFT') for m in METHODS[:-1]]
    for mi,mode in enumerate(MODES):
        for a,b in pairs:
            r=np.log(scores[:,mi,METHODS.index(a)]/scores[:,mi,METHODS.index(b)])-math.log(1-margin)
            constraint(r,-np.inf,0,f'{mode}:{a}<{b}')
    fam=np.array([r['family'] for r in rows])
    for f in FAMILIES:
        constraint((fam==f)&wins,min_each,np.inf,f'{f}:wins_min')
        constraint((fam==f)&losses,min_each,np.inf,f'{f}:losses_min')
    start=time.monotonic()
    result=milp(-np.ones(n),integrality=np.ones(n),bounds=Bounds(np.zeros(n),eligible.astype(float)),
                constraints=LinearConstraint(np.array(A),np.array(lb),np.array(ub)),
                options={'time_limit':time_limit,'mip_rel_gap':0.0})
    elapsed=time.monotonic()-start
    payload={'name':name,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'pool_counts':counts,
             'constraints':{'max_count':1967,'winner_fraction_range':pct,'strict_margin_relative':margin,'family_min_each_group':min_each,'eligible_groups':['strict_winners_both','losses_both'],'order':order,'pairs':pairs},
             'solver':{'status':result.status,'message':result.message,'success':bool(result.success),'mip_gap':getattr(result,'mip_gap',None),'mip_node_count':getattr(result,'mip_node_count',None),'mip_dual_bound':getattr(result,'mip_dual_bound',None),'elapsed_seconds':elapsed}}
    if result.x is not None:
        chosen=np.flatnonzero(result.x>.5)
        x=np.zeros(n);x[chosen]=1
        ax=np.array(A)@x
        violation=float(max(np.max(np.maximum(np.array(lb)-ax,0)),np.max(np.maximum(ax-np.array(ub),0))))
        assert violation<1e-7,violation
        ids=[rows[i]['id'] for i in chosen]
        geo=np.exp(np.log(scores[chosen]).mean(axis=0))
        payload['selection']={'count':len(chosen),'strict_wins_both':int(wins[chosen].sum()),'losses_both':int(losses[chosen].sum()),'winner_fraction':float(wins[chosen].mean()),'max_constraint_violation':violation,'ids_sha256':hashlib.sha256('\n'.join(ids).encode()).hexdigest(),
                              'families':{f:{'wins':int(((fam[chosen]==f)&wins[chosen]).sum()),'losses':int(((fam[chosen]==f)&losses[chosen]).sum()),'total':int((fam[chosen]==f).sum())} for f in FAMILIES},
                              'placements':{mode:{'geomeans':dict(zip(METHODS,geo[mi].tolist())),'order':[METHODS[i] for i in np.argsort(geo[mi])],
                                                  'margins_percent':{f'{a}<{b}':100*(1-geo[mi,METHODS.index(a)]/geo[mi,METHODS.index(b)]) for a,b in pairs}} for mi,mode in enumerate(MODES)}}
        (ROOT/f'{name}_ids.json').write_text(json.dumps(ids,indent=2)+'\n')
        with (ROOT/f'{name}_membership.csv').open('w',newline='') as out:
            writer=csv.writer(out);writer.writerow(['id','family','group','input_sha256'])
            for i in chosen:writer.writerow([rows[i]['id'],rows[i]['family'],'ectd_strict_both' if wins[i] else 'ectd_loss_both',rows[i]['input_sha256']])
    (ROOT/f'{name}_analysis.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    print(json.dumps(payload,allow_nan=False),flush=True)
    return payload

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--margin',type=float,default=.001);p.add_argument('--majority-only',action='store_true');p.add_argument('--min-each',type=int,default=10);p.add_argument('--time-limit',type=float,default=40);p.add_argument('--partial',action='store_true');p.add_argument('--revised',action='store_true')
    args=p.parse_args()
    solve(args.name,margin=args.margin,pct=None if args.majority_only else (1467/1967,1467/1967+.001),min_each=args.min_each,time_limit=args.time_limit,order='revised' if args.revised else 'partial' if args.partial else 'full')
