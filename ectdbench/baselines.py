"""Deterministic, precedence-safe makespan baseline policies.

These are clean implementations of the documented policies, not executions of
the legacy C++ programs.  The legacy programs append tasks only, round priorities,
and contain undefined-variable bugs (notably CPOP's critical-path rank).  The
shared engine selects either insertion scheduling (the default here) or append-
only scheduling explicitly.  All methods use the SAME selected placement model.

References:
  HEFT/CPOP: Topcuoglu, Hariri and Wu, TPDS 13(3), 2002.
             https://doi.org/10.1109/71.993206
  PEFT: Arabnejad and Barbosa, TPDS 25(3), 2014.
        https://doi.org/10.1109/TPDS.2013.57
  IPPTS: Djigal et al., TPDS 32(5), 2021.
         https://doi.org/10.1109/TPDS.2020.3041829
         Author implementation: https://github.com/Hamza-Djigal/
         IPPTS-An-efficient-algorithm-for-scientific-workflow-scheduling-in-heterogeneous-computing-systems
  IPPTS precedence ambiguity: Devaraj and Sarkar, TPDS 34(3), 2023.
                              https://doi.org/10.1109/TPDS.2022.3232326

The IPPTS variant is explicitly named IPPTS-ready: it retains PCM, rank and
processor score, but chooses only ready tasks.  It does not claim bitwise
equivalence to the original global-sort code or to the author's later priority
correction.  Ties for every method use (score, EFT, processor index), and task
priority ties use the common engine's task-index rule.  No algorithm is tuned
against the benchmark results.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .engine import Schedule, optimistic_cost_table, ready_order
from .model import Problem


def upward_ranks(problem: Problem) -> np.ndarray:
    """HEFT upward ranks with mean processor costs and scalar edge delays."""
    means = np.mean(problem.w, axis=1)
    ranks = np.zeros(problem.n, dtype=float)
    for task in reversed(problem.topo):
        ranks[task] = means[task] + max(
            (problem.edges[task, child] + ranks[child]
             for child in problem.succ[task]),
            default=0.0,
        )
    return ranks


def _run_policy(
    problem: Problem,
    ranks: Sequence[float],
    *,
    offsets: np.ndarray | None = None,
    forced: dict[int, int] | None = None,
    insertion: bool = True,
) -> Schedule:
    """Apply static ranks and per-processor look-ahead offsets to one engine."""
    result = Schedule(problem, insertion=insertion)
    forced = {} if forced is None else forced
    for task in ready_order(problem, ranks):
        starts, finishes = result.earliest_slots(task)
        processors = (forced[task],) if task in forced else range(problem.p)
        best = None
        for processor in processors:
            start, finish = float(starts[processor]), float(finishes[processor])
            offset = 0.0 if offsets is None else float(offsets[task, processor])
            candidate = (float(finish) + offset, float(finish), processor, start)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            raise ValueError("A scheduling problem must provide a processor")
        _, finish, processor, start = best
        result.place(task, processor, slot=(start, finish))
    return result


def run_heft(problem: Problem, insertion: bool = True) -> Schedule:
    """HEFT: mean-cost upward rank, then earliest finish time."""
    return _run_policy(problem, upward_ranks(problem), insertion=insertion)


def cpop_priorities_and_path(problem: Problem) -> tuple[np.ndarray, tuple[int, ...], int]:
    """Return CPOP priorities, one deterministic critical path and its processor.

    A tied collection of critical branches is not forced wholesale onto one
    processor: the original algorithm traces one critical path from the entry.
    The common Problem representation normalizes multiple entries with a dummy
    entry before this function is called.
    """
    upward = upward_ranks(problem)
    means = np.mean(problem.w, axis=1)
    downward = np.zeros(problem.n, dtype=float)
    for task in problem.topo:
        for child in problem.succ[task]:
            candidate = downward[task] + means[task] + problem.edges[task, child]
            downward[child] = max(downward[child], candidate)
    priorities = upward + downward
    current = problem.entry
    path = [current]
    while problem.succ[current]:
        current = min(problem.succ[current], key=lambda child: (-priorities[child], child))
        path.append(current)
    processor = int(np.argmin(np.sum(problem.w[path, :], axis=0)))
    return priorities, tuple(path), processor


def run_cpop(problem: Problem, insertion: bool = True) -> Schedule:
    """CPOP: upward+downward ready priorities and a common critical processor."""
    priorities, path, processor = cpop_priorities_and_path(problem)
    return _run_policy(
        problem,
        priorities,
        forced={task: processor for task in path},
        insertion=insertion,
    )


def run_peft(problem: Problem, insertion: bool = True) -> Schedule:
    """PEFT: mean optimistic continuation cost, then EFT+OCT."""
    oct_table, _ = optimistic_cost_table(problem)
    return _run_policy(
        problem,
        np.mean(oct_table, axis=1),
        offsets=oct_table,
        insertion=insertion,
    )


def compute_ippts_pcm(problem: Problem) -> np.ndarray:
    """Compute IPPTS's predicted-cost matrix without changing its recurrence.

    For edge i->j and current processor p, minimize over destination q:
      PCM[j,q] + w[j,q] + w[i,q] + (0 if p==q else c[i,j]).
    Then maximize over children.  A sink's PCM equals its execution-cost row.
    With scalar nonnegative cross-processor communication, the minimization is
    exactly min(local value, global minimum + c), reducing work to O(edges*p).
    """
    pcm = np.zeros_like(problem.w, dtype=float)
    for task in reversed(problem.topo):
        children = problem.succ[task]
        if not children:
            pcm[task, :] = problem.w[task, :]
            continue
        row = np.zeros(problem.p, dtype=float)
        for child in children:
            costs = pcm[child, :] + problem.w[child, :] + problem.w[task, :]
            best_per_source = np.minimum(costs, float(np.min(costs)) + problem.edges[task, child])
            np.maximum(row, best_per_source, out=row)
        pcm[task, :] = row
    return pcm


def run_ippts(problem: Problem, insertion: bool = True) -> Schedule:
    """IPPTS-ready: original PCM/rank/score with explicit precedence filtering."""
    pcm = compute_ippts_pcm(problem)
    degrees = np.fromiter((len(children) for children in problem.succ), dtype=float)
    ranks = np.mean(pcm, axis=1) * degrees
    # Do not clip LHET: PCM-w can be negative on a particularly slow processor
    # in the published optimistic recurrence.  Clipping would change the policy.
    return _run_policy(problem, ranks, offsets=pcm - problem.w, insertion=insertion)


BASELINES = {
    "HEFT": run_heft,
    "CPOP": run_cpop,
    "PEFT": run_peft,
    "IPPTS-ready": run_ippts,
}
