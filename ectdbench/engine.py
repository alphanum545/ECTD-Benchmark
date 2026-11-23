"""Shared explicit-copy scheduling engine and independent feasibility checks."""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

import numpy as np

from .model import Problem


@dataclass(frozen=True)
class Execution:
    task: int
    processor: int
    start: float
    finish: float
    is_duplicate: bool = False


def ready_order(problem: Problem, ranks):
    """A static-priority topological order, with smaller task index on a tie."""
    ranks = np.asarray(ranks, dtype=float)
    if ranks.shape != (problem.n,) or not np.isfinite(ranks).all():
        raise ValueError("one finite rank is required per task")
    remaining = [len(x) for x in problem.pred]
    ready = [(-float(ranks[i]), i) for i in problem.topo if not remaining[i]]
    heapq.heapify(ready)
    count = 0
    while ready:
        _, task = heapq.heappop(ready)
        yield task
        count += 1
        for child in problem.succ[task]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, (-float(ranks[child]), child))
    if count != problem.n:
        raise ValueError("could not produce a precedence-safe ordering")


def optimistic_cost_table(problem: Problem):
    """Exact max-successor/min-processor OCT for scalar interprocessor costs.

    For a child tail t and communication c>=0, min_q(t[q]+c*[q!=p])
    equals min(t[p], min(t)+c). This reduces the direct O(e*p*p)
    recurrence to O(e*p), without changing the mathematical values.
    """
    oct_values = np.zeros((problem.n, problem.p), dtype=float)
    cps = np.full((problem.n, problem.p), -1, dtype=int)
    for task in reversed(problem.topo):
        best = np.full(problem.p, -np.inf)
        for child in problem.succ[task]:
            tail = problem.w[child] + oct_values[child]
            values = np.minimum(tail, tail.min() + problem.edges[task, child])
            update = values > best
            cps[task, update] = child
            best = np.maximum(best, values)
        if problem.succ[task]:
            oct_values[task] = best
    return oct_values, cps


class Schedule:
    def __init__(self, problem: Problem, insertion=True):
        self.problem = problem
        self.insertion = bool(insertion)
        self.events = [[] for _ in range(problem.p)]
        self.copies = {}
        self.primary = {}
        self.available = np.zeros(problem.p, dtype=float)
        self.selection_order = []
        self.diagnostics = {}

    def _ready_vector(self, task):
        ready = np.zeros(self.problem.p, dtype=float)
        for parent in self.problem.pred[task]:
            copies = self.copies.get(parent)
            if not copies:
                raise ValueError(f"task {task} selected before parent {parent}")
            delay = self.problem.edges[parent, task]
            arrival = np.full(self.problem.p, min(x.finish for x in copies) + delay)
            for copy in copies:
                arrival[copy.processor] = min(arrival[copy.processor], copy.finish)
            ready = np.maximum(ready, arrival)
        return ready

    def earliest_slots(self, task):
        starts = self._ready_vector(task)
        if not self.insertion:
            starts = np.maximum(starts, self.available)
        else:
            for processor, calendar in enumerate(self.events):
                duration = self.problem.w[task, processor]
                candidate = starts[processor]
                if duration == 0:
                    continue
                for event in calendar:
                    if candidate + duration <= event.start:
                        break
                    if candidate < event.finish:
                        candidate = event.finish
                starts[processor] = candidate
        return starts, starts + self.problem.w[task]

    def earliest_slot(self, task, processor):
        starts, finishes = self.earliest_slots(task)
        return float(starts[processor]), float(finishes[processor])

    def place(self, task, processor, duplicate=False, slot=None):
        if not 0 <= processor < self.problem.p:
            raise ValueError("invalid processor")
        if duplicate and task not in self.primary:
            raise ValueError("place the primary execution before its copies")
        if not duplicate and task in self.primary:
            raise ValueError("logical task has more than one primary execution")
        if any(e.processor == processor for e in self.copies.get(task, ())):
            raise ValueError("a second copy on the same processor is redundant")
        start, finish = self.earliest_slot(task, processor) if slot is None else slot
        start, finish = float(start), float(finish)
        if not math.isfinite(start) or not math.isfinite(finish) or start < 0:
            raise ValueError("invalid execution interval")
        expected_duration = float(self.problem.w[task, processor])
        if not math.isclose(finish - start, expected_duration, rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("execution interval does not match computation cost")
        event = Execution(task, processor, start, finish, bool(duplicate))
        calendar = self.events[processor]
        if not calendar or start >= calendar[-1].start:
            calendar.append(event)
        else:
            position = next(i for i, previous in enumerate(calendar) if previous.start > start)
            calendar.insert(position, event)
        self.available[processor] = max(self.available[processor], finish)
        self.copies.setdefault(task, []).append(event)
        if not duplicate:
            self.primary[task] = event
            self.selection_order.append(task)
        return event

    @property
    def makespan(self):
        """Completion of all logical tasks, as in the manuscript objective."""
        return max((event.finish for event in self.primary.values()), default=0.0)

    @property
    def execution_horizon(self):
        return max((event.finish for calendar in self.events for event in calendar), default=0.0)

    @property
    def duplicate_count(self):
        return sum(event.is_duplicate for calendar in self.events for event in calendar)

    @property
    def duplicate_work(self):
        return sum(event.finish - event.start for calendar in self.events for event in calendar if event.is_duplicate)

    def as_dict(self):
        return {"makespan": self.makespan, "execution_horizon": self.execution_horizon,
                "duplicate_count": self.duplicate_count, "duplicate_work": self.duplicate_work,
                "events": [[event.task, event.processor, event.start, event.finish, event.is_duplicate]
                           for calendar in self.events for event in calendar]}


def validate_schedule(problem: Problem, schedule: Schedule):
    """Check durations, completeness, resource occupancy, and every dependency.

    This checks the final execution records directly, independently of the
    engine's earliest-start calculation. Duplicate executions reserve real
    processor time, and all predecessor copies have their own finish times.
    """
    errors = []
    if set(schedule.primary) != set(range(problem.n)):
        errors.append("missing or extra primary task")
    seen = {}
    horizon = max(1.0, schedule.execution_horizon)
    tolerance = max(1e-8, 1e-12 * horizon)
    for processor, calendar in enumerate(schedule.events):
        previous_finish = 0.0
        for event in sorted(calendar, key=lambda x: (x.start, x.finish, x.task)):
            if event.processor != processor or not 0 <= event.task < problem.n:
                errors.append("event processor/task mismatch")
                continue
            if not math.isfinite(event.start) or not math.isfinite(event.finish):
                errors.append("nonfinite interval")
                continue
            if event.start < -tolerance or event.finish < event.start - tolerance:
                errors.append("negative execution interval")
            duration = event.finish - event.start
            if abs(duration - problem.w[event.task, processor]) > tolerance:
                errors.append("wrong computation duration")
            if duration > tolerance and event.start < previous_finish - tolerance:
                errors.append(f"processor overlap on {processor}")
            if duration > tolerance:
                previous_finish = max(previous_finish, event.finish)
            seen.setdefault(event.task, []).append(event)
    for task, executions in seen.items():
        for event in executions:
            for parent in problem.pred[task]:
                alternatives = seen.get(parent, ())
                if not alternatives:
                    errors.append("missing predecessor execution")
                    continue
                arrival = min(copy.finish + (0.0 if copy.processor == event.processor else problem.edges[parent, task])
                              for copy in alternatives)
                if event.start + tolerance < arrival:
                    errors.append(f"precedence/data-arrival violation on {parent}->{task}")
    for task, executions in seen.items():
        primary = [e for e in executions if not e.is_duplicate]
        if len(primary) != 1 or schedule.primary.get(task) != primary[0]:
            errors.append("primary execution bookkeeping mismatch")
        if len({e.processor for e in executions}) != len(executions):
            errors.append("duplicate task copies on a single processor")
    min_work = problem.w.min(axis=1)
    path_cost = np.zeros(problem.n)
    for task in reversed(problem.topo):
        path_cost[task] = min_work[task] + max((path_cost[c] for c in problem.succ[task]), default=0.0)
    lower_bound = max(float(min_work.sum() / problem.p), float(path_cost.max()))
    if schedule.makespan + tolerance < lower_bound:
        errors.append("makespan below a valid computation-only lower bound")
    duplicates = [e for values in seen.values() for e in values if e.is_duplicate]
    beneficial = 0
    for copy in duplicates:
        primary = schedule.primary[copy.task]
        for child in problem.succ[copy.task]:
            child_event = schedule.primary.get(child)
            if child_event is None:
                continue
            copy_arrival = copy.finish + problem.comm(copy.task, child, copy.processor, child_event.processor)
            primary_arrival = primary.finish + problem.comm(copy.task, child, primary.processor, child_event.processor)
            if copy_arrival + tolerance < primary_arrival and child_event.start + tolerance >= copy_arrival:
                beneficial += 1
                break
    return {"valid": not errors, "errors": sorted(set(errors)), "lower_bound": lower_bound,
            "duplicate_copies_improving_arrival": beneficial,
            "unused_or_nonbeneficial_copies": len(duplicates) - beneficial}
