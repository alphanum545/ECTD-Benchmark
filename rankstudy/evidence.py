"""Evidence checks and summaries retained from the fixed mixed study."""

from __future__ import annotations

import argparse

from collections import Counter

from contextlib import ExitStack

import csv

from datetime import datetime, timezone

import gzip

import hashlib

import json

import math

from pathlib import Path

METHODS = ("ECTD", "AEFT", "LSTD", "BPPTS", "HEFT", "IPEFT")

MODES = ("append", "insertion")

FAMILIES = ("FFT", "GE", "Genome", "LA", "LIGO", "Montage")

SOURCE_KEYS = {"ECTD": "ECTD", "AEFT": "AEFT-ref", "LSTD": "LSTD-ref",
               "BPPTS": "BPPTS-ref", "HEFT": "HEFT", "IPEFT": "IPEFT"}

REL_TOL, ABS_TOL = 1e-12, 1e-9

def require(condition, message):
    if not condition:
        raise ValueError(message)

def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def id_set_hash(identifiers):
    return hashlib.sha256("\n".join(sorted(identifiers)).encode()).hexdigest()

def strictly_less(a, b):
    return a < b and not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)

def read_gzip_records(path):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            require(record["id"] not in result, f"duplicate ID in {Path(path).name}")
            result[record["id"]] = record
    return result

def inspect_inputs(path):
    """Validate all core input hashes while retaining only lightweight metadata."""
    result = {}
    with gzip.open(path, "rb") as stream:
        for line in stream:
            record = json.loads(line)
            identifier = record["id"]
            require(identifier not in result, "duplicate generated input ID")
            core = {key: record[key] for key in ("n", "p", "costs", "edges")}
            require(type(core["n"]) is int and core["n"] > 0, "invalid task count")
            require(type(core["p"]) is int and core["p"] > 0, "invalid processor count")
            require(len(core["costs"]) == core["n"] and
                    all(len(row) == core["p"] for row in core["costs"]), "invalid cost dimensions")
            require(all(type(v) is int and v >= 0 for row in core["costs"] for v in row),
                    "generated execution costs must be nonnegative integers")
            require(all(len(edge) == 3 and all(type(v) is int for v in edge)
                        and 0 <= edge[0] < core["n"] and 0 <= edge[1] < core["n"]
                        and edge[0] != edge[1] and edge[2] >= 0 for edge in core["edges"]),
                    "invalid generated edge")
            require(hashlib.sha256(json_bytes(core)).hexdigest() == record["input_sha256"],
                    f"generated input hash mismatch: {identifier}")
            require(record["source_sha256"] == record["input_sha256"], "synthetic source hash mismatch")
            require(record["family"] in FAMILIES and record.get("synthetic") is True,
                    "unexpected family or synthetic status")
            result[identifier] = {k: v for k, v in record.items() if k not in {"costs", "edges"}}
    return result

def load_evidence(directory):
    paths = {name: directory / name for name in (
        "candidates.jsonl.gz", "original_results.jsonl.gz", "ipeft_pool_results.jsonl.gz",
        "full_pool_all_3072_results.csv", "original_run_metadata.json")}
    hashes = {name: file_hash(path) for name, path in paths.items()}
    run = json.loads(paths["original_run_metadata.json"].read_text())
    require(hashes["candidates.jsonl.gz"] == run["candidates_sha256"], "original candidate archive changed")
    require(hashes["original_results.jsonl.gz"] == run["results_sha256"], "original result archive changed")
    inputs = inspect_inputs(paths["candidates.jsonl.gz"])
    original = read_gzip_records(paths["original_results.jsonl.gz"])
    ipeft = read_gzip_records(paths["ipeft_pool_results.jsonl.gz"])
    with paths["full_pool_all_3072_results.csv"].open(newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    comparison = {row["id"]: row for row in csv_rows}
    require(len(csv_rows) == len(comparison) == len(inputs) == 3072, "unexpected or duplicate pool count")
    require(set(inputs) == set(original) == set(ipeft) == set(comparison), "input/result/CSV ID sets differ")
    scores = {}
    inherited_schedule_count = 0
    for identifier, record in inputs.items():
        old, new, row = original[identifier], ipeft[identifier], comparison[identifier]
        require(record["input_sha256"] == old["input_sha256"] == new["source_sha256"] == row["input_sha256"],
                f"input/result identity mismatch: {identifier}")
        require(record["family"] == old["family"] == new["family"] == row["family"], "family mismatch")
        require(int(row["n"]) == record["n"] and int(row["p"]) == record["p"], "CSV shape metadata mismatch")
        require(old["valid"] is True and row["valid"] == "True", "invalid source trial")
        modes = {}
        for mode in MODES:
            require(len(old["placements"][mode]) == 11, "incomplete original method suite")
            for outcome in old["placements"][mode].values():
                require(outcome["valid"] is True, "invalid original source schedule")
                inherited_schedule_count += 1
            mode_scores = {}
            for method in METHODS:
                outcome = new["modes"][mode] if method == "IPEFT" else old["placements"][mode][SOURCE_KEYS[method]]
                require(outcome["valid"] is True and not outcome.get("errors"), "invalid retained source schedule")
                value = float(outcome["makespan"])
                require(math.isfinite(value) and value > 0, "invalid makespan")
                require(value == float(row[f"{mode}_{SOURCE_KEYS[method]}_makespan"]),
                        f"CSV/result makespan disagreement: {identifier}/{mode}/{method}")
                horizon = float(outcome["execution_horizon"])
                copies = outcome["duplicate_count"]
                work = 0.0 if method == "IPEFT" else float(outcome["duplicate_work"])
                require(math.isfinite(horizon) and horizon >= value and type(copies) is int and copies >= 0,
                        "invalid execution horizon or duplicate count")
                require(math.isfinite(work) and work >= 0, "invalid duplicate work")
                require(method != "IPEFT" or copies == 0, "IPEFT unexpectedly contains duplicates")
                fingerprint = outcome["schedule_sha256"]
                require(len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint),
                        "invalid schedule fingerprint")
                mode_scores[method] = {"makespan": value, "execution_horizon": horizon,
                                       "duplicate_count": copies, "duplicate_work": work,
                                       "schedule_sha256": fingerprint}
            modes[mode] = mode_scores
        scores[identifier] = modes
    require(inherited_schedule_count == 67584, "original schedule count mismatch")
    return inputs, scores, hashes

def classify(placements):
    wins, losses = [], []
    for mode in MODES:
        row = placements[mode]
        candidate = row["ECTD"]["makespan"]
        baselines = [row[method]["makespan"] for method in METHODS if method != "ECTD"]
        wins.append(all(strictly_less(candidate, baseline) for baseline in baselines))
        losses.append(any(strictly_less(baseline, candidate) for baseline in baselines))
    if all(wins):
        return "ectd_strict_both"
    if all(losses):
        return "ectd_loss_both"
    return "other"

def summarize(identifiers, scores):
    result = {"instances": len(identifiers), "placements": {}}
    for mode in MODES:
        sole = Counter({method: 0 for method in METHODS})
        tied = Counter({method: 0 for method in METHODS})
        tie_groups = Counter()
        logs = {method: [] for method in METHODS}
        pairwise = {method: Counter({"wins": 0, "ties": 0, "losses": 0}) for method in METHODS[1:]}
        copies, work, overruns = Counter(), Counter(), Counter()
        for identifier in identifiers:
            row = scores[identifier][mode]
            values = {m: row[m]["makespan"] for m in METHODS}
            best = min(values.values())
            best_methods = [m for m in METHODS if math.isclose(values[m], best, rel_tol=REL_TOL, abs_tol=ABS_TOL)]
            if len(best_methods) == 1:
                sole[best_methods[0]] += 1
            else:
                tied.update(best_methods)
                tie_groups[" + ".join(best_methods)] += 1
            for method in METHODS:
                logs[method].append(math.log(values[method]))
                copies[method] += row[method]["duplicate_count"]
                work[method] += row[method]["duplicate_work"]
                overruns[method] += strictly_less(values[method], row[method]["execution_horizon"])
                if method != "ECTD":
                    relation = "wins" if strictly_less(values["ECTD"], values[method]) else "losses" if strictly_less(values[method], values["ECTD"]) else "ties"
                    pairwise[method][relation] += 1
        geomeans = {method: math.exp(math.fsum(values) / len(identifiers)) for method, values in logs.items()}
        result["placements"][mode] = {
            "ranking_lowest_makespan_first": sorted(METHODS, key=lambda m: (geomeans[m], m)),
            "geometric_makespans": geomeans,
            "sole_winners": dict(sole), "tied_best_instances": sum(tie_groups.values()),
            "tied_best_membership": dict(tied), "tie_groups": dict(tie_groups),
            "win_tie_loss_vs_best": {m: {"strict_wins": sole[m], "tied_best": tied[m],
                                          "beaten": len(identifiers) - sole[m] - tied[m]} for m in METHODS},
            "ECTD_pairwise": {m: dict(counts) | {"geometric_makespan_reduction_percent": 100 * (1 - geomeans["ECTD"] / geomeans[m])}
                              for m, counts in pairwise.items()},
            "duplicate_count_totals": dict(copies), "duplicate_work_totals": dict(work),
            "horizon_exceeds_makespan_instances": dict(overruns),
        }
        require(sum(sole.values()) + sum(tie_groups.values()) == len(identifiers), "winner accounting mismatch")
    result["both_mode_classifications"] = dict(Counter(classify(scores[i]) for i in identifiers))
    return result

def export_inputs(source, output, memberships):
    counts = Counter()
    with ExitStack() as stack:
        streams = {}
        for filename in memberships:
            raw = stack.enter_context((output / filename).open("wb"))
            streams[filename] = stack.enter_context(gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6))
        with gzip.open(source, "rb") as stream:
            for line in stream:
                identifier = json.loads(line)["id"]
                for filename, members in memberships.items():
                    if identifier in members:
                        streams[filename].write(line)
                        counts[filename] += 1
    require(all(counts[name] == len(members) for name, members in memberships.items()), "input export count mismatch")
    return {name: {"records": counts[name], "sha256": file_hash(output / name),
                   "bytes": (output / name).stat().st_size, "records_copied_byte_for_byte": True}
            for name in memberships}
