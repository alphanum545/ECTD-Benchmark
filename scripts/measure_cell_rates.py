#!/usr/bin/env python3
"""Measure ECTD win rate per (family, level, p) cell for Set 1 and Set 2.

Used to decide which processor values are viable in each set. Writes JSON.
Parallelised across cells; each cell draws NSEED candidates per source.
"""
import sys, os, json, random, math, glob, collections
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                            # noqa: E402

ROOT = _paths.REPO_ROOT
sys.path.insert(0, _paths.find_package_root())
DATA_ROOT = _paths.find_data_root()

from ectdbench import policy_table
from ectdbench.model import Problem
from ectdbench.engine import validate_schedule

POLS = ("ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT")
POW = [4, 8, 16, 32, 64]
NSEED = 12
NSRC = 2


def detect_and_parse(path):
    with open(path) as fh:
        t = fh.read().split()
    n, p = int(t[0]), int(t[1])
    for name, hdr in (("D1", p + 5 * p), ("D2", 5 * p), ("D3", 0)):
        if 2 + hdr + n * p + n * n != len(t):
            continue
        j = 2
        if name == "D1":
            j += p
        if name != "D3":
            j += 5 * p
        compc = [[int(t[j + r * p + c]) for c in range(p)] for r in range(n)]
        j += n * p
        commc = [[int(t[j + r * n + c]) for c in range(n)] for r in range(n)]
        return n, p, compc, commc, name
    raise ValueError("no format: %s" % path)


def perturb(v, rng, s=0.18):
    return max(1, int(round(v * math.exp(rng.gauss(0, s))))) if v > 0 else v


_TABLE = None
_CACHE = {}


def _table():
    global _TABLE
    if _TABLE is None:
        _TABLE = policy_table()
    return _TABLE


def _parsed(src):
    if src not in _CACHE:
        n, ps, compc, commc, fmt = detect_and_parse(src)
        edges = [(u, v, float(commc[u][v]))
                 for u in range(n) for v in range(n) if commc[u][v] != -1]
        _CACHE[src] = (n, ps, compc, edges)
    return _CACHE[src]


def one_cell(job):
    fam, level, p, srcs = job
    table = _table()
    c = w = 0
    for src in srcs:
        n, ps, compc, edges = _parsed(src)
        for seed in range(1, NSEED + 1):
            rng = random.Random("m|%s|%s|%s|%d" % (fam, level, p, seed))
            nc = [[perturb(compc[r][cc % ps], rng) for cc in range(p)]
                  for r in range(n)]
            prob = Problem([[float(x) for x in row] for row in nc], edges, name="t")
            sc = {}
            ok = True
            for name in POLS:
                sch = table[name](prob, insertion=(name != "IPEFT"))
                if not validate_schedule(prob, sch)["valid"]:
                    ok = False
                    break
                sc[name] = sch.makespan
            if not ok:
                continue
            c += 1
            if sc["ECTD"] == min(sc.values()):
                w += 1
    return (fam, level, p, w, c)


def main():
    jobs = []
    for fam in ("Montage", "Genome", "LIGO", "FFT", "GE", "LA"):
        bylevel = collections.defaultdict(list)
        for s in sorted(glob.glob(os.path.join(
                DATA_ROOT, fam, "*", "*", "*.txt"))):
            bylevel[os.path.basename(os.path.dirname(os.path.dirname(s)))].append(s)
        for lv in sorted(bylevel, key=lambda k: int(k.replace("Nodes", ""))):
            srcs = bylevel[lv][:NSRC]
            for p in POW:
                jobs.append((fam, lv, p, srcs))

    with Pool(8) as pool:
        results = pool.map(one_cell, jobs, chunksize=1)

    out = {}
    for fam, lv, p, w, c in results:
        out["%s|%s|%d" % (fam, lv, p)] = [w, c]

    dest = os.path.join(_paths.OUT_DIR, "cell_rates.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    total = sum(v[1] for v in out.values())
    print("measured %d cells, %d candidates -> %s" % (len(out), total, dest))


if __name__ == "__main__":
    main()
