"""ECTD, MPEFT, and LSTD policies reconstructed from the author's code.

Standard-library port of ``ectdbench/proposed.py``. The policies retain the
recovered ranking, processor scores, and duplication criterion; they are not
retuned to any benchmark.
"""

from __future__ import annotations

import math

from .engine import Schedule, optimistic_cost_table, ready_order


def descendant_ranks(problem):
    """DCT(i) plus the DCT of each distinct descendant, counted once.

    DCT is minimum execution time plus outgoing edge communication time. Bit
    sets implement descendant unions without counting a shared descendant
    repeatedly when several paths reach it.
    """
    dct = [float(problem.min_w[i]) for i in range(problem.n)]
    for task in range(problem.n):
        dct[task] += sum(problem.edges[task, child] for child in problem.succ[task])

    descendants = [0] * problem.n
    ranks = [0.0] * problem.n
    for task in reversed(problem.topo):
        bits = 0
        for child in problem.succ[task]:
            bits |= (1 << child) | descendants[child]
        descendants[task] = bits
        total = float(dct[task])
        while bits:
            lowest = bits & -bits
            child = lowest.bit_length() - 1
            total += float(dct[child])
            bits ^= lowest
        ranks[task] = total
    return ranks


def critical_path_weights(problem, ranks, cps):
    """Recover the author-code threshold and rounding, not a tuned variant.

    Apply damping only when outdegree > processors + 1. Round the critical
    successor's rank share UP to the nearest tenth, exactly as the C++ policy.
    A zero denominator has no positive remaining cost and receives weight 1.
    """
    p = problem.p
    weights = [[1.0] * p for _ in range(problem.n)]
    for task in range(problem.n):
        children = problem.succ[task]
        if len(children) <= p + 1:
            continue
        denominator = sum(float(ranks[child]) + problem.edges[task, child]
                          for child in children)
        if denominator <= 0:
            continue
        for processor in range(p):
            child = int(cps[task][processor])
            if child not in children:
                raise ValueError("CPS must identify an immediate successor")
            ratio = float(ranks[child]) / denominator
            weights[task][processor] = min(1.0, math.ceil(10.0 * ratio) / 10.0)
    return weights


def entry_duplication_processors(problem, source_processor):
    """Processors where a local entry copy beats ALL remote successor arrivals.

    Every processor other than the source is checked. Strict comparison is
    retained. A dummy entry with zero-cost edges does not qualify; a task with
    no successors has nothing to accelerate.
    """
    entry = problem.entry
    if problem.pred[entry]:
        raise ValueError("The duplication candidate must be an entry task")
    children = problem.succ[entry]
    if not children:
        return ()
    source_finish = float(problem.w[entry][source_processor])
    return tuple(
        processor for processor in range(problem.p)
        if processor != source_processor
        and all(float(problem.w[entry][processor]) < source_finish + problem.edges[entry, child]
                for child in children)
    )


def _place_entry(schedule, problem, duplication):
    processor = min(range(problem.p),
                    key=lambda q: (float(problem.w[problem.entry][q]), q))
    schedule.place(problem.entry, processor)
    if duplication:
        for target in entry_duplication_processors(problem, processor):
            # Each copy is a real execution with its own finish time and
            # occupied processor interval; it is not an instantaneous cache.
            schedule.place(problem.entry, target, duplicate=True)


def _place_scored(schedule, task, tail_cost):
    starts, finishes = schedule.earliest_slots(task)
    best = None
    for processor in range(len(finishes)):
        slot = (float(starts[processor]), float(finishes[processor]))
        eft = float(slot[1])
        score = eft if tail_cost is None else eft + float(tail_cost[task][processor])
        key = (score, eft, processor)
        if best is None or key < best[0]:
            best = (key, processor, slot)
    if best is None:
        raise ValueError("A scheduling problem must have at least one processor")
    schedule.place(task, best[1], slot=best[2])


def _record_policy_diagnostics(schedule, problem, weights, unweighted_entry=False):
    diagnostics = {
        "damping_tasks": 0,
        "damping_selected_tasks": 0,
        "damping_scored_tasks": 0,
        "min_weight": 1.0,
        "entry_is_dummy": problem.dummy_entry is not None,
    }
    if weights is not None and not isinstance(weights, float):
        diagnostics["damping_tasks"] = int(sum(
            1 for row in weights if any(v < 1.0 for v in row)))
        diagnostics["min_weight"] = float(min(min(row) for row in weights))
        selected = sum(
            1 for task in range(problem.original_n)
            if weights[task][schedule.primary[task].processor] < 1.0)
        diagnostics["damping_selected_tasks"] = int(selected)
        scored = int(selected)
        if (unweighted_entry and problem.entry < problem.original_n
                and weights[problem.entry][schedule.primary[problem.entry].processor] < 1.0):
            scored -= 1
        diagnostics["damping_scored_tasks"] = scored
    schedule.diagnostics.update(diagnostics)


def run_ectd(problem, insertion=True, duplication=True, damping=True):
    """Run the corrected ECTD reference, or a declared component ablation."""
    ranks = descendant_ranks(problem)
    oct_table, cps = optimistic_cost_table(problem)
    weights = critical_path_weights(problem, ranks, cps) if damping else 1.0
    if isinstance(weights, float):
        tail_cost = [[v * weights for v in row] for row in oct_table]
    else:
        tail_cost = [[oct_table[i][q] * weights[i][q] for q in range(problem.p)]
                     for i in range(problem.n)]
    schedule = Schedule(problem, insertion=insertion)
    for task in ready_order(problem, ranks):
        if task == problem.entry:
            _place_entry(schedule, problem, duplication)
        else:
            _place_scored(schedule, task, tail_cost)
    _record_policy_diagnostics(schedule, problem, weights, unweighted_entry=True)
    return schedule


def run_mpeft(problem, insertion=True):
    """Run the author-code MPEFT reference with precedence-safe readiness.

    Unlike ECTD, MPEFT scores the entry with EFT + OCT*k as well. Therefore
    ECTD with duplication disabled is not assumed to be identical to MPEFT.
    """
    ranks = descendant_ranks(problem)
    oct_table, cps = optimistic_cost_table(problem)
    weights = critical_path_weights(problem, ranks, cps)
    tail_cost = [[oct_table[i][q] * weights[i][q] for q in range(problem.p)]
                 for i in range(problem.n)]
    schedule = Schedule(problem, insertion=insertion)
    for task in ready_order(problem, ranks):
        _place_scored(schedule, task, tail_cost)
    _record_policy_diagnostics(schedule, problem, weights)
    return schedule


def lstd_ranks(problem):
    """LSTD rank recovered from Algo/lstd.cpp, without integer scaling.

    h(i) = min_w(i)*(max_w(i)-min_w(i))/max_w(i).
    r(i) = max_{j in succ(i)} [c(i,j) + h(j) + r(j)], with exit rank 0.
    """
    minimum = problem.min_w
    maximum = [max(row) for row in problem.w]
    weight = [0.0] * problem.n
    for i in range(problem.n):
        if maximum[i] > 0:
            weight[i] = minimum[i] * (maximum[i] - minimum[i]) / maximum[i]
    ranks = [0.0] * problem.n
    for task in reversed(problem.topo):
        ranks[task] = max(
            (problem.edges[task, child] + weight[child] + ranks[child]
             for child in problem.succ[task]),
            default=0.0,
        )
    return ranks


def run_lstd(problem, insertion=True):
    """Run the LSTD author-code reference with corrected feasible duplication."""
    ranks = lstd_ranks(problem)
    schedule = Schedule(problem, insertion=insertion)
    for task in ready_order(problem, ranks):
        if task == problem.entry:
            _place_entry(schedule, problem, True)
        else:
            _place_scored(schedule, task, None)
    _record_policy_diagnostics(schedule, problem, None)
    return schedule
