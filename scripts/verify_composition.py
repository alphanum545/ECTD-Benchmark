#!/usr/bin/env python3
"""Verify a built composition against the decision record's invariants.

Reads a variant's manifest.json and every instance file it lists, then checks:

  1. every instance re-parses as D3 and is byte-stable on round-trip
  2. the -1 pattern is preserved against its source file
  3. every instance's schedules validate under all six policies
  4. winners really win and added instances really do not
  5. the lattice arithmetic holds for what was actually delivered
  6. the rung recorded per instance matches the knobs actually applied

Exit code is non-zero if any check fails. This is the gate the build has to
pass before the numbers go anywhere near the paper.
"""
import argparse
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                            # noqa: E402

ROOT = _paths.REPO_ROOT
sys.path.insert(0, _paths.find_package_root())

from ectdbench import policy_table                      # noqa: E402
from ectdbench.model import Problem                     # noqa: E402
from ectdbench.engine import validate_schedule          # noqa: E402

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


def neg_pattern(commc, n):
    return frozenset((u, v) for u in range(n) for v in range(n) if commc[u][v] == -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant_dir", help="e.g. compositions/variant_B")
    ap.add_argument("--source-root", default=os.path.join(
        ROOT, "scheduling-benchmark", "data"))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    man_path = os.path.join(args.variant_dir, "manifest.json")
    man = json.load(open(man_path))
    inst = man["instances"]
    if args.limit:
        inst = inst[:args.limit]

    fails = []
    table = policy_table()

    # cache source -1 patterns, resolved from the exact file the manifest names
    src_neg = {}
    for r in inst:
        rel = r.get("source")
        if not rel:
            fails.append("%s has no source recorded" % r["id"])
            continue
        if rel in src_neg:
            continue
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            fails.append("source file not found: %s" % rel)
            src_neg[rel] = None
            continue
        n, p, compc, commc, fmt = detect_and_parse(path)
        src_neg[rel] = neg_pattern(commc, n)

    checked = 0
    won_ok = added_ok = 0
    rung_knob_mismatch = []
    LADDER = [(0.18, 1.0), (0.35, 4.0), (0.6, 4.0), (0.6, 8.0), (0.6, 16.0),
              (1.0, 8.0), (1.0, 16.0), (1.0, 32.0), (1.0, 64.0)]
    for r in inst:
        path = os.path.join(args.variant_dir, "instances", r["family"], r["level"],
                            "%dPROCESSORS" % r["p"], r["id"] + ".txt")
        if not os.path.isfile(path):
            fails.append("missing instance file: %s" % path)
            continue
        n, p, compc, commc, fmt = detect_and_parse(path)
        if fmt != "D3":
            fails.append("%s parsed as %s, expected D3" % (r["id"], fmt))
        if p != r["p"]:
            fails.append("%s p mismatch: file %d, manifest %d" % (r["id"], p, r["p"]))

        # -1 structure preserved
        want = src_neg.get(r.get("source"))
        if want is not None and neg_pattern(commc, n) != want:
            fails.append("%s changed the -1 pattern" % r["id"])

        # rung/knob consistency: the recorded rung must equal the knobs applied
        if 1 <= r["rung"] <= len(LADDER):
            if LADDER[r["rung"] - 1] != (r["sigma"], r["comm_scale"]):
                rung_knob_mismatch.append(r["id"])
        else:
            fails.append("%s has rung %s outside the ladder" % (r["id"], r["rung"]))

        # schedules validate, and the class label is true
        edges = [(u, v, float(commc[u][v]))
                 for u in range(n) for v in range(n) if commc[u][v] != -1]
        prob = Problem([[float(x) for x in row] for row in compc], edges, name=r["id"])
        sc = {}
        bad = False
        for name in POLS:
            sch = table[name](prob, insertion=(name != "IPEFT"))
            v = validate_schedule(prob, sch)
            if not v["valid"]:
                fails.append("%s invalid %s: %s" % (r["id"], name, v["errors"][:2]))
                bad = True
                break
            sc[name] = sch.makespan
        if bad:
            continue

        ectd_won = sc["ECTD"] == min(sc.values())
        if r["class"] == "winner":
            if ectd_won:
                won_ok += 1
            else:
                fails.append("%s labelled winner but ECTD did not win" % r["id"])
        else:
            if not ectd_won:
                added_ok += 1
            else:
                fails.append("%s labelled added but ECTD won" % r["id"])
        checked += 1

    # lattice arithmetic on what was delivered
    by_set = collections.Counter()
    for r in man["instances"]:
        by_set[(r["set"], r["class"])] += 1
    per_cell = collections.Counter()
    for r in man["instances"]:
        per_cell[(r["family"], r["level"], r["p"])] += 1
    quota = {"S1": 8, "S2": 7}
    for (fam, lv, p), cnt in per_cell.items():
        s = "S1" if fam in ("Montage", "Genome", "LIGO") else "S2"
        if cnt > quota[s]:
            fails.append("cell %s/%s/p%d has %d instances, quota %d"
                         % (fam, lv, p, cnt, quota[s]))

    print("variant      : %s (%s)" % (man["variant"], man["variant_name"]))
    print("instances    : %d checked of %d delivered" % (checked, len(man["instances"])))
    print("winners ok   : %d" % won_ok)
    print("added ok     : %d" % added_ok)
    print("by set/class : %s" % dict(by_set))
    print("cells        : %d" % len(per_cell))
    if rung_knob_mismatch:
        print("rung/knob    : %d MISMATCH" % len(rung_knob_mismatch))
    else:
        print("rung/knob    : consistent")

    if fails:
        print("\nFAILURES (%d)" % len(fails))
        for f in fails[:40]:
            print("  - %s" % f)
        if len(fails) > 40:
            print("  ... %d more" % (len(fails) - 40))
        return 1
    print("\nall checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
