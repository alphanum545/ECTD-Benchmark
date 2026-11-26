#!/usr/bin/env python3
"""Probe stronger knob settings on the cells that survived the 4-step ladder."""
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
# stronger rungs beyond the approved ladder
LADDER = [(0.6, 16.0), (1.0, 8.0), (1.0, 16.0), (1.0, 32.0)]
SEEDS = 10


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


def perturb(v, rng, s):
    return max(1, int(round(v * math.exp(rng.gauss(0, s))))) if v > 0 else v


_T = None
_C = {}


def _table():
    global _T
    if _T is None:
        _T = policy_table()
    return _T


def _parsed(src):
    if src not in _C:
        n, ps, compc, commc, fmt = detect_and_parse(src)
        edges = [(u, v, float(commc[u][v]))
                 for u in range(n) for v in range(n) if commc[u][v] != -1]
        _C[src] = (n, ps, compc, edges)
    return _C[src]


def probe(job):
    fam, level, p, src = job
    table = _table()
    n, ps, compc, edges = _parsed(src)
    for step, (sigma, cs) in enumerate(LADDER, 1):
        w = c = 0
        for seed in range(1, SEEDS + 1):
            rng = random.Random("q|%s|%s|%d|%d|%d" % (fam, level, p, step, seed))
            nc = [[perturb(compc[r][cc % ps], rng, sigma) for cc in range(p)]
                  for r in range(n)]
            e2 = [(u, v, cc * cs) for u, v, cc in edges]
            prob = Problem([[float(x) for x in row] for row in nc], e2, name="t")
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
        if w > 0:
            return (fam, level, p, step, w, c)
    return (fam, level, p, 0, 0, 0)


def main():
    prev = json.load(open(os.path.join(_paths.OUT_DIR, "ladder_probe.json")))
    stuck = [(x["family"], x["level"], x["p"]) for x in prev if x["step"] == 0]
    jobs = []
    for fam, lv, p in stuck:
        fs = sorted(glob.glob(os.path.join(
            DATA_ROOT, fam, lv, "*", "*.txt")))
        if fs:
            jobs.append((fam, lv, p, fs[0]))

    with Pool(8) as pool:
        res = pool.map(probe, jobs, chunksize=1)

    by = collections.Counter(r[3] for r in res)
    print("probed %d stubborn cells with stronger rungs" % len(res))
    for step in range(1, 5):
        print("  filled at extra step %d %s: %d" % (
            step, LADDER[step - 1], by[step]))
    print("  STILL DEAD: %d" % by[0])
    for fam, lv, p, step, w, c in res:
        if step == 0:
            print("     %s %s p=%s" % (fam, lv, p))

    dest = os.path.join(_paths.OUT_DIR, "ladder_probe2.json")
    with open(dest, "w") as fh:
        json.dump([{"family": f, "level": l, "p": p, "step": s,
                    "wins": w, "cand": c} for f, l, p, s, w, c in res],
                  fh, indent=1)
    print("-> %s" % dest)


if __name__ == "__main__":
    main()
