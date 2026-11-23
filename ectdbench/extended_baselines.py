"""Ports of BPPTS and AEFT from the pinned scheduling-benchmark repository.

Source: alphanum545/scheduling-benchmark at
3741b6d4a61a9599284f78c23a826658b81f7500, algorithms/makespan/.
The source-specific ranking, degree switches, and processor ties are retained.
Append-only placement matches that source; insertion is a labelled sensitivity
variant provided by the common engine. See docs/extended_algorithm_sources.md.
"""

from __future__ import annotations

import numpy as np

from .engine import Schedule, ready_order
from .model import Problem


def aeft_ioct(problem: Problem) -> np.ndarray:
    """IOCT(i,p) includes the current task's processor-specific execution cost."""
    table = np.zeros((problem.n, problem.p), dtype=float)
    for task in reversed(problem.topo):
        continuation = np.zeros(problem.p, dtype=float)
        for child in problem.succ[task]:
            child_tail = table[child]
            values = np.minimum(child_tail, child_tail.min() + problem.edges[task, child])
            continuation = np.maximum(continuation, values)
        table[task] = problem.w[task] + continuation
    return table


def bppts_bpcm(problem: Problem) -> np.ndarray:
    """The exact BPCM recurrence in the pinned source, including sink costs."""
    table = np.zeros((problem.n, problem.p), dtype=float)
    for task in reversed(problem.topo):
        if not problem.succ[task]:
            table[task] = problem.w[task]
            continue
        continuation = np.zeros(problem.p, dtype=float)
        for child in problem.succ[task]:
            child_tail = table[child] + problem.w[child]
            values = np.minimum(child_tail, child_tail.min() + problem.edges[task, child])
            continuation = np.maximum(continuation, values)
        table[task] = float(problem.w[task].mean()) + continuation
    return table


def bppts_ranks(problem: Problem, table: np.ndarray) -> np.ndarray:
    """Mean BPCM times the source's mean-compute/mean-outgoing-edge factor.

    The denominator is max(mean outgoing communication, 1), including fractional
    positive communication below 1. Sinks use factor 1. This interpretation is
    inherited from the existing source, not inferred afresh from the paper.
    """
    ranks = table.mean(axis=1)
    for task in range(problem.n):
        children = problem.succ[task]
        if children:
            mean_communication = sum(problem.edges[task, child] for child in children) / len(children)
            ranks[task] *= 1.0 + float(problem.w[task].mean()) / max(mean_communication, 1.0)
    return ranks


def _select_processor(
    finishes: np.ndarray, offsets: np.ndarray, *, bppts: bool, pure_eft: bool
) -> int:
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
                abs(score - best_score) <= 1e-9 and finishes[processor] < finishes[best]
            ):
                best = processor
        elif score < best_score:
            # AEFT deliberately has no EFT secondary comparison on a score tie.
            best = processor
    return best


def _schedule(
    problem: Problem, table: np.ndarray, ranks: np.ndarray, *, bppts: bool, insertion: bool
) -> Schedule:
    schedule = Schedule(problem, insertion=insertion)
    pure_eft_tasks = 0
    for task in ready_order(problem, ranks):
        starts, finishes = schedule.earliest_slots(task)
        pure_eft = len(problem.succ[task]) > problem.p
        processor = _select_processor(finishes, table[task], bppts=bppts, pure_eft=pure_eft)
        schedule.place(task, processor, slot=(float(starts[processor]), float(finishes[processor])))
        if task < problem.original_n and pure_eft:
            pure_eft_tasks += 1
    schedule.diagnostics.update(
        pure_eft_tasks=pure_eft_tasks,
        entry_is_dummy=problem.dummy_entry is not None,
    )
    return schedule


def run_aeft(problem: Problem, insertion: bool = True) -> Schedule:
    """AEFT-ref: mean IOCT priority and source-specific I_EFT selection."""
    table = aeft_ioct(problem)
    return _schedule(problem, table, table.mean(axis=1), bppts=False, insertion=insertion)


def run_bppts(problem: Problem, insertion: bool = True) -> Schedule:
    """BPPTS-ref: BPCM priority and tolerance-aware B_EFT selection."""
    table = bppts_bpcm(problem)
    return _schedule(problem, table, bppts_ranks(problem, table), bppts=True, insertion=insertion)
