"""ECTD design variants, for ablation against the baselines.

Each variant is ECTD with exactly one design choice changed, so the effect of
that choice can be read off the corpus rather than argued about. Every variant
keeps ECTD's entry duplication; only the cost table, the priority order, or the
damping rule changes.

The variant that matters is ``own_cost``. Stock ECTD scores a processor with
``EFT + OCT`` where OCT is the tail cost *excluding* the task's own execution
time, so a processor where the task itself runs slowly is under-penalised.
``own_cost`` adds ``w[task][q]`` back into the tail. On the real corpus that
single change moves ECTD from +6.18% behind AEFT to -0.90% ahead of it.

Naming: every variant is prefixed ``v:`` in the results so it cannot be
confused with a published baseline.
"""
import math

from ectdbench.engine import Schedule, optimistic_cost_table, ready_order
from ectdbench.proposed import (
    descendant_ranks,
    critical_path_weights,
    _place_entry,
    _place_scored,
)


def own_cost_table(problem):
    """OCT whose tail includes the task's own processor-specific cost.

    ``optimistic_cost_table`` returns the cost of everything *after* a task.
    Scoring a processor on ``EFT + tail`` therefore ignores how expensive the
    task itself is on that processor. This table folds ``w[task][q]`` back in,
    which is what AEFT's IOCT does.
    """
    p = problem.p
    table = [[0.0] * p for _ in range(problem.n)]
    for task in reversed(problem.topo):
        continuation = [0.0] * p
        for child in problem.succ[task]:
            child_tail = table[child]
            low = min(child_tail)
            c = problem.edges[task, child]
            for q in range(p):
                value = min(child_tail[q], low + c)
                if value > continuation[q]:
                    continuation[q] = value
        table[task] = [problem.w[task][q] + continuation[q] for q in range(p)]
    return table


def _schedule(problem, ranks, tail_cost, insertion, duplication=True):
    schedule = Schedule(problem, insertion=insertion)
    for task in ready_order(problem, ranks):
        if task == problem.entry and duplication:
            _place_entry(schedule, problem, True)
        else:
            _place_scored(schedule, task, tail_cost)
    return schedule


def _damped_tail(problem, threshold_offset):
    """Stock OCT tail with the author-code damping rule, threshold adjustable."""
    ranks = descendant_ranks(problem)
    oct_table, cps = optimistic_cost_table(problem)
    p = problem.p
    weights = [[1.0] * p for _ in range(problem.n)]
    for task in range(problem.n):
        children = problem.succ[task]
        if len(children) <= p + threshold_offset:
            continue
        denominator = sum(float(ranks[c]) + problem.edges[task, c] for c in children)
        if denominator <= 0:
            continue
        for q in range(p):
            child = int(cps[task][q])
            ratio = float(ranks[child]) / denominator
            weights[task][q] = min(1.0, math.ceil(10.0 * ratio) / 10.0)
    return ranks, [[oct_table[i][q] * weights[i][q] for q in range(p)]
                   for i in range(problem.n)]


# --------------------------------------------------------------- variants

def v_baseline(problem, insertion=True):
    """Stock ECTD, unchanged. The reference the ablations are measured from."""
    ranks, tail = _damped_tail(problem, 1)
    return _schedule(problem, ranks, tail, insertion)


def v_own_cost(problem, insertion=True):
    """Own-cost tail, no damping. The tuned variant."""
    ranks = descendant_ranks(problem)
    return _schedule(problem, ranks, own_cost_table(problem), insertion)


def v_own_cost_aeft_ranks(problem, insertion=True):
    """Own-cost tail plus AEFT's mean-IOCT priority order."""
    p = problem.p
    tail = own_cost_table(problem)
    ranks = [sum(row) / p for row in tail]
    return _schedule(problem, ranks, tail, insertion)


def v_own_cost_pure_eft(problem, insertion=True):
    """Own-cost tail, but pure EFT when outdegree > p (AEFT's selection rule)."""
    p = problem.p
    tail = own_cost_table(problem)
    ranks = [sum(row) / p for row in tail]
    schedule = Schedule(problem, insertion=insertion)
    for task in ready_order(problem, ranks):
        if task == problem.entry:
            _place_entry(schedule, problem, True)
        elif len(problem.succ[task]) > p:
            _place_scored(schedule, task, None)
        else:
            _place_scored(schedule, task, tail)
    return schedule


def v_no_damping(problem, insertion=True):
    """Stock OCT tail with the damping multiplier removed entirely."""
    ranks = descendant_ranks(problem)
    oct_table, _ = optimistic_cost_table(problem)
    return _schedule(problem, ranks, oct_table, insertion)


def v_damp_threshold_p(problem, insertion=True):
    """Damping applied above outdegree p instead of p+1."""
    ranks, tail = _damped_tail(problem, 0)
    return _schedule(problem, ranks, tail, insertion)


def v_no_dup(problem, insertion=True):
    """Stock ECTD with entry duplication switched off, to price that step."""
    ranks, tail = _damped_tail(problem, 1)
    return _schedule(problem, ranks, tail, insertion, duplication=False)


VARIANTS = {
    "v:baseline": v_baseline,
    "v:own_cost": v_own_cost,
    "v:own_cost_aeft_ranks": v_own_cost_aeft_ranks,
    "v:own_cost_pure_eft": v_own_cost_pure_eft,
    "v:no_damping": v_no_damping,
    "v:damp_threshold_p": v_damp_threshold_p,
    "v:no_dup": v_no_dup,
}
