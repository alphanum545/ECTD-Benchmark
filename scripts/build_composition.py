#!/usr/bin/env python3
"""Build the two 1,845-instance compositions (Variant A FORCE, Variant B KNOB LADDER).

Implements the build method in docs/Decision-1605-DualComposition.md section 7:

    comp[r][c] = source_comp[r][c % p_src] * lognormal(0, sigma)
    comm[u][v] = source_comm[u][v] * scale        # -1 stays -1, always

Variant A runs a single rung (sigma=0.18, comm_scale=1) and records a waiver
wherever a cell cannot fill its quota. Variant B escalates through the nine
rungs of section 4.2 and records the rung used on every instance.

Lattice: 165 Set 1 cells at 7W+1A plus 75 Set 2 cells at 6W+1A = 1,845.

Two things this script deliberately does not do:

  * It does not claim its rung distribution will match the ladder probe table in
    section 4.2. The probe used its own seed strings. The probe's job was to show
    the ladder can fill every dead cell; this script's job is to record what the
    build actually did. Both belong in the record.
  * It does not silently backfill a cell that cannot fill. A short cell is a
    waiver in the manifest, and the summary reports the realised ratio rather
    than the target.

Usage:
    python3 scripts/build_composition.py --self-check
    python3 scripts/build_composition.py --variant both
    python3 scripts/build_composition.py --variant B --limit-cells 8
"""
import argparse
import collections
import glob
import json
import math
import os
import random
import statistics
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                            # noqa: E402

ROOT = _paths.REPO_ROOT
PKG_ROOT = _paths.find_package_root()
sys.path.insert(0, PKG_ROOT)
DATA_ROOT = _paths.find_data_root()
GENOME900_CACHE = os.path.join(ROOT, "compositions", "_sources")

POLS = ("ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT")
POW = (4, 8, 16, 32, 64)

SET1 = ("Montage", "Genome", "LIGO")
SET2 = ("FFT", "GE", "LA")

# Genome's eleventh level, synthesised per section 7 (see scripts/genome900.py).
GENOME900_LEVEL = "900Nodes"

# section 4.2, nine rungs, tried in order per cell
LADDER = (
    (0.18, 1.0),
    (0.35, 4.0),
    (0.6, 4.0),
    (0.6, 8.0),
    (0.6, 16.0),
    (1.0, 8.0),
    (1.0, 16.0),
    (1.0, 32.0),
    (1.0, 64.0),
)
RUNG_CAP = 20          # section 4.2: cap 20 candidates per rung, then escalate

# Variant A's per-cell budget. "Dead" is defined as 0 ECTD wins in 24 measured
# candidates, so 24 is the budget that definition implies: a cell A cannot fill
# in 24 draws is dead by the same rule the dead-cell inventory was built on.
A_CAP = 24

# winners, added per cell
QUOTA = {"S1": (7, 1), "S2": (6, 1)}

_TABLE = None
_ENGINE = None
_CACHE = {}


def _table():
    global _TABLE
    if _TABLE is None:
        from ectdbench import policy_table
        _TABLE = policy_table()
    return _TABLE


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from ectdbench.model import Problem
        from ectdbench.engine import validate_schedule
        _ENGINE = (Problem, validate_schedule)
    return _ENGINE


def detect_and_parse(path):
    """Parse a D1/D2/D3 instance file. Same reader as the measurement scripts."""
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


def _parsed(src):
    """Parse once per worker. Returns (n, ps, compc, commc, neg_count)."""
    if src not in _CACHE:
        n, ps, compc, commc, fmt = detect_and_parse(src)
        neg = sum(1 for u in range(n) for v in range(n) if commc[u][v] == -1)
        _CACHE[src] = (n, ps, compc, commc, neg)
    return _CACHE[src]


def comm_matrix(commc, n, cs):
    """Scale comm by cs, preserving every -1 exactly. -1 is structure, not cost."""
    return [[-1 if commc[u][v] == -1 else int(round(commc[u][v] * cs))
             for v in range(n)] for u in range(n)]


def write_d3(path, comp, comm, n, p):
    """D3: 'n p', then the n by p comp matrix, then the n by n comm matrix."""
    with open(path, "w") as fh:
        fh.write("%d %d\n" % (n, p))
        for r in range(n):
            fh.write(" ".join(str(comp[r][c]) for c in range(p)) + "\n")
        for r in range(n):
            fh.write(" ".join(str(comm[r][c]) for c in range(n)) + "\n")


def drift(compc, nc, n, ps, p):
    """Median |log(derived/source)| over comp cells. Same metric as compare_search.py."""
    vals = []
    for r in range(n):
        for c in range(p):
            s = compc[r][c % ps]
            d = nc[r][c]
            if s > 0 and d > 0:
                vals.append(abs(math.log(d / s)))
    return statistics.median(vals) if vals else 0.0


def score_candidate(compc, commc, n, ps, p, rng, sigma, cs):
    """One candidate: resample comp, scale comm, score all six policies.

    Returns (comp_matrix, ectd_won, makespan, margin_pct) or None if any
    schedule fails validation.
    """
    Problem, validate_schedule = _engine()
    nc = [[0] * p for _ in range(n)]
    for r in range(n):
        for c in range(p):
            v = compc[r][c % ps]
            nc[r][c] = max(1, int(round(v * math.exp(rng.gauss(0, sigma))))) if v > 0 else 0

    edges = [(u, v, float(commc[u][v]) * cs)
             for u in range(n) for v in range(n) if commc[u][v] != -1]
    prob = Problem([[float(x) for x in row] for row in nc], edges, name="t")

    table = _table()
    sc = {}
    for name in POLS:
        sch = table[name](prob, insertion=(name != "IPEFT"))
        if not validate_schedule(prob, sch)["valid"]:
            return None
        sc[name] = sch.makespan

    best_other = min(sc[k] for k in POLS if k != "ECTD")
    won = sc["ECTD"] == min(sc.values())
    margin = (best_other - sc["ECTD"]) / best_other * 100.0 if best_other else 0.0
    return nc, won, sc["ECTD"], margin


def fill_cell(job):
    """Fill one cell's quota. Returns a dict; never raises for a short cell.

    A cell is short when it runs out of rungs (B) or budget (A) before meeting
    its quota. That is a waiver, recorded, not an error.
    """
    (fam, level, p, set_name, src, variant, outdir) = job
    quota_w, quota_a = QUOTA[set_name]
    n, ps, compc, commc, neg = _parsed(src)

    rungs = LADDER if variant == "B" else (LADDER[0],)
    cap = RUNG_CAP if variant == "B" else A_CAP

    winners = []      # (comp_matrix, makespan, margin, sigma, cs, rung, cand)
    added = []        # (comp_matrix, makespan, margin, sigma, cs, rung, cand)
    rung_used = 0
    rung_hist = collections.Counter()
    tried = 0
    started = time.time()

    for rung, (sigma, cs) in enumerate(rungs, 1):
        if len(winners) >= quota_w and len(added) >= quota_a:
            break
        for cand in range(cap):
            if len(winners) >= quota_w and len(added) >= quota_a:
                break
            tried += 1
            # Seed includes the cell and the attempt index, so a cell's draws do
            # not depend on how many other cells ran before it.
            rng = random.Random("build|%s|%s|%d|%s|%d|%d"
                                % (fam, level, p, variant, rung, cand))
            res = score_candidate(compc, commc, n, ps, p, rng, sigma, cs)
            if res is None:
                continue
            nc, won, makespan, margin = res
            if won and len(winners) < quota_w:
                winners.append((nc, makespan, margin, sigma, cs, rung, cand))
                rung_hist[rung] += 1
            elif (not won) and len(added) < quota_a:
                added.append((nc, makespan, margin, sigma, cs, rung, cand))
                rung_hist[rung] += 1
        if len(winners) >= quota_w and len(added) >= quota_a:
            rung_used = rung
            break

    met = len(winners) >= quota_w and len(added) >= quota_a
    if met:
        rung_used = max(rung_used, max(rung_hist) if rung_hist else 1)

    # Write the cell's instances. Only what was actually filled is written.
    records = []
    cell_dir = os.path.join(outdir, "instances", fam, level, "%dPROCESSORS" % p)
    os.makedirs(cell_dir, exist_ok=True)
    for kind, bucket, want in (("W", winners, quota_w), ("A", added, quota_a)):
        for i, (nc, makespan, margin, sigma, cs, rung, cand) in enumerate(bucket[:want]):
            comm = comm_matrix(commc, n, cs)
            name = "%s_%s_p%d_%s%d" % (fam, level, p, kind, i + 1)
            path = os.path.join(cell_dir, name + ".txt")
            write_d3(path, nc, comm, n, p)
            records.append({
                "id": name,
                "family": fam,
                "level": level,
                "p": p,
                "set": set_name,
                "class": "winner" if kind == "W" else "added",
                "source": os.path.relpath(src, ROOT),
                "sigma": sigma,
                "comm_scale": cs,
                "rung": rung,
                "candidate": cand,
                "makespan": makespan,
                "margin_pct": round(margin, 4),
                "drift": round(drift(compc, nc, n, ps, p), 6),
                "neg_entries": neg,
            })

    return {
        "family": fam,
        "level": level,
        "p": p,
        "set": set_name,
        "variant": variant,
        "source": os.path.relpath(src, ROOT),
        "quota_w": quota_w,
        "quota_a": quota_a,
        "filled_w": len(winners),
        "filled_a": len(added),
        "met": met,
        "waived": (max(0, quota_w - len(winners)) + max(0, quota_a - len(added))),
        "rung_used": rung_used,
        "rung_hist": dict(rung_hist),
        "candidates": tried,
        "sec": round(time.time() - started, 3),
        "records": records,
    }


def cell_inventory():
    """Enumerate the 240 lattice cells and resolve each to a source file.

    Set 1 is the 11-level families; Set 2 the 5-level ones. Genome 900 is
    synthesised (section 7) and has no source file, so it is reported as
    unresolved rather than silently skipped.

    One source DAG per level, evaluated at all five p values. This matches
    ``measure_cell_rates.py`` exactly, which is what makes the dead-cell
    inventory apply to this build: the win rates were measured on that same
    DAG. The source's comp matrix has its own column count and is tiled to the
    target p by ``c % ps``; the comm matrix and its -1 pattern are the DAG's
    and do not depend on p. Picking a different source per p would silently
    break the correspondence with the measurements.
    """
    cells = []
    resolved = []
    unresolved = []
    for fam in SET1 + SET2:
        set_name = "S1" if fam in SET1 else "S2"
        bylevel = collections.defaultdict(list)
        pattern = os.path.join(DATA_ROOT, fam, "*", "*", "*.txt")
        for s in sorted(glob.glob(pattern)):
            bylevel[os.path.basename(os.path.dirname(os.path.dirname(s)))].append(s)
        for lv in sorted(bylevel, key=lambda k: int(k.replace("Nodes", ""))):
            src = bylevel[lv][0]
            for p in POW:
                cells.append((fam, lv, p, set_name, src))

    # Genome 900. The corpus has ten Genome levels; Set 1 needs eleven. Section
    # 7 says the eleventh is synthesised, so build it here rather than letting
    # the lattice quietly come up 40 instances short. The source is a
    # reconstruction of the declared properties (n=901, 2,729 edges, CCR 0.51),
    # not the original file, and every instance built from it is marked
    # synthesised in the manifest.
    have = {(f, l) for f, l, _, _, _ in cells}
    for fam in SET1:
        levels = {l for f, l in have if f == fam}
        if len(levels) >= 11:
            continue
        if fam != "Genome":
            unresolved.append({"family": fam, "levels_found": sorted(levels),
                               "note": "missing levels and no synthesis recipe"})
            continue
        import genome900
        src, info = genome900.ensure_source(GENOME900_CACHE)
        for p in POW:
            cells.append((fam, GENOME900_LEVEL, p, "S1", src))
        resolved.append({"family": fam, "level": GENOME900_LEVEL,
                         "source": os.path.relpath(src, ROOT),
                         "synthesised": True, "info": info})
    return cells, resolved, unresolved


def build(variant, outdir, workers, limit_cells=None, shard_id=None, num_shards=None):
    """Build a variant, optionally over one shard of the cell inventory.

    Sharding is by canonical cell index modulo num_shards, so the union of all
    shards is exactly the full inventory with no overlap and no gaps. A shard
    writes only its own cells; the merge job recombines them.
    """
    cells, resolved, unresolved = cell_inventory()
    if limit_cells:
        cells = cells[:limit_cells]
    if shard_id is not None:
        if num_shards is None or not (0 <= shard_id < num_shards):
            raise ValueError("invalid shard_id/num_shards: %s/%s" % (shard_id, num_shards))
        cells = [c for i, c in enumerate(cells) if i % num_shards == shard_id]
    jobs = [(f, l, p, s, src, variant, outdir) for f, l, p, s, src in cells]

    started = time.time()
    if workers > 1:
        with Pool(workers) as pool:
            results = pool.map(fill_cell, jobs, chunksize=1)
    else:
        results = [fill_cell(j) for j in jobs]
    elapsed = time.time() - started

    records = [r for c in results for r in c["records"]]
    cells_out = [{k: v for k, v in c.items() if k != "records"} for c in results]

    total_w = sum(c["filled_w"] for c in results)
    total_a = sum(c["filled_a"] for c in results)
    waived = sum(c["waived"] for c in results)
    short_cells = [c for c in results if not c["met"]]

    rung_usage = collections.Counter()
    for r in records:
        rung_usage[r["rung"]] += 1

    # Rung 5 is sigma=0.6 / comm x16. The record counts "x16 or beyond" as the
    # cells that have left their source communication regime, so this one
    # threshold defines both the instance count and the cell count.
    off_regime = [r for r in records if r["rung"] >= 5]

    by_set = {}
    for s in ("S1", "S2"):
        w = sum(c["filled_w"] for c in results if c["set"] == s)
        a = sum(c["filled_a"] for c in results if c["set"] == s)
        by_set[s] = {"winners": w, "added": a,
                     "ratio": round(w / a, 4) if a else None}

    by_family = {}
    for fam in SET1 + SET2:
        w = sum(c["filled_w"] for c in results if c["family"] == fam)
        a = sum(c["filled_a"] for c in results if c["family"] == fam)
        by_family[fam] = {"winners": w, "added": a,
                          "ratio": round(w / a, 4) if a else None}

    manifest = {
        "variant": variant,
        "variant_name": "FORCE" if variant == "A" else "KNOB LADDER",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "shard": {"id": shard_id, "count": num_shards},
        "lattice_target": 1845,
        "cells_target": 240,
        "quota": {"S1": {"winners": 7, "added": 1}, "S2": {"winners": 6, "added": 1}},
        "delivered": len(records),
        "winners": total_w,
        "added": total_a,
        "waived": waived,
        "cells_filled": sum(1 for c in results if c["met"]),
        "cells_short": len(short_cells),
        "realised_ratio": round(total_w / total_a, 4) if total_a else None,
        "by_set": by_set,
        "by_family": by_family,
        "rung_usage": {str(k): v for k, v in sorted(rung_usage.items())},
        "escalated_instances": len(off_regime),
        "cells_outside_source_regime": len({(r["family"], r["level"], r["p"])
                                            for r in off_regime}),
        "synthesised_sources": resolved,
        "unresolved": unresolved,
        "elapsed_sec": round(elapsed, 2),
        "cells": cells_out,
        "instances": records,
    }
    return manifest


def self_check():
    """Verify the lattice arithmetic and the invariants the build must hold."""
    ok = True

    def check(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print("  %-52s %-10s %s" % (label, got, "ok" if good else "FAIL want %s" % want))

    print("lattice")
    s1 = 3 * 11 * 5
    s2 = 3 * 5 * 5
    check("Set 1 cells", s1, 165)
    check("Set 2 cells", s2, 75)
    check("total cells", s1 + s2, 240)
    check("Set 1 instances (7W+1A)", s1 * 8, 1320)
    check("Set 2 instances (6W+1A)", s2 * 7, 525)
    check("total instances", s1 * 8 + s2 * 7, 1845)
    check("Set 1 winners", s1 * 7, 1155)
    check("Set 2 winners", s2 * 6, 450)
    check("total winners", s1 * 7 + s2 * 6, 1605)
    check("total added", s1 + s2, 240)

    print("ladder")
    check("rungs", len(LADDER), 9)
    check("rung 1 is baseline", LADDER[0], (0.18, 1.0))
    check("rung 9 is x64", LADDER[-1], (1.0, 64.0))

    print("comm scaling preserves -1")
    commc = [[-1, 5, 0], [3, -1, 7], [0, 2, -1]]
    for cs in (1.0, 4.0, 64.0):
        m = comm_matrix(commc, 3, cs)
        neg_ok = all(m[u][v] == -1 for u in range(3) for v in range(3) if commc[u][v] == -1)
        zero_ok = m[0][2] == 0 and m[2][0] == 0
        check("cs=%-5s -1 preserved" % cs, neg_ok and zero_ok, True)
    check("cs=4 scales a real cost", comm_matrix(commc, 3, 4.0)[0][1], 20)

    print("D3 round-trip")
    import tempfile
    comp = [[1, 2], [3, 4], [5, 6]]
    comm = [[-1, 9, 0], [9, -1, 4], [0, 4, -1]]
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "t.txt")
        write_d3(path, comp, comm, 3, 2)
        n2, p2, comp2, comm2, fmt = detect_and_parse(path)
        check("n", n2, 3)
        check("p", p2, 2)
        check("format", fmt, "D3")
        check("comp identical", comp2, comp)
        check("comm identical", comm2, comm)
        check("-1 count", sum(1 for r in comm2 for v in r if v == -1), 3)

    print("\n%s" % ("all checks pass" if ok else "CHECKS FAILED"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("A", "B", "both"), default="both")
    ap.add_argument("--out", default=os.path.join(ROOT, "compositions"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-cells", type=int, default=None)
    ap.add_argument("--shard-id", type=int, default=None,
                    help="build only cells whose canonical index %% num-shards == this")
    ap.add_argument("--num-shards", type=int, default=None,
                    help="total shard count; required with --shard-id")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        return self_check()

    if (args.shard_id is None) != (args.num_shards is None):
        raise SystemExit("--shard-id and --num-shards must be given together")

    variants = ("A", "B") if args.variant == "both" else (args.variant,)
    for v in variants:
        outdir = os.path.join(args.out, "variant_%s" % v)
        os.makedirs(outdir, exist_ok=True)
        print("building variant %s -> %s" % (v, outdir))
        m = build(v, outdir, args.workers, args.limit_cells,
                  args.shard_id, args.num_shards)
        dest = os.path.join(outdir, "manifest.json")
        with open(dest, "w") as fh:
            json.dump(m, fh, indent=1)
        print("  delivered %d of %d (%d winners, %d added), %d waived"
              % (m["delivered"], m["lattice_target"], m["winners"],
                 m["added"], m["waived"]))
        print("  cells filled %d of %d, realised ratio %s, %.1fs"
              % (m["cells_filled"], m["cells_target"],
                 m["realised_ratio"], m["elapsed_sec"]))
        print("  -> %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
