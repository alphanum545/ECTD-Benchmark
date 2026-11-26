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

from ectdbench.baselines import compute_ippts_pcm, upward_ranks
from ectdbench.engine import Schedule, optimistic_cost_table, ready_order
from ectdbench.extended_baselines import aeft_ioct, bppts_bpcm
from ectdbench.ipeft import tables as ipeft_tables
from ectdbench.proposed import (
    descendant_ranks,
    critical_path_weights,
    lstd_ranks,
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


def _own_cost_damped_with_ranks(problem, ranks, insertion=True):
    """The winning scoring rule, with the priority order supplied from outside.

    ``v_own_cost_damped`` fixes both the scoring rule and the rank. This splits
    them: the tail and the damping are held constant and only ``ranks`` varies,
    so the cost of a rank functional can be read off on its own.

    One coupling to be aware of: ``critical_path_weights`` takes ``ranks`` as an
    argument, so changing the order also changes the damping weights. That is
    the configuration we would actually ship, so it is measured as-is rather
    than isolated. ``v_rank_*_nodamp`` variants exist for the cases where the
    interaction is worth separating.
    """
    oct_table, cps = optimistic_cost_table(problem)
    weights = critical_path_weights(problem, ranks, cps)
    tail = [[problem.w[i][q] + oct_table[i][q] * weights[i][q]
             for q in range(problem.p)] for i in range(problem.n)]
    return _schedule(problem, ranks, tail, insertion)


def _mean_row(table, p):
    return [sum(row) / p for row in table]


# --------------------------------------------------------------- variants

def v_baseline(problem, insertion=True):
    """Stock ECTD, unchanged. The reference the ablations are measured from."""
    ranks, tail = _damped_tail(problem, 1)
    return _schedule(problem, ranks, tail, insertion)


def v_own_cost(problem, insertion=True):
    """Own-cost tail, no damping. The tuned variant."""
    ranks = descendant_ranks(problem)
    return _schedule(problem, ranks, own_cost_table(problem), insertion)


def v_own_cost_damped(problem, insertion=True):
    """Own-cost tail with the author-code damping applied to the tail part.

    Current best on the corpus. The damping weights multiply only the
    continuation, not the task's own cost: the own cost is measured, so there
    is nothing optimistic about it to damp. That is the whole difference from
    ``v_own_cost``, and it is worth 0.12%.

    Algebraically identical to the ``s:sw2.0_damp_descendant`` configuration in
    ``scripts/ectd_search.py``, which is how it was found: that harness scores
    ``start + 2w + oct*weights``, and since ``oct == own_cost - w`` this is
    ``start + w + (w + oct*weights)``.
    """
    ranks = descendant_ranks(problem)
    oct_table, cps = optimistic_cost_table(problem)
    weights = critical_path_weights(problem, ranks, cps)
    tail = [[problem.w[i][q] + oct_table[i][q] * weights[i][q]
             for q in range(problem.p)] for i in range(problem.n)]
    return _schedule(problem, ranks, tail, insertion)


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
    "v:own_cost_damped": v_own_cost_damped,
    "v:own_cost_aeft_ranks": v_own_cost_aeft_ranks,
    "v:own_cost_pure_eft": v_own_cost_pure_eft,
    "v:no_damping": v_no_damping,
    "v:damp_threshold_p": v_damp_threshold_p,
    "v:no_dup": v_no_dup,
}


# ------------------------------------------------- rank-functional sweep
#
# The complexity requirement is O(n^2 p) worst case in n. ECTD misses it on one
# term only: descendant_ranks needs the weighted sum over DISTINCT descendants,
# which is transitive-closure shaped and costs O(e n/w) for the union, i.e.
# O(n^3/w) on a dense DAG. Every rank below is O(n + e) or O(e p), so every one
# of them clears the bound. The question is only what each costs in quality.
#
# All of these hold the winning scoring rule fixed (own-cost tail, damped
# continuation) so the delta is attributable to the rank alone.

def v_rank_heft(problem, insertion=True):
    """HEFT upward rank. O(n + e)."""
    return _own_cost_damped_with_ranks(problem, upward_ranks(problem), insertion)


def v_rank_lstd(problem, insertion=True):
    """LSTD rank. O(n + e)."""
    return _own_cost_damped_with_ranks(problem, lstd_ranks(problem), insertion)


def v_rank_aeft(problem, insertion=True):
    """AEFT mean IOCT. O(e p)."""
    return _own_cost_damped_with_ranks(
        problem, _mean_row(aeft_ioct(problem), problem.p), insertion)


def v_rank_own_cost(problem, insertion=True):
    """Mean own-cost-plus-tail. O(e p)."""
    return _own_cost_damped_with_ranks(
        problem, _mean_row(own_cost_table(problem), problem.p), insertion)


def v_rank_bppts(problem, insertion=True):
    """BPPTS BPCM mean. O(e p)."""
    return _own_cost_damped_with_ranks(
        problem, _mean_row(bppts_bpcm(problem), problem.p), insertion)


def v_rank_ipeft(problem, insertion=True):
    """IPEFT PCT-based rank. O(e p)."""
    ranks, _cnp, _cnct, _cn = ipeft_tables(problem)
    return _own_cost_damped_with_ranks(problem, ranks, insertion)


def v_rank_ippts(problem, insertion=True):
    """IPPTS PCM rank, scaled by outdegree as the source does. O(e p)."""
    p = problem.p
    pcm = compute_ippts_pcm(problem)
    ranks = [sum(pcm[i]) / p * len(problem.succ[i]) for i in range(problem.n)]
    return _own_cost_damped_with_ranks(problem, ranks, insertion)


def v_rank_own_cost_nodamp(problem, insertion=True):
    """Control: mean own-cost rank with damping off, to separate the coupling."""
    p = problem.p
    tail = own_cost_table(problem)
    return _schedule(problem, _mean_row(tail, p), tail, insertion)


# ------------------------------------------- ECTD's own parameterised rank
#
# The v:rank_* variants above import another algorithm's priority order. That
# solves the complexity problem but it is not a contribution: the resulting
# policy is a baseline's rank with ECTD's scoring rule attached, and a reviewer
# is entitled to say so. What follows is ECTD's own rank with its own parameter.
#
# The mechanism. ECTD's optimistic cost table is per processor: oct[i][q] is the
# best-case cost of everything after task i, given i runs on q. Ordering tasks
# requires collapsing that row to one number, and the collapse is a choice that
# no other algorithm in the suite makes explicitly:
#
#     rank_lam(i) = max_q oct[i][q] + lam * (mean_q oct[i][q] - max_q oct[i][q])
#
#   lam = 0    the max: assume the tail runs on its worst processor. A task
#              whose tail is expensive somewhere is treated as urgent.
#   lam = 1    the mean: what AEFT and IPPTS effectively use, and it measured
#              1.0% worse than descendant_ranks.
#   lam > 1    below the mean, toward the min: assume the tail lands well.
#
# So lam is a single knob on how much per-processor pessimism the ordering keeps.
# The claim to test is that lam < 1 orders better than the mean, because a task
# that is expensive on its worst processor is more urgent than its average
# suggests. That is ECTD's own table and ECTD's own claim, and lam is the
# parameter the algorithm gets to have.

def ectd_rank(problem, lam):
    """ECTD's own priority order: a lam-blend of the max and mean of its OCT.

    O(e p) to build the table plus O(n p) to collapse it, so it clears O(n^2 p)
    with no descendant set and no imported rank.
    """
    p = problem.p
    oct_table, _cps = optimistic_cost_table(problem)
    ranks = [0.0] * problem.n
    for i in range(problem.n):
        row = oct_table[i]
        high = max(row)
        mean = sum(row) / p
        ranks[i] = high + lam * (mean - high)
    return ranks


def _ectd_lam(lam):
    def policy(problem, insertion=True):
        return _own_cost_damped_with_ranks(problem, ectd_rank(problem, lam), insertion)
    policy.__name__ = "v_ectd_lam_%s" % ("%g" % lam).replace(".", "p")
    return policy


# The sweep. lam = 1 is the mean, which is the aggregation the baselines use, so
# it doubles as the control: if the family does not beat lam = 1 it has not
# demonstrated anything. lam = 0 is the pure max.
ECTD_LAMBDAS = (0.0, 0.25, 0.5, 0.75, 1.0)

ECTD_LAM_VARIANTS = {
    "v:ectd_lam_%s" % ("%g" % lam).replace(".", "p"): _ectd_lam(lam)
    for lam in ECTD_LAMBDAS
}


RANK_VARIANTS = {
    "v:rank_heft": v_rank_heft,
    "v:rank_lstd": v_rank_lstd,
    "v:rank_aeft": v_rank_aeft,
    "v:rank_own_cost": v_rank_own_cost,
    "v:rank_bppts": v_rank_bppts,
    "v:rank_ipeft": v_rank_ipeft,
    "v:rank_ippts": v_rank_ippts,
    "v:rank_own_cost_nodamp": v_rank_own_cost_nodamp,
}

VARIANTS.update(RANK_VARIANTS)
VARIANTS.update(ECTD_LAM_VARIANTS)
