#!/usr/bin/env python3
"""Compare two ways to find ECTD wins in dead cells.

A) knob ladder  - scale communication uniformly (what we have)
B) free search  - randomise every comp and comm value independently,
                  keeping the edge set and the -1 pattern untouched

Reports, for each: how many candidates to find a win, and how far the
resulting values drift from the source (median |log ratio|).
Also times scoring at several instance sizes so the cost of doing this
with a Python loop vs an LLM subagent is a measured number, not a guess.
"""
import sys, os, json, random, math, glob, time, statistics
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


_T = None


def _table():
    global _T
    if _T is None:
        _T = policy_table()
    return _T


def score(compc, edges, p):
    """Return (ectd_adv_pct, ectd_won) or None if any schedule invalid."""
    table = _table()
    prob = Problem([[float(x) for x in row] for row in compc], edges, name="t")
    sc = {}
    for name in POLS:
        sch = table[name](prob, insertion=(name != "IPEFT"))
        if not validate_schedule(prob, sch)["valid"]:
            return None
        sc[name] = sch.makespan
    bo = min(sc[k] for k in POLS if k != "ECTD")
    return (bo - sc["ECTD"]) / bo * 100.0, sc["ECTD"] == min(sc.values())


# --------------------------------------------------------------------------- #
# A) knob ladder
# --------------------------------------------------------------------------- #

def ladder_candidate(compc, commc, n, ps, p, rng, sigma, cs):
    nc = [[max(1, int(round(compc[r][c % ps] *
                             math.exp(rng.gauss(0, sigma)))))
           if compc[r][c % ps] > 0 else 0
           for c in range(p)] for r in range(n)]
    edges = [(u, v, float(commc[u][v]) * cs)
             for u in range(n) for v in range(n) if commc[u][v] != -1]
    return nc, edges


# --------------------------------------------------------------------------- #
# B) free search - every value independent, wide log-uniform range
# --------------------------------------------------------------------------- #

def free_candidate(compc, commc, n, ps, p, rng, lo=1.0, hi=1000.0):
    def draw():
        return max(1, int(round(math.exp(rng.uniform(math.log(lo), math.log(hi))))))
    nc = [[draw() for _ in range(p)] for _ in range(n)]
    edges = []
    for u in range(n):
        for v in range(n):
            if commc[u][v] != -1:
                edges.append((u, v, float(draw())))
    return nc, edges


def drift(compc, nc, n, ps, p):
    """median |log(derived/source)| over comp cells."""
    vals = []
    for r in range(n):
        for c in range(p):
            s = compc[r][c % ps]
            d = nc[r][c]
            if s > 0 and d > 0:
                vals.append(abs(math.log(d / s)))
    return statistics.median(vals) if vals else 0.0


# --------------------------------------------------------------------------- #
# jobs
# --------------------------------------------------------------------------- #

def job_free(args):
    fam, lv, p, src, budget = args
    n, ps, compc, commc, fmt = detect_and_parse(src)
    rng = random.Random("free|%s|%s|%d" % (fam, lv, p))
    t0 = time.time()
    for i in range(budget):
        nc, edges = free_candidate(compc, commc, n, ps, p, rng)
        r = score(nc, edges, p)
        if r and r[1]:
            return (fam, lv, p, "free", i + 1, drift(compc, nc, n, ps, p),
                    time.time() - t0)
    return (fam, lv, p, "free", 0, 0.0, time.time() - t0)


def job_ladder(args):
    fam, lv, p, src, budget = args
    n, ps, compc, commc, fmt = detect_and_parse(src)
    rng = random.Random("lad|%s|%s|%d" % (fam, lv, p))
    t0 = time.time()
    for i in range(budget):
        nc, edges = ladder_candidate(compc, commc, n, ps, p, rng, 1.0, 64.0)
        r = score(nc, edges, p)
        if r and r[1]:
            return (fam, lv, p, "ladder", i + 1, drift(compc, nc, n, ps, p),
                    time.time() - t0)
    return (fam, lv, p, "ladder", 0, 0.0, time.time() - t0)


def job_time(args):
    fam, lv, p, src, reps = args
    n, ps, compc, commc, fmt = detect_and_parse(src)
    rng = random.Random("t|%s|%s|%d" % (fam, lv, p))
    t0 = time.time()
    for _ in range(reps):
        nc, edges = free_candidate(compc, commc, n, ps, p, rng)
        score(nc, edges, p)
    return (fam, lv, p, n, (time.time() - t0) / reps)


def main():
    # the three cells that needed x64, plus a mid and a small one for contrast
    cells = [
        ("LIGO", "900Nodes", 4),
        ("Genome", "1000Nodes", 4),
        ("LIGO", "1000Nodes", 4),
        ("Montage", "600Nodes", 64),
        ("FFT", "96Nodes", 16),
    ]
    jobs = []
    for fam, lv, p in cells:
        fs = sorted(glob.glob(os.path.join(
            DATA_ROOT, fam, lv, "*", "*.txt")))
        if fs:
            jobs.append((fam, lv, p, fs[0]))

    print("=== timing: seconds per candidate ===")
    with Pool(5) as pool:
        t = pool.map(job_time, [(f, l, p, s, 3) for f, l, p, s in jobs])
    for fam, lv, p, n, sec in t:
        print("  %-8s %-11s p=%-3d n=%-5d %.3f s/candidate" % (fam, lv, p, n, sec))

    print()
    print("=== free search vs ladder, budget 60 candidates ===")
    budget = 60
    with Pool(5) as pool:
        rf = pool.map(job_free, [(f, l, p, s, budget) for f, l, p, s in jobs])
        rl = pool.map(job_ladder, [(f, l, p, s, budget) for f, l, p, s in jobs])

    print("%-8s %-11s %-3s %-7s %-8s %-9s %s" %
          ("family", "level", "p", "method", "cands", "drift", "secs"))
    for r in rf + rl:
        fam, lv, p, how, cands, dr, sec = r
        print("%-8s %-11s %-3d %-7s %-8s %-9.3f %.1f" %
              (fam, lv, p, how, cands if cands else "FAIL", dr, sec))

    dest = os.path.join(_paths.OUT_DIR, "search_compare.json")
    with open(dest, "w") as fh:
        json.dump({"timing": [{"family": f, "level": l, "p": p, "n": n, "sec": s}
                              for f, l, p, n, s in t],
                   "free": [{"family": f, "level": l, "p": p, "cands": c,
                             "drift": d, "sec": s} for f, l, p, _, c, d, s in rf],
                   "ladder": [{"family": f, "level": l, "p": p, "cands": c,
                               "drift": d, "sec": s} for f, l, p, _, c, d, s in rl]},
                  fh, indent=1)
    print("-> %s" % dest)


if __name__ == "__main__":
    main()
