"""IPEFT scheduling policy, ported from the pinned scheduling-benchmark ipeft.cpp.

Source (read on 2026-11-23): alphanum545/scheduling-benchmark,
commit 3741b6d4a61a9599284f78c23a826658b81f7500,
algorithms/makespan/ipeft.cpp SHA 841cba1c1840d8d9c50b484f4386aeedc96c6418.
The source's PCT and CNCT recurrences, critical-neighbor selection,
priority ordering (higher task ID wins rank ties), and processor score
are preserved. 'append' is the source placement mode; 'insertion' uses
these same scores with the shared engine's gap insertion as a sensitivity.
Not claimed to be verified equivalent to the published algorithm.
"""
from __future__ import annotations

import numpy as np
from .engine import Schedule
from .model import Problem


def _round_tenth_cpp(a):
    a = np.asarray(a, dtype=np.float64)
    return np.sign(a) * np.floor(np.abs(a) * 10.0 + 0.5) / 10.0


def _other_max(values):
    """max over q != k, for each k, or -inf when p == 1."""
    n = len(values)
    if n == 1:
        return np.array([-np.inf])
    ind = int(np.argmax(values))
    top = values[ind]
    other = np.max(np.delete(values, ind))
    result = np.full(n, top, dtype=float)
    result[ind] = other
    return result


def tables(problem: Problem):
    n, p = problem.n, problem.p
    w, children, pred, edges = problem.w, problem.succ, problem.pred, problem.edges
    mw = _round_tenth_cpp(w.mean(axis=1))

    # Source findpct: exit PCT=0. Outdegree branch uses max_q, not min_q.
    pct = np.zeros((n,p), dtype=float)
    for task in reversed(problem.topo):
        r = np.zeros(p, dtype=float)
        for child in children[task]:
            z = pct[child] + w[child]
            options = np.maximum(z, _other_max(z) + edges[task,child])
            r = np.maximum(r,options)
        pct[task]=r
    ranks=pct.mean(axis=1)+mw

    aest=np.zeros(n,dtype=float)
    for task in problem.topo:
        aest[task]=max((aest[parent]+mw[parent]+edges[parent,task] for parent in pred[task]),default=0.0)
    alst=np.array(aest, copy=True)
    for task in reversed(problem.topo):
        if children[task]:
            alst[task]=float(_round_tenth_cpp(min(alst[child]-edges[task,child]
                                                      for child in children[task])-mw[task]))
    cn = aest == alst
    cnp=np.array([not cn[t] and any(cn[child] for child in children[t])
                  for t in range(n)],dtype=bool)

    cnct=np.zeros((n,p),dtype=float)
    for task in reversed(problem.topo):
        critical_children=[c for c in children[task] if cn[c]]
        selected=critical_children if critical_children else children[task]
        for child in selected:
            z=cnct[child]+w[child]
            score=np.minimum(z, float(np.min(z))+edges[task,child])
            cnct[task]=np.maximum(cnct[task], score)
    return ranks,cnp,cnct,cn


def run_ipeft(problem: Problem, insertion: bool = False) -> Schedule:
    ranks, cnp, cnct, cn=tables(problem)
    order = sorted(range(problem.n), key=lambda t: (-ranks[t],-t))
    schedule=Schedule(problem,insertion=insertion)
    for task in order:
        if any(parent not in schedule.primary for parent in problem.pred[task]):
            raise ValueError(f'IPEFT source global priority order violates precedence at task {task}')
        starts,finishes=schedule.earliest_slots(task)
        score=finishes if cnp[task] else finishes+cnct[task]
        processor=int(np.argmin(score))
        schedule.place(task,processor,slot=(starts[processor],finishes[processor]))
    schedule.diagnostics={'cn_tasks':int(sum(cn)),'cnp_tasks':int(sum(cnp)),
                          'source_policy':'ipeft.cpp',
                          'placement_extension':'insertion using source processor score' if insertion else 'source append-only'}
    return schedule
