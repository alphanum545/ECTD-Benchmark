"""Seeded workflow instance generator with four structurally distinct families.

Every instance is a deterministic function of its seed and family. The four
families reproduce the canonical DAG topologies used in workflow-scheduling
benchmarks, and each instance carries a structural signature that is checked
against the family's canonical form by ``validate_structure``.

Families
--------
FFT      Fast Fourier Transform: layers of 2^k tasks, butterfly edges
         (outdegree 2), the canonical layered-communication workload.
GE       Gaussian elimination: the triangular task graph of matrix elimination,
         n = m(m-1)/2, edges (i,j)->(i,j+1) and (i,j)->(i+1,j).
Genome   Gene sequencing: a wide independent first stage, a dependent second
         stage, and a reduction tail. High parallelism, shallow depth.
LA       Linear algebra: irregular layered graph with a declared layer count and
         variable outdegree, the least regular of the four.

Size
----
Every family is parameterised by a target node count. FFT and GE are quantised
by their structure (FFT to multiples of its width, GE to triangular numbers);
Genome and LA are close to continuous. The finished instance, including the
entry and exit super-nodes, is always inside ``NODE_RANGE``.

Groups (structural motifs layered on the base topology)
------------------------------------------------------
plain            the family topology with no added motif
entry_transfer   several real roots with heavy entry-to-successor communication,
                 which is what makes entry duplication worth anything
branch_affinity  a high-outdegree node whose children all prefer one processor,
                 which is what makes critical-path weighting worth anything
lookahead_traps  a node that is locally cheapest on one processor while its
                 successors are only fast on another, an optimistic-cost trap
mixed_affinity   entry_transfer and branch_affinity applied together
"""

from __future__ import annotations

import hashlib
import json
import math
import random

FAMILIES = ("FFT", "GE", "Genome", "LA")
GROUPS = ("plain", "entry_transfer", "branch_affinity", "lookahead_traps", "mixed_affinity")

# The suite spans these ranges. Every generated instance is checked against them.
NODE_RANGE = (50, 500)
PROCESSOR_RANGE = (4, 64)

# Processor counts are drawn from this ladder rather than uniformly, so the
# suite covers the small- and large-machine regimes evenly instead of piling up
# in the middle of the range.
PROCESSOR_CHOICES = (4, 6, 8, 12, 16, 24, 32, 48, 64)


def _hex12(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _costs(rng, n, p, base_low, base_high, het_low, het_high):
    """Task costs with a task-specific base and a processor-specific speed factor."""
    costs = []
    for _ in range(n):
        base = rng.uniform(base_low, base_high)
        row = [round(base * rng.uniform(het_low, het_high), 4) for _ in range(p)]
        costs.append(row)
    return costs


def _fft(rng, p, target_n):
    """Butterfly FFT: layers of 2^k tasks, outdegree 2 within and across layers.

    The width is a power of two and the layer count is chosen so that
    ``width * layers`` lands as close to ``target_n`` as the family allows. When
    there are more layers than butterfly stages the stride cycles, which keeps
    the graph a valid layered DAG with outdegree at most 2.
    """
    best = None
    for k in (4, 5, 6):
        width = 1 << k
        layers = int(round(float(target_n) / width))
        layers = max(k + 1, min(layers, NODE_RANGE[1] // width))
        n = width * layers
        score = (abs(n - target_n), k)
        if best is None or score < best[0]:
            best = (score, k, width, layers, n)
    _, k, width, layers, n = best
    edges = []
    for layer in range(layers - 1):
        stride = 1 << ((k - 1 - layer) % k)
        for i in range(width):
            src = layer * width + i
            edges.append((src, (layer + 1) * width + i))
            partner = i ^ stride
            if partner != i:
                edges.append((src, (layer + 1) * width + partner))
    costs = _costs(rng, n, p, 8.0, 40.0, 0.6, 1.6)
    meta = {"family": "FFT", "k": k, "layers": layers, "width": width}
    return costs, edges, meta


def _ge(rng, p, target_n):
    """Gaussian elimination: triangular task graph, n = m(m-1)/2."""
    m = int(round((1.0 + math.sqrt(1.0 + 8.0 * target_n)) / 2.0))
    m = max(11, min(m, 32))
    index = {}
    tasks = []
    for i in range(m):
        for j in range(i + 1, m):
            index[(i, j)] = len(tasks)
            tasks.append((i, j))
    edges = []
    for (i, j), src in index.items():
        if (i, j + 1) in index:
            edges.append((src, index[(i, j + 1)]))
        if (i + 1, j) in index and i + 1 < j:
            edges.append((src, index[(i + 1, j)]))
    costs = _costs(rng, len(tasks), p, 10.0, 45.0, 0.6, 1.6)
    meta = {"family": "GE", "m": m, "layers": m - 1}
    return costs, edges, meta


def _genome(rng, p, target_n):
    """Gene sequencing: wide independent stage, dependent stage, reduction tail."""
    tail = rng.choice((3, 4, 5, 6))
    width = int(round((target_n - tail) / 2.0))
    width = max(22, min(width, (NODE_RANGE[1] - 2 - tail) // 2))
    stage1 = width
    stage2 = width
    n = stage1 + stage2 + tail
    edges = []
    for j in range(stage2):
        src = stage1 + j
        # each stage-2 task depends on a contiguous window of stage-1 tasks
        span = rng.choice((2, 3, 4))
        start = (j * width) // stage2
        for offset in range(span):
            edges.append(((start + offset) % stage1, src))
    tail_start = stage1 + stage2
    for t in range(tail):
        for j in range(stage2):
            if (j + t) % 3 == 0:
                edges.append((stage1 + j, tail_start + t))
    for t in range(tail - 1):
        edges.append((tail_start + t, tail_start + t + 1))
    costs = _costs(rng, n, p, 6.0, 30.0, 0.5, 1.8)
    meta = {"family": "Genome", "width": width, "layers": 3, "tail": tail}
    return costs, edges, meta


def _la(rng, p, target_n):
    """Irregular layered linear-algebra graph with variable outdegree."""
    best = None
    for per_layer in (10, 12, 14, 16, 18, 20, 22, 24, 25):
        layers = int(round(float(target_n) / per_layer))
        layers = max(5, min(layers, NODE_RANGE[1] // per_layer))
        n = layers * per_layer
        score = (abs(n - target_n), per_layer)
        if best is None or score < best[0]:
            best = (score, layers, per_layer, n)
    _, layers, per_layer, n = best
    edges = []
    for layer in range(layers - 1):
        for i in range(per_layer):
            src = layer * per_layer + i
            fanout = rng.choice((1, 1, 2, 2, 3))
            targets = rng.sample(range(per_layer), min(fanout, per_layer))
            for t in targets:
                edges.append((src, (layer + 1) * per_layer + t))
    # guarantee every node has a path forward: connect any orphan to the next layer
    has_child = {u for u, _ in edges}
    for layer in range(layers - 1):
        for i in range(per_layer):
            src = layer * per_layer + i
            if src not in has_child:
                edges.append((src, (layer + 1) * per_layer + rng.randrange(per_layer)))
    costs = _costs(rng, n, p, 8.0, 50.0, 0.5, 1.9)
    meta = {"family": "LA", "layers": layers, "per_layer": per_layer}
    return costs, edges, meta


_BUILDERS = {"FFT": _fft, "GE": _ge, "Genome": _genome, "LA": _la}


def _apply_group(rng, costs, edges, group, p):
    """Layer a structural motif onto the base topology, preserving acyclicity."""
    if group == "plain":
        return costs, edges

    triples = _as_triples(edges)

    if group in ("entry_transfer", "mixed_affinity"):
        # Make entry->child communication heavy, so that a local entry copy can
        # actually beat a remote arrival. Without this the duplication term has
        # nothing to buy and the motif is inert.
        roots = sorted({u for u, _, _ in triples} - {v for _, v, _ in triples})
        heavy = set(rng.sample(roots, min(2, len(roots)))) if roots else set()
        triples = [(u, v, round(c * rng.uniform(6.0, 12.0), 4) if u in heavy else c)
                   for (u, v, c) in triples]

    if group in ("branch_affinity", "mixed_affinity"):
        # A wide-fanout node whose children all prefer one processor.
        fanout = {u: 0 for u, _, _ in triples}
        for u, _, _ in triples:
            fanout[u] += 1
        if fanout:
            hub = max(sorted(fanout), key=lambda u: (fanout[u], -u))
            preferred = rng.randrange(p)
            for child in {v for u, v, _ in triples if u == hub}:
                for q in range(p):
                    if q != preferred:
                        costs[child][q] = round(costs[child][q] * rng.uniform(2.2, 3.4), 4)
                costs[child][preferred] = round(costs[child][preferred] * 0.55, 4)

    if group == "lookahead_traps":
        # A node locally cheapest on one processor whose successors are only
        # fast on another: greedy EFT takes the bait, look-ahead does not.
        fanout = {}
        for u, _, _ in triples:
            fanout[u] = fanout.get(u, 0) + 1
        candidates = [u for u in sorted(fanout) if fanout[u] >= 2]
        if candidates:
            trap = candidates[rng.randrange(len(candidates))]
            bait = rng.randrange(p)
            real = (bait + 1 + rng.randrange(p - 1)) % p
            for q in range(p):
                if q != bait:
                    costs[trap][q] = round(costs[trap][q] * rng.uniform(2.0, 3.0), 4)
            costs[trap][bait] = round(costs[trap][bait] * 0.5, 4)
            for child in {v for u, v, _ in triples if u == trap}:
                for q in range(p):
                    if q != real:
                        costs[child][q] = round(costs[child][q] * rng.uniform(2.0, 3.0), 4)
                costs[child][real] = round(costs[child][real] * 0.5, 4)
            triples = [(u, v, round(c * 1.5, 4) if u == trap else c)
                       for (u, v, c) in triples]

    return costs, triples


def _as_triples(edges):
    out = []
    for e in edges:
        if len(e) == 3:
            out.append((int(e[0]), int(e[1]), float(e[2])))
        else:
            out.append((int(e[0]), int(e[1]), 0.0))
    return out


def _augment_endpoints(costs, triples):
    """Give the graph exactly one entry task and one exit task.

    Real workflow DAGs (Montage, CyberShake, Inspiral, Sipht, Epigenomics) and
    the canonical FFT and Gaussian-elimination graphs have a single entry and a
    single exit. A graph with many roots is not that shape, and it also disables
    entry duplication: ``Problem`` normalises a multi-root graph by inserting a
    zero-cost dummy entry, and a dummy entry has nothing to duplicate.

    A real entry task is prepended to fan out to every former root, and a real
    exit task is appended to collect every former sink. Both carry the mean
    execution cost of the graph, so they are genuine tasks, not padding.

    Returns (costs, triples, info) where info records what was added, so the
    structural validator can check the base topology rather than the augmented
    graph.
    """
    n = len(costs)
    p = len(costs[0])
    roots = sorted({u for u, _, _ in triples} - {v for _, v, _ in triples})
    sinks = sorted({v for _, v, _ in triples} - {u for u, _, _ in triples})
    isolated = [i for i in range(n)
                if i not in {u for u, _, _ in triples}
                and i not in {v for _, v, _ in triples}]
    if len(roots) <= 1 and len(sinks) <= 1 and not isolated:
        return costs, triples, {"base_n": n, "entry_added": False, "exit_added": False}

    mean_cost = sum(sum(row) / p for row in costs) / n
    need_entry = len(roots) > 1 or bool(isolated)
    need_exit = len(sinks) > 1 or bool(isolated)
    shift = 1 if need_entry else 0

    new_costs = []
    if need_entry:
        new_costs.append([round(mean_cost, 4)] * p)
    new_costs.extend(costs)
    if need_exit:
        new_costs.append([round(mean_cost, 4)] * p)

    new_triples = [(u + shift, v + shift, c) for u, v, c in triples]
    if need_entry:
        for root in roots:
            new_triples.append((0, root + shift, 0.0))
        for node in isolated:
            new_triples.append((0, node + shift, 0.0))
    if need_exit:
        exit_node = len(new_costs) - 1
        for sink in sinks:
            new_triples.append((sink + shift, exit_node, 0.0))
        for node in isolated:
            new_triples.append((node + shift, exit_node, 0.0))
    return new_costs, new_triples, {
        "base_n": n, "entry_added": need_entry, "exit_added": need_exit}


def _assign_communication(rng, triples, comm_low, comm_high):
    """Fill in scalar edge communication delays where the motif did not set one."""
    result = []
    for u, v, c in triples:
        if c == 0.0:
            c = round(rng.uniform(comm_low, comm_high), 4)
        result.append((u, v, c))
    return result


def _content_hash(costs, triples):
    payload = json.dumps(
        {"costs": costs, "edges": sorted(triples)}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_instance(family, group, seed, processors=None, nodes=None):
    """Build one instance deterministically from (family, group, seed).

    The base topology is drawn from a seed that depends only on
    (family, seed), so every group of the same family and seed shares the same
    node count, processor count and edge set. The group motif is then applied
    from a separate stream. That keeps a group comparison controlled: the motif
    is the only thing that changes between two instances of the same family and
    seed.

    ``nodes`` is the target node count for the finished instance. Families that
    are quantised by their structure (FFT, GE) land on the nearest shape their
    topology allows; the achieved count is always inside ``NODE_RANGE``.
    """
    if family not in _BUILDERS:
        raise ValueError("unknown family %r" % (family,))
    if group not in GROUPS:
        raise ValueError("unknown group %r" % (group,))

    base_rng = random.Random("%s|base|%d" % (family, seed))
    # Node count and processor count are drawn from the same base stream that
    # the family topology uses, so every group of one (family, seed) shares
    # them and a group comparison differs only in the motif.
    if processors is None:
        processors = base_rng.choice(PROCESSOR_CHOICES)
    p = max(PROCESSOR_RANGE[0], min(processors, PROCESSOR_RANGE[1]))
    if nodes is None:
        nodes = base_rng.randint(NODE_RANGE[0], NODE_RANGE[1])
    # Reserve room for the entry and exit super-nodes so the finished instance,
    # not just the base topology, lands inside NODE_RANGE.
    target_n = max(NODE_RANGE[0] - 2, min(nodes, NODE_RANGE[1] - 2))
    costs, edges, meta = _BUILDERS[family](base_rng, p, target_n)

    # One real entry and one real exit, as in the canonical workflow graphs.
    costs, edges, endpoint_info = _augment_endpoints(costs, _as_triples(edges))
    meta = dict(meta)
    meta.update(endpoint_info)
    meta["entry"] = 0
    meta["exit"] = len(costs) - 1

    group_rng = random.Random("%s|%s|%d" % (family, group, seed))
    # Communication delays are assigned BEFORE the motif is layered on. The
    # motifs scale existing delays (entry_transfer multiplies entry edges by
    # 6-12x), so applying a motif to the 0.0 placeholders the base topology
    # carries would multiply zero and leave the motif inert.
    triples = _assign_communication(group_rng, _as_triples(edges), 1.0, 20.0)
    costs, triples = _apply_group(group_rng, costs, triples, group, p)
    triples = _as_triples(triples)

    digest = _content_hash(costs, triples)
    structure = _hex12(json.dumps(meta, sort_keys=True))
    instance_id = "synthetic/%s/%s/%s/seed_%d-%s" % (
        family, structure, group, seed, digest[:12])

    return {
        "id": instance_id,
        "family": family,
        "group": group,
        "seed": seed,
        "n": len(costs),
        "p": p,
        "costs": costs,
        "edges": [[u, v, c] for u, v, c in triples],
        "input_sha256": digest,
        "structure": meta,
    }


def validate_structure(instance):
    """Check that the instance is a well-formed DAG matching its family signature.

    Returns a dict of structural facts plus a list of problems. An empty problem
    list means the DAG is acyclic, fully connected, and has the canonical layer
    and degree shape its family declares.
    """
    problems = []
    n = instance["n"]
    triples = instance["edges"]
    costs = instance["costs"]

    if len(costs) != n:
        problems.append("cost row count does not match n")
    if any(len(row) != instance["p"] for row in costs):
        problems.append("cost matrix is not n by p")
    if any(v < 0 for row in costs for v in row):
        problems.append("negative execution cost")

    succ = [[] for _ in range(n)]
    pred = [[] for _ in range(n)]
    for u, v, c in triples:
        if not (0 <= u < n and 0 <= v < n):
            problems.append("edge out of range: %d->%d" % (u, v))
            continue
        if u == v:
            problems.append("self loop at %d" % u)
        if c < 0:
            problems.append("negative communication on %d->%d" % (u, v))
        succ[u].append(v)
        pred[v].append(u)

    # Kahn topological sort: a cycle leaves nodes unvisited.
    indegree = [len(x) for x in pred]
    queue = [i for i, d in enumerate(indegree) if d == 0]
    seen = 0
    while queue:
        u = queue.pop()
        seen += 1
        for v in succ[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if seen != n:
        problems.append("graph contains a cycle (%d of %d reachable)" % (seen, n))

    roots = [i for i in range(n) if not pred[i]]
    sinks = [i for i in range(n) if not succ[i]]
    if not roots:
        problems.append("no entry task")
    if not sinks:
        problems.append("no exit task")

    # Connectivity: every node reachable from some root.
    reach = set(roots)
    stack = list(roots)
    while stack:
        u = stack.pop()
        for v in succ[u]:
            if v not in reach:
                reach.add(v)
                stack.append(v)
    if len(reach) != n:
        problems.append("%d tasks unreachable from any root" % (n - len(reach)))

    outdeg = [len(x) for x in succ]
    indeg = [len(x) for x in pred]
    family = instance["family"]
    structure = instance.get("structure", {})

    # Family shape is a property of the base topology. The synthetic entry and
    # exit added by _augment_endpoints are super-nodes: the entry legitimately
    # fans out to every former root and the exit collects every former sink, so
    # they are excluded from the degree checks and from the node-count checks.
    base_n = structure.get("base_n", n)
    entry_added = structure.get("entry_added", False)
    exit_added = structure.get("exit_added", False)
    offset = 1 if entry_added else 0
    base_nodes = range(offset, offset + base_n)
    base_outdeg = [outdeg[i] for i in base_nodes]

    if family == "FFT":
        k = structure.get("k")
        layers = structure.get("layers")
        if k is not None and layers is not None:
            if base_n != (1 << k) * layers:
                problems.append(
                    "FFT base node count does not match k=%d, layers=%d" % (k, layers))
            if base_outdeg and max(base_outdeg) > 2:
                problems.append("FFT base outdegree exceeds 2")
    if family == "GE":
        m = structure.get("m")
        if m is not None and base_n != m * (m - 1) // 2:
            problems.append("GE base node count does not match m=%d" % m)
    if family == "Genome":
        # The reduction tail is a reduction: it is supposed to have many
        # parents. The declared window constrains the dependent stage only.
        width = structure.get("width")
        if width is not None:
            stage2 = range(offset + width, min(offset + 2 * width, n))
            worst = max((indeg[i] for i in stage2), default=0)
            if worst > 4:
                problems.append("Genome stage-2 indegree exceeds the declared window")
    if family == "LA":
        layers = structure.get("layers")
        per_layer = structure.get("per_layer")
        if layers and per_layer and base_n != layers * per_layer:
            problems.append("LA base node count does not match layers*per_layer")

    # The augmented graph must still have exactly one entry and one exit.
    if len(roots) != 1:
        problems.append("expected one entry task, found %d" % len(roots))
    if len(sinks) != 1:
        problems.append("expected one exit task, found %d" % len(sinks))

    # Declared suite ranges. These are the contract the suite advertises, so
    # they are checked per instance rather than assumed.
    if not (NODE_RANGE[0] <= n <= NODE_RANGE[1]):
        problems.append("node count %d outside declared range %s" % (n, NODE_RANGE))
    if not (PROCESSOR_RANGE[0] <= instance["p"] <= PROCESSOR_RANGE[1]):
        problems.append("processor count %d outside declared range %s"
                        % (instance["p"], PROCESSOR_RANGE))

    return {
        "valid": not problems,
        "problems": problems,
        "n": n,
        "p": instance["p"],
        "edges": len(triples),
        "roots": len(roots),
        "sinks": len(sinks),
        "max_outdegree": max(outdeg) if outdeg else 0,
        "max_indegree": max(indeg) if indeg else 0,
        "mean_outdegree": round(sum(outdeg) / n, 4) if n else 0.0,
        "depth": _depth(succ, roots, n),
    }


def _depth(succ, roots, n):
    """Longest path in edges from any root, by topological relaxation."""
    order = []
    indegree = [0] * n
    for u in range(n):
        for v in succ[u]:
            indegree[v] += 1
    queue = [i for i, d in enumerate(indegree) if d == 0]
    while queue:
        u = queue.pop()
        order.append(u)
        for v in succ[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    dist = {r: 0 for r in roots}
    for u in order:
        if u in dist:
            for v in succ[u]:
                if dist.get(v, -1) < dist[u] + 1:
                    dist[v] = dist[u] + 1
    return max(dist.values()) if dist else 0
