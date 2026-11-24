"""IPEFT scheduling policy, ported from the pinned scheduling-benchmark ipeft.cpp.

Standard-library port of ``ectdbench/ipeft.py``. Source: alphanum545/scheduling-benchmark,
commit 3741b6d4a61a9599284f78c23a826658b81f7500, algorithms/makespan/ipeft.cpp
SHA 841cba1c1840d8d9c50b484f4386aeedc96c6418. The source's PCT and CNCT
recurrences, critical-neighbor selection, priority ordering (higher task ID wins
rank ties), and processor score are preserved. 'append' is the source placement
mode; 'insertion' uses these same scores with the shared engine's gap insertion
as a sensitivity.
"""

from __future__ import annotations

from .engine import Schedule


def _round_tenth_cpp(value):
    sign = -1.0 if value < 0 else 1.0
    return sign * (int(abs(value) * 10.0 + 0.5) // 1) / 10.0


def _other_max(values):
    """max over q != k, for each k, or -inf when p == 1."""
    n = len(values)
    if n == 1:
        return [float("-inf")]
    index = max(range(n), key=lambda i: (values[i], -i))
    top = values[index]
    other = max(values[:index] + values[index + 1:])
    result = [top] * n
    result[index] = other
    return result


def tables(problem):
    n, p = problem.n, problem.p
    w, children, pred, edges = problem.w, problem.succ, problem.pred, problem.edges
    mw = [_round_tenth_cpp(sum(w[i]) / p) for i in range(n)]

    # Source findpct: exit PCT=0. Outdegree branch uses max_q, not min_q.
    pct = [[0.0] * p for _ in range(n)]
    for task in reversed(problem.topo):
        row = [0.0] * p
        for child in children[task]:
            z = [pct[child][q] + w[child][q] for q in range(p)]
            other = _other_max(z)
            c = edges[task, child]
            for q in range(p):
                value = max(z[q], other[q] + c)
                if value > row[q]:
                    row[q] = value
        pct[task] = row
    ranks = [sum(pct[i]) / p + mw[i] for i in range(n)]

    aest = [0.0] * n
    for task in problem.topo:
        aest[task] = max(
            (aest[parent] + mw[parent] + edges[parent, task] for parent in pred[task]),
            default=0.0,
        )
    alst = list(aest)
    for task in reversed(problem.topo):
        if children[task]:
            alst[task] = _round_tenth_cpp(
                min(alst[c] - edges[task, c] for c in children[task]) - mw[task])

    cn = [aest[i] == alst[i] for i in range(n)]
    cnp = [not cn[t] and any(cn[c] for c in children[t]) for t in range(n)]

    cnct = [[0.0] * p for _ in range(n)]
    for task in reversed(problem.topo):
        critical_children = [c for c in children[task] if cn[c]]
        selected = critical_children if critical_children else children[task]
        for child in selected:
            z = [cnct[child][q] + w[child][q] for q in range(p)]
            low = min(z)
            c = edges[task, child]
            for q in range(p):
                value = min(z[q], low + c)
                if value > cnct[task][q]:
                    cnct[task][q] = value
    return ranks, cnp, cnct, cn


def run_ipeft(problem, insertion=False):
    ranks, cnp, cnct, cn = tables(problem)
    order = sorted(range(problem.n), key=lambda t: (-ranks[t], -t))
    schedule = Schedule(problem, insertion=insertion)
    for task in order:
        if any(parent not in schedule.primary for parent in problem.pred[task]):
            raise ValueError(
                "IPEFT source global priority order violates precedence at task %d" % task)
        starts, finishes = schedule.earliest_slots(task)
        score = finishes if cnp[task] else [finishes[q] + cnct[task][q] for q in range(problem.p)]
        processor = min(range(problem.p), key=lambda q: (score[q], q))
        schedule.place(task, processor, slot=(starts[processor], finishes[processor]))
    schedule.diagnostics = {
        "cn_tasks": int(sum(cn)),
        "cnp_tasks": int(sum(cnp)),
        "source_policy": "ipeft.cpp",
        "placement_extension": ("insertion using source processor score" if insertion
                                else "source append-only"),
    }
    return schedule
