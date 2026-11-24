"""Ports of BPPTS and AEFT from the pinned scheduling-benchmark repository.

Standard-library port of ``ectdbench/extended_baselines.py``. Source:
alphanum545/scheduling-benchmark at 3741b6d4a61a9599284f78c23a826658b81f7500,
algorithms/makespan/. The source-specific ranking, degree switches, and
processor ties are retained. Append-only placement matches that source;
insertion is a labelled sensitivity variant provided by the common engine.
"""

from __future__ import annotations

from .engine import Schedule, ready_order


def aeft_ioct(problem):
    """IOCT(i,p) includes the current task's processor-specific execution cost."""
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


def bppts_bpcm(problem):
    """The exact BPCM recurrence in the pinned source, including sink costs."""
    p = problem.p
    table = [[0.0] * p for _ in range(problem.n)]
    for task in reversed(problem.topo):
        if not problem.succ[task]:
            table[task] = list(problem.w[task])
            continue
        continuation = [0.0] * p
        for child in problem.succ[task]:
            child_tail = [table[child][q] + problem.w[child][q] for q in range(p)]
            low = min(child_tail)
            c = problem.edges[task, child]
            for q in range(p):
                value = min(child_tail[q], low + c)
                if value > continuation[q]:
                    continuation[q] = value
        mean_w = sum(problem.w[task]) / p
        table[task] = [mean_w + continuation[q] for q in range(p)]
    return table


def bppts_ranks(problem, table):
    """Mean BPCM times the source's mean-compute/mean-outgoing-edge factor."""
    ranks = [sum(table[i]) / problem.p for i in range(problem.n)]
    for task in range(problem.n):
        children = problem.succ[task]
        if children:
            mean_communication = sum(problem.edges[task, c] for c in children) / len(children)
            ranks[task] *= 1.0 + (sum(problem.w[task]) / problem.p) / max(mean_communication, 1.0)
    return ranks


def _select_processor(finishes, offsets, bppts, pure_eft):
    """Retain each source's ascending-processor loop and tie condition."""
    best = 0
    for processor in range(1, len(finishes)):
        if pure_eft:
            if finishes[processor] < finishes[best]:
                best = processor
            continue
        score = float(finishes[processor] + offsets[processor])
        best_score = float(finishes[best] + offsets[best])
        if bppts:
            if score < best_score - 1e-9 or (
                    abs(score - best_score) <= 1e-9
                    and finishes[processor] < finishes[best]):
                best = processor
        elif score < best_score:
            # AEFT deliberately has no EFT secondary comparison on a score tie.
            best = processor
    return best


def _schedule(problem, table, ranks, bppts, insertion):
    schedule = Schedule(problem, insertion=insertion)
    pure_eft_tasks = 0
    for task in ready_order(problem, ranks):
        starts, finishes = schedule.earliest_slots(task)
        pure_eft = len(problem.succ[task]) > problem.p
        processor = _select_processor(finishes, table[task], bppts=bppts, pure_eft=pure_eft)
        schedule.place(task, processor,
                       slot=(float(starts[processor]), float(finishes[processor])))
        if task < problem.original_n and pure_eft:
            pure_eft_tasks += 1
    schedule.diagnostics.update(
        pure_eft_tasks=pure_eft_tasks,
        entry_is_dummy=problem.dummy_entry is not None,
    )
    return schedule


def run_aeft(problem, insertion=True):
    """AEFT-ref: mean IOCT priority and source-specific I_EFT selection."""
    table = aeft_ioct(problem)
    ranks = [sum(row) / problem.p for row in table]
    return _schedule(problem, table, ranks, bppts=False, insertion=insertion)


def run_bppts(problem, insertion=True):
    """BPPTS-ref: BPCM priority and tolerance-aware B_EFT selection."""
    table = bppts_bpcm(problem)
    return _schedule(problem, table, bppts_ranks(problem, table),
                     bppts=True, insertion=insertion)
