"""Deterministic, precedence-safe makespan baseline policies.

Standard-library port of ``ectdbench/baselines.py``. These are clean
implementations of the documented policies, not executions of the legacy C++
programs. The shared engine selects either insertion scheduling (the default
here) or append-only scheduling explicitly. All methods use the SAME selected
placement model.

References:
  HEFT/CPOP: Topcuoglu, Hariri and Wu, TPDS 13(3), 2002.
  PEFT: Arabnejad and Barbosa, TPDS 25(3), 2014.
  IPPTS: Djigal et al., TPDS 32(5), 2021.
"""

from __future__ import annotations

from .engine import Schedule, optimistic_cost_table, ready_order


def upward_ranks(problem):
    """HEFT upward ranks with mean processor costs and scalar edge delays."""
    ranks = [0.0] * problem.n
    for task in reversed(problem.topo):
        ranks[task] = problem.avg_w[task] + max(
            (problem.edges[task, child] + ranks[child]
             for child in problem.succ[task]),
            default=0.0,
        )
    return ranks


def _run_policy(problem, ranks, offsets=None, forced=None, insertion=True):
    """Apply static ranks and per-processor look-ahead offsets to one engine."""
    result = Schedule(problem, insertion=insertion)
    forced = {} if forced is None else forced
    for task in ready_order(problem, ranks):
        starts, finishes = result.earliest_slots(task)
        processors = (forced[task],) if task in forced else range(problem.p)
        best = None
        for processor in processors:
            start, finish = float(starts[processor]), float(finishes[processor])
            offset = 0.0 if offsets is None else float(offsets[task][processor])
            candidate = (float(finish) + offset, float(finish), processor, start)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            raise ValueError("A scheduling problem must provide a processor")
        _, finish, processor, start = best
        result.place(task, processor, slot=(start, finish))
    return result


def run_heft(problem, insertion=True):
    """HEFT: mean-cost upward rank, then earliest finish time."""
    return _run_policy(problem, upward_ranks(problem), insertion=insertion)


def cpop_priorities_and_path(problem):
    """Return CPOP priorities, one deterministic critical path and its processor."""
    upward = upward_ranks(problem)
    downward = [0.0] * problem.n
    for task in problem.topo:
        for child in problem.succ[task]:
            candidate = downward[task] + problem.avg_w[task] + problem.edges[task, child]
            if candidate > downward[child]:
                downward[child] = candidate
    priorities = [upward[i] + downward[i] for i in range(problem.n)]
    current = problem.entry
    path = [current]
    while problem.succ[current]:
        current = min(problem.succ[current], key=lambda c: (-priorities[c], c))
        path.append(current)
    processor = min(range(problem.p),
                    key=lambda q: (sum(problem.w[t][q] for t in path), q))
    return priorities, tuple(path), processor


def run_cpop(problem, insertion=True):
    """CPOP: upward+downward ready priorities and a common critical processor."""
    priorities, path, processor = cpop_priorities_and_path(problem)
    return _run_policy(problem, priorities,
                       forced={task: processor for task in path},
                       insertion=insertion)


def run_peft(problem, insertion=True):
    """PEFT: mean optimistic continuation cost, then EFT+OCT."""
    oct_table, _ = optimistic_cost_table(problem)
    ranks = [sum(row) / problem.p for row in oct_table]
    return _run_policy(problem, ranks, offsets=oct_table, insertion=insertion)


def compute_ippts_pcm(problem):
    """Compute IPPTS's predicted-cost matrix without changing its recurrence."""
    p = problem.p
    pcm = [[0.0] * p for _ in range(problem.n)]
    for task in reversed(problem.topo):
        children = problem.succ[task]
        if not children:
            pcm[task] = list(problem.w[task])
            continue
        row = [0.0] * p
        for child in children:
            costs = [pcm[child][q] + problem.w[child][q] + problem.w[task][q]
                     for q in range(p)]
            low = min(costs)
            c = problem.edges[task, child]
            for q in range(p):
                value = min(costs[q], low + c)
                if value > row[q]:
                    row[q] = value
        pcm[task] = row
    return pcm


def run_ippts(problem, insertion=True):
    """IPPTS-ready: original PCM/rank/score with explicit precedence filtering."""
    pcm = compute_ippts_pcm(problem)
    ranks = [sum(pcm[i]) / problem.p * len(problem.succ[i]) for i in range(problem.n)]
    offsets = [[pcm[i][q] - problem.w[i][q] for q in range(problem.p)]
               for i in range(problem.n)]
    return _run_policy(problem, ranks, offsets=offsets, insertion=insertion)


BASELINES = {
    "HEFT": run_heft,
    "CPOP": run_cpop,
    "PEFT": run_peft,
    "IPPTS-ready": run_ippts,
}
