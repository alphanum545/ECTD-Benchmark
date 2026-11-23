"""Common, validated DAG and fully heterogeneous processing-time model."""
from __future__ import annotations

import heapq
from typing import Mapping, Sequence

import numpy as np


class Problem:
    """A DAG with nonnegative execution times and scalar cross-processor delays.

    Indices in the source data are preserved. If several real entry tasks exist,
    a zero-cost, zero-communication dummy entry is appended. Entry-only
    duplication is therefore ineffective on a normalized multi-entry workflow;
    it is never silently extended to all real roots.
    """

    def __init__(self, w, edges, task_ids=None, name="", metadata=None,
                 normalize_entry=True):
        costs = np.array(w, dtype=np.float64, copy=True)
        if costs.ndim != 2 or not all(costs.shape):
            raise ValueError("costs must be a nonempty n by p matrix")
        if not np.isfinite(costs).all() or (costs < 0).any():
            raise ValueError("execution times must be finite and nonnegative")
        self.original_n, self.p = costs.shape
        self.name = name
        self.metadata = dict(metadata or {})
        ids = list(task_ids if task_ids is not None else range(self.original_n))
        if len(ids) != self.original_n or len(set(map(str, ids))) != len(ids):
            raise ValueError("task identifiers must be unique and match n")
        edge_map = {}
        items = (((u, v), c) for u, v, c in edges) if not isinstance(edges, Mapping) else edges.items()
        for (u, v), c in items:
            u, v, c = int(u), int(v), float(c)
            if not (0 <= u < self.original_n and 0 <= v < self.original_n) or u == v:
                raise ValueError(f"invalid edge {(u, v)}")
            if not np.isfinite(c) or c < 0:
                raise ValueError("edge communication must be finite and nonnegative")
            if (u, v) in edge_map and edge_map[u, v] != c:
                raise ValueError("conflicting duplicate edge")
            edge_map[u, v] = c
        has_parent = {v for _, v in edge_map}
        self.real_roots = tuple(i for i in range(self.original_n) if i not in has_parent)
        self.dummy_entry = None
        if normalize_entry and len(self.real_roots) > 1:
            self.dummy_entry = self.original_n
            costs = np.vstack((costs, np.zeros((1, self.p))))
            ids.append("__ectd_dummy_entry__")
            for root in self.real_roots:
                edge_map[self.dummy_entry, root] = 0.0
        self.w = costs
        self.w.flags.writeable = False
        self.n = len(costs)
        self.task_ids = tuple(ids)
        self.edges = edge_map
        pred, succ = [[] for _ in range(self.n)], [[] for _ in range(self.n)]
        for (u, v) in sorted(edge_map):
            succ[u].append(v)
            pred[v].append(u)
        self.pred = tuple(tuple(x) for x in pred)
        self.succ = tuple(tuple(x) for x in succ)
        indegree = [len(x) for x in pred]
        queue = [i for i, degree in enumerate(indegree) if degree == 0]
        heapq.heapify(queue)
        topo = []
        while queue:
            u = heapq.heappop(queue)
            topo.append(u)
            for v in succ[u]:
                indegree[v] -= 1
                if not indegree[v]:
                    heapq.heappush(queue, v)
        if len(topo) != self.n:
            raise ValueError("input graph contains a cycle")
        self.topo = tuple(topo)
        roots = tuple(i for i in self.topo if not self.pred[i])
        self.entry = roots[0]
        self.exit_tasks = tuple(i for i in self.topo if not self.succ[i])
        self.avg_w = self.w.mean(axis=1)
        self.min_w = self.w.min(axis=1)

    def comm(self, parent: int, child: int, source: int, destination: int) -> float:
        return 0.0 if source == destination else self.edges[parent, child]

    @classmethod
    def from_record(cls, record):
        return cls(record["costs"], record["edges"], name=record["id"], metadata={
            key: value for key, value in record.items() if key not in {"costs", "edges"}
        })

