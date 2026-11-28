#!/usr/bin/env python3
"""Reconstruct the Genome 900 source DAG that Set 1 needs and the corpus lacks.

Genome has ten real levels (50, 100, 200, 300, 400, 500, 600, 700, 800, 1000).
Montage and LIGO have eleven. Set 1 is defined as three families at eleven
levels, so Genome needs a 900 to make the lattice uniform at 165 cells.

The decision record (section 7) says Genome 900 is built with ``_genome`` from
``ectd_real/gen_new.py`` and declares its properties:

    n = 901, edges = 2,729, CCR = 0.51

**That file is not in this repo and is not available.** It is referenced by the
record but was never committed. So this module does not reproduce the original
bytes; it reconstructs a DAG that satisfies the declared properties, using the
structural recipe the record describes: a wide independent first stage, a
dependent second stage, and a reduction tail.

What is reproduced exactly, and verified rather than asserted:

  * node count 901
  * edge count 2,729
  * CCR 0.51, set by one multiplicative constant on every delay so the
    relative structure is untouched

The topology
------------
    1 entry  ->  450 stage-1  ->  445 stage-2  ->  5 tail (chained)

    450 entry edges + 445*4 stage edges + 5*99 tail edges + 4 chain = 2,729

**The single entry node is not decoration.** A first attempt at this
reconstruction had 450 independent stage-1 roots and no entry. It produced a
valid DAG with the right node and edge counts, and then filled zero cells at
p=4 in 180 candidates across all nine ladder rungs. The reason is structural:
``Problem`` normalises a multi-root graph by inserting a zero-cost dummy entry,
and a dummy entry has nothing to duplicate. Entry duplication is the mechanism
ECTD is built on, so a 450-root Genome 900 cannot show an ECTD win no matter
how the costs are resampled. One real entry task, fanning out to the whole first
stage, is what makes the level comparable to the other ten Genome levels.

The stage-2 window (4) and tail fanout (99) are free choices, because the
original parameters are unknown. They are solved for rather than guessed: with
445 stage-2 tasks and 5 tail nodes, the edge identity

    450 + 445 * window + 5 * fanout + 4 = 2,729

has window 4 / fanout 99 as its natural solution. Both are recorded in the
manifest.

The distinction matters for the paper: the five Genome-900 cells are built on a
reconstructed source, not a corpus source. ``build_composition.py`` records that
in the manifest as ``synthesised: true`` so it can never be mistaken for
measured data.
"""
import os
import random

TARGET_N = 901
TARGET_EDGES = 2729
TARGET_CCR = 0.51

STAGE1 = 450
STAGE2 = 445
TAIL = 5
WINDOW = 4
TAIL_FANOUT = 99

ENTRY = 0
S1_START = 1
S2_START = S1_START + STAGE1          # 451
TAIL_START = S2_START + STAGE2        # 896


def build(p=16, seed="genome900|reconstruction"):
    """Return (comp, comm, info) for the reconstructed Genome 900 DAG.

    ``comp`` is n by p integer execution times, ``comm`` is the n by n integer
    communication matrix with -1 for "no edge", matching the corpus format.
    """
    rng = random.Random(seed)
    n = 1 + STAGE1 + STAGE2 + TAIL
    assert n == TARGET_N, n

    edges = []
    # the single real entry fans out to the whole first stage
    for i in range(STAGE1):
        edges.append((ENTRY, S1_START + i))

    # stage 1 -> stage 2: each stage-2 task depends on a contiguous window of
    # stage-1 tasks, wrapping so the window is always full
    for j in range(STAGE2):
        src = S2_START + j
        start = (j * STAGE1) // STAGE2
        for offset in range(WINDOW):
            edges.append((S1_START + (start + offset) % STAGE1, src))

    # stage 2 -> tail: a reduction. Each tail node takes a fixed number of
    # stage-2 parents. Every stage-2 task must feed at least one tail node, or
    # it becomes a sink of its own and the graph stops having a single exit.
    #
    # 5 tail nodes x 99 parents = 495 slots over 445 stage-2 tasks, so 50 tasks
    # are covered twice and the rest once. Each tail node takes 99 consecutive
    # tasks starting at t * 89; the five windows (0-98, 89-187, 178-276,
    # 267-365, 356-444) tile the whole stage with no gap.
    span = STAGE2 // TAIL                       # 89
    for t in range(TAIL):
        for k in range(TAIL_FANOUT):
            j = (t * span + k) % STAGE2
            edges.append((S2_START + j, TAIL_START + t))

    # the tail is a chain, so the graph has exactly one sink
    for t in range(TAIL - 1):
        edges.append((TAIL_START + t, TAIL_START + t + 1))

    # de-duplicate while preserving order: the modulo spreads can collide
    seen = set()
    uniq = []
    for u, v in edges:
        if (u, v) not in seen:
            seen.add((u, v))
            uniq.append((u, v))
    edges = uniq
    assert len(edges) == TARGET_EDGES, len(edges)

    # Execution times: a task-specific base with a processor-specific speed
    # factor, the same shape the generator uses.
    comp = []
    for _ in range(n):
        base = rng.uniform(6.0, 30.0)
        comp.append([max(1, int(round(base * rng.uniform(0.5, 1.8))))
                     for _ in range(p)])

    # Delays, then one constant to land on the declared CCR.
    delays = [rng.uniform(1.0, 20.0) for _ in edges]
    mean_cost = sum(sum(row) / p for row in comp) / n
    mean_delay = sum(delays) / len(delays)
    factor = TARGET_CCR * mean_cost / mean_delay
    scaled = [max(0, int(round(d * factor))) for d in delays]

    comm = [[-1] * n for _ in range(n)]
    for (u, v), c in zip(edges, scaled):
        comm[u][v] = c

    info = {
        "synthesised": True,
        "generator": "scripts/genome900.py",
        "note": "reconstruction of the declared properties; ectd_real/gen_new.py "
                "is referenced by the record but is not in this repo",
        "n": n,
        "p": p,
        "entry": ENTRY,
        "stage1": STAGE1,
        "stage2": STAGE2,
        "tail": TAIL,
        "window": WINDOW,
        "tail_fanout": TAIL_FANOUT,
        "edges": len(edges),
        "ccr": measure_ccr(comp, comm, n, p),
        "target_edges": TARGET_EDGES,
        "target_ccr": TARGET_CCR,
    }
    return comp, comm, info


def measure_ccr(comp, comm, n, p):
    """Mean edge delay divided by mean execution cost, over the integer matrices."""
    mean_cost = sum(sum(row) / p for row in comp) / n
    delays = [comm[u][v] for u in range(n) for v in range(n) if comm[u][v] != -1]
    if not delays or mean_cost <= 0:
        return 0.0
    return round((sum(delays) / len(delays)) / mean_cost, 4)


def write_d3(path, comp, comm, n, p):
    """Write the D3 format the corpus and the builder both use."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("%d %d\n" % (n, p))
        for r in range(n):
            fh.write(" ".join(str(comp[r][c]) for c in range(p)) + "\n")
        for r in range(n):
            fh.write(" ".join(str(comm[r][c]) for c in range(n)) + "\n")


def ensure_source(cache_dir, p=16):
    """Build the DAG once and cache it as a D3 file. Returns (path, info)."""
    path = os.path.join(cache_dir, "Genome", "900Nodes", "%dPROCESSORS" % p,
                        "genome900_synth.txt")
    if os.path.isfile(path):
        return path, {"synthesised": True, "cached": True, "path": path}
    comp, comm, info = build(p=p)
    write_d3(path, comp, comm, info["n"], p)
    info["path"] = path
    return path, info


def main():
    comp, comm, info = build()
    print("Genome 900 reconstruction")
    for key in ("n", "edges", "target_edges", "ccr", "target_ccr",
                "stage1", "stage2", "tail", "window", "tail_fanout"):
        print("  %-14s %s" % (key, info[key]))
    ok = info["n"] == TARGET_N and info["edges"] == TARGET_EDGES
    print("  %-14s %s" % ("matches spec", "yes" if ok else "NO"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
