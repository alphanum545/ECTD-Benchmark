#!/usr/bin/env python3
"""Merge composition shards into canonical variant manifests and instance trees.

Each CI shard runs build_composition.py with --shard-id/--num-shards and uploads
its output tree. This script downloads are already merged into shards/ by the
workflow; it copies the instance files into the canonical output and recombines
the per-shard manifests into one manifest per variant with the same shape the
serial builder produces.

The union of shards is exact: cell_inventory() assigns cells by canonical index
modulo num_shards, so no cell is duplicated or dropped.
"""
import argparse
import collections
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _paths                                            # noqa: E402

ROOT = _paths.REPO_ROOT
POLS = ("ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT")
SET1 = ("Montage", "Genome", "LIGO")
SET2 = ("FFT", "GE", "LA")


def merge_variant(variant, shard_dirs, out_dir, expected_shards):
    """Recombine one variant's shards. Returns the merged manifest."""
    dest = os.path.join(out_dir, "variant_%s" % variant)
    inst_dest = os.path.join(dest, "instances")
    os.makedirs(inst_dest, exist_ok=True)

    manifests = []
    for sd in shard_dirs:
        p = os.path.join(sd, "variant_%s" % variant, "manifest.json")
        if not os.path.isfile(p):
            raise SystemExit("missing shard manifest: %s" % p)
        manifests.append((sd, json.load(open(p))))

    # verify shard coverage
    ids = sorted(m["shard"]["id"] for _, m in manifests)
    if ids != list(range(expected_shards)):
        raise SystemExit("shard ids %s != 0..%d" % (ids, expected_shards - 1))
    counts = {m["shard"]["count"] for _, m in manifests}
    if counts != {expected_shards}:
        raise SystemExit("shard counts %s != %d" % (counts, expected_shards))

    records = []
    cells = []
    for sd, m in manifests:
        records.extend(m["instances"])
        cells.extend(m["cells"])

        # copy this shard's instance files into the canonical tree
        src_inst = os.path.join(sd, "variant_%s" % variant, "instances")
        for path in glob.glob(os.path.join(src_inst, "**", "*.txt"), recursive=True):
            rel = os.path.relpath(path, src_inst)
            target = os.path.join(inst_dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(path, target)

    # dedupe guard: no instance id may appear twice
    names = [r["id"] for r in records]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate instance ids across shards")

    total_w = sum(c["filled_w"] for c in cells)
    total_a = sum(c["filled_a"] for c in cells)
    waived = sum(c["waived"] for c in cells)

    rung_usage = collections.Counter()
    for r in records:
        rung_usage[r["rung"]] += 1
    off_regime = [r for r in records if r["rung"] >= 5]

    by_set = {}
    for s in ("S1", "S2"):
        w = sum(c["filled_w"] for c in cells if c["set"] == s)
        a = sum(c["filled_a"] for c in cells if c["set"] == s)
        by_set[s] = {"winners": w, "added": a,
                     "ratio": round(w / a, 4) if a else None}

    by_family = {}
    for fam in SET1 + SET2:
        w = sum(c["filled_w"] for c in cells if c["family"] == fam)
        a = sum(c["filled_a"] for c in cells if c["family"] == fam)
        by_family[fam] = {"winners": w, "added": a,
                          "ratio": round(w / a, 4) if a else None}

    # provenance fields are identical across shards; take the first
    first = manifests[0][1]
    manifest = {
        "variant": variant,
        "variant_name": first["variant_name"],
        "generated": first["generated"],
        "merged_from_shards": expected_shards,
        "lattice_target": 1845,
        "cells_target": 240,
        "quota": {"S1": {"winners": 7, "added": 1}, "S2": {"winners": 6, "added": 1}},
        "delivered": len(records),
        "winners": total_w,
        "added": total_a,
        "waived": waived,
        "cells_filled": sum(1 for c in cells if c["met"]),
        "cells_short": sum(1 for c in cells if not c["met"]),
        "realised_ratio": round(total_w / total_a, 4) if total_a else None,
        "by_set": by_set,
        "by_family": by_family,
        "rung_usage": {str(k): v for k, v in sorted(rung_usage.items())},
        "escalated_instances": len(off_regime),
        "cells_outside_source_regime": len({(r["family"], r["level"], r["p"])
                                            for r in off_regime}),
        "synthesised_sources": first["synthesised_sources"],
        "unresolved": first["unresolved"],
        "elapsed_sec": round(sum(m["elapsed_sec"] for _, m in manifests), 2),
        "cells": cells,
        "instances": records,
    }

    with open(os.path.join(dest, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", required=True,
                    help="directory holding shard-N/ trees")
    ap.add_argument("--out", default=os.path.join(ROOT, "compositions"))
    ap.add_argument("--expected-shards", type=int, default=20)
    ap.add_argument("--variant", choices=("A", "B", "both"), default="both")
    args = ap.parse_args()

    shard_dirs = sorted(glob.glob(os.path.join(args.shards, "comp-shard-*")))
    if len(shard_dirs) != args.expected_shards:
        raise SystemExit("expected %d shard dirs, found %d"
                         % (args.expected_shards, len(shard_dirs)))

    variants = ("A", "B") if args.variant == "both" else (args.variant,)
    for v in variants:
        m = merge_variant(v, shard_dirs, args.out, args.expected_shards)
        print("variant %s: delivered %d of %d (%dW/%dA), %d waived, ratio %s"
              % (v, m["delivered"], m["lattice_target"], m["winners"],
                 m["added"], m["waived"], m["realised_ratio"]))
        print("  -> %s" % os.path.join(args.out, "variant_%s" % v, "manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
