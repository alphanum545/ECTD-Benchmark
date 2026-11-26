#!/usr/bin/env python3
"""Generate a small synthetic source tree so build_composition.py can be
smoke-tested without the 3.1 GB scheduling-benchmark corpus.

This is a TEST FIXTURE, not data. It writes D3 instances in the same on-disk
format the real corpus uses, at the same directory depth, so the builder's
glob, parser and writer are exercised exactly as they will be in the real run.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "scheduling-benchmark", "data")

# small levels only: this is a pipeline test, not a scale test
FAMILIES = {
    "Montage": [50, 100, 200],
    "Genome": [50, 100, 200],
    "LIGO": [50, 100, 200],
    "FFT": [40, 96, 224],
    "GE": [9, 35, 135],
    "LA": [11, 37, 137],
}


def make_d3(n, p, seed):
    rng = random.Random(seed)
    # layered DAG so precedence is acyclic by construction
    layer = [0] * n
    for i in range(1, n):
        layer[i] = layer[rng.randrange(max(0, i - 6), i)] + 1
    comp = [[rng.randrange(1, 60) for _ in range(p)] for _ in range(n)]
    comm = [[-1] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if layer[j] == layer[i] + 1 and rng.random() < 0.35:
                comm[i][j] = rng.randrange(0, 40)
    return comp, comm


def write(path, comp, comm, n, p):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("%d %d\n" % (n, p))
        for r in range(n):
            fh.write(" ".join(str(comp[r][c]) for c in range(p)) + "\n")
        for r in range(n):
            fh.write(" ".join(str(comm[r][c]) for c in range(n)) + "\n")


def main():
    made = 0
    for fam, levels in FAMILIES.items():
        for lv in levels:
            for p in (4, 8, 16, 32, 64):
                comp, comm = make_d3(lv, p, "%s|%d|%d" % (fam, lv, p))
                path = os.path.join(OUT, fam, "%dNodes" % lv,
                                    "%dPROCESSORS" % p, "synth_0.txt")
                write(path, comp, comm, lv, p)
                made += 1
    print("wrote %d synthetic source files under %s" % (made, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
