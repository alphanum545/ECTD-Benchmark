"""Common, validated DAG and fully heterogeneous processing-time model.

Standard-library port of ``ectdbench/model.py`` from the research branch
``research/ranking-revision-2026-11-23``. NumPy arrays are replaced by nested
lists; the semantics, validation and normalisation rules are unchanged.

A ``Problem`` is a DAG with nonnegative execution times ``w[i][p]`` and scalar
cross-processor communication delays ``edges[(u, v)]``. If several real entry
tasks exist, a zero-cost, zero-communication dummy entry is appended.
"""

from __future__ import annotations

import heapq


class Problem:
    """A DAG with nonnegative execution times and scalar cross-processor delays."""

    def __init__(self, w, edges, task_ids=None, name="", metadata=None,
                 normalize_entry=True):
        costs = [[float(v) for v in row] for row in w]
        if not costs or not costs[0]:
            raise ValueError("costs must be a nonempty n by p matrix")
        p = len(costs[0])
        for row in costs:
            if len(row) != p:
                raise ValueError("costs must be an n by p matrix")
            for v in row:
                if v != v or v < 0 or v == float("inf"):
                    raise ValueError("execution times must be finite and nonnegative")

        self.original_n = len(costs)
        self.p = p
        self.name = name
        self.metadata = dict(metadata or {})

        ids = list(task_ids if task_ids is not None else range(self.original_n))
        if len(ids) != self.original_n or len({str(x) for x in ids}) != len(ids):
            raise ValueError("task identifiers must be unique and match n")

        edge_map = {}
        if isinstance(edges, dict):
            items = edges.items()
        else:
            items = (((u, v), c) for u, v, c in edges)
        for (u, v), c in items:
            u, v, c = int(u), int(v), float(c)
            if not (0 <= u < self.original_n and 0 <= v < self.original_n) or u == v:
                raise ValueError("invalid edge (%d, %d)" % (u, v))
            if c != c or c < 0 or c == float("inf"):
                raise ValueError("edge communication must be finite and nonnegative")
            if (u, v) in edge_map and edge_map[u, v] != c:
                raise ValueError("conflicting duplicate edge")
            edge_map[u, v] = c

        has_parent = {v for _, v in edge_map}
        self.real_roots = tuple(i for i in range(self.original_n) if i not in has_parent)
        self.dummy_entry = None
        if normalize_entry and len(self.real_roots) > 1:
            self.dummy_entry = self.original_n
            costs.append([0.0] * p)
            ids.append("__ectd_dummy_entry__")
            for root in self.real_roots:
                edge_map[self.dummy_entry, root] = 0.0

        self.w = costs
        self.n = len(costs)
        self.task_ids = tuple(ids)
        self.edges = edge_map

        pred = [[] for _ in range(self.n)]
        succ = [[] for _ in range(self.n)]
        for (u, v) in sorted(edge_map):
            succ[u].append(v)
            pred[v].append(u)
        self.pred = tuple(tuple(x) for x in pred)
        self.succ = tuple(tuple(x) for x in succ)

        indegree = [len(x) for x in pred]
        queue = [i for i, d in enumerate(indegree) if d == 0]
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
        self.avg_w = [sum(row) / p for row in self.w]
        self.min_w = [min(row) for row in self.w]

    def comm(self, parent, child, source, destination):
        return 0.0 if source == destination else self.edges[parent, child]

    @classmethod
    def from_record(cls, record):
        return cls(
            record["costs"],
            record["edges"],
            name=record.get("id", ""),
            metadata={k: v for k, v in record.items() if k not in {"costs", "edges"}},
        )

    def to_record(self):
        return {
            "id": self.name,
            "costs": [[round(v, 6) for v in row] for row in self.w[: self.original_n]],
            "edges": sorted(
                [int(u), int(v), round(float(c), 6)]
                for (u, v), c in self.edges.items()
                if u < self.original_n and v < self.original_n
            ),
            "n": self.original_n,
            "p": self.p,
            "metadata": self.metadata,
        }
