"""Replay all six fixed policies and compare every saved schedule fingerprint."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

from ectdbench.engine import validate_schedule
from ectdbench.model import Problem
from .algorithms import ALGORITHMS
from .build import PROFILES


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def evaluate(record):
    problem = Problem.from_record(record)
    result = {"id": record["id"], "family": record["family"],
              "input_sha256": record["input_sha256"], "placements": {}}
    for mode in ("append", "insertion"):
        outcomes = {}
        for name, method in ALGORITHMS.items():
            schedule = method(problem, insertion=mode == "insertion")
            checked = validate_schedule(problem, schedule)
            outcomes[name] = {
                "makespan": schedule.makespan,
                "execution_horizon": schedule.execution_horizon,
                "duplicate_count": schedule.duplicate_count,
                "duplicate_work": schedule.duplicate_work,
                "schedule_sha256": hashlib.sha256(json_bytes(schedule.as_dict())).hexdigest(),
                "valid": checked["valid"], "errors": checked["errors"],
            }
        result["placements"][mode] = outcomes
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--inputs")
    parser.add_argument("--expected")
    parser.add_argument("--summary")
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    project = Path(__file__).resolve().parents[1]
    cohort = project / "cohorts" / args.profile
    args.inputs = args.inputs or str(cohort / "inputs.jsonl.gz")
    args.expected = args.expected or str(cohort / "expected_results.jsonl.gz")
    args.summary = args.summary or str(cohort / "summary.json")
    if args.workers < 1:
        parser.error("workers must be positive")
    output = Path(args.output)
    if output.exists():
        parser.error("refusing to overwrite an existing replay")
    records = sorted(read_jsonl(args.inputs), key=lambda row: row["id"])
    expected_rows = read_jsonl(args.expected)
    expected = {row["id"]: row for row in expected_rows}
    ids = [row["id"] for row in records]
    if len(set(ids)) != len(records) or len(expected) != len(expected_rows) or set(ids) != set(expected):
        raise ValueError("input/expected records are not unique and one-to-one")
    summary = json.loads(Path(args.summary).read_text())
    if summary["profile"] != args.profile:
        raise ValueError("summary profile does not match requested profile")
    if len(records) != summary["selected"]["instances"]:
        raise ValueError("cohort count does not match its frozen summary")
    if hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest() != summary["membership_ids_sha256"]:
        raise ValueError("cohort membership does not match its frozen summary")
    for record in records:
        core = {key: record[key] for key in ("n", "p", "costs", "edges")}
        if hashlib.sha256(json_bytes(core)).hexdigest() != record["input_sha256"]:
            raise ValueError("input core digest mismatch")
    project = Path(__file__).resolve().parents[1]
    sources = sorted(p for folder in ("ectdbench", "rankstudy")
                     for p in (project / folder).rglob("*.py") if "__pycache__" not in p.parts)
    metadata = {
        "execution_environment": "local", "ci": None,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_file_sha256": file_hash(args.inputs),
        "expected_file_sha256": file_hash(args.expected),
        "summary_file_sha256": file_hash(args.summary),
        "profile": summary["profile"],
        "source_sha256": {p.relative_to(project).as_posix(): file_hash(p) for p in sources},
        "workers": args.workers, "python": sys.version, "numpy": np.__version__,
        "platform": platform.platform(), "algorithms": list(ALGORITHMS),
        "placements": ["append", "insertion"], "input_count": len(records),
    }
    output.mkdir(parents=True)
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    failures = []
    checked = 0
    mismatches = 0
    invalid = 0
    families = Counter()
    start = time.perf_counter()
    raw_path = output / "replayed_results.jsonl.gz"
    with raw_path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6) as stream:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                for count, result in enumerate(pool.map(evaluate, records, chunksize=4), start=1):
                    previous = expected[result["id"]]
                    if previous["input_sha256"] != result["input_sha256"]:
                        raise ValueError("input digest mismatch in expected result")
                    families[result["family"]] += 1
                    for mode, values in result["placements"].items():
                        if set(previous["placements"][mode]) != set(ALGORITHMS):
                            raise ValueError("expected result has wrong algorithm set")
                        for name, outcome in values.items():
                            saved = previous["placements"][mode][name]
                            checked += 1
                            bad_fields = [key for key in ("makespan", "execution_horizon", "duplicate_count", "duplicate_work", "schedule_sha256")
                                          if outcome[key] != saved[key]]
                            mismatches += bool(bad_fields)
                            invalid += not outcome["valid"]
                            if bad_fields or not outcome["valid"]:
                                failures.append({"id": result["id"], "placement": mode, "algorithm": name,
                                                 "mismatched_fields": bad_fields, "errors": outcome["errors"]})
                    stream.write(json_bytes(result) + b"\n")
                    if count % 300 == 0 or count == len(records):
                        print(json.dumps({"inputs_replayed": count, "schedules_checked": checked,
                                          "mismatched_schedules": mismatches, "invalid_schedules": invalid,
                                          "elapsed_seconds": round(time.perf_counter() - start, 2)}), flush=True)
    changed_sources = [name for name, digest in metadata["source_sha256"].items()
                       if file_hash(project / name) != digest]
    metadata.update(
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.perf_counter() - start,
        checked_schedules=checked, mismatched_schedules=mismatches,
        invalid_schedules=invalid, families=dict(families),
        changed_source_files=changed_sources, failures=failures,
        replayed_results_sha256=file_hash(raw_path),
        passed=(checked == len(records) * 6 * 2 and not failures and not changed_sources),
    )
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": metadata["passed"], "checked_schedules": checked,
                      "invalid_schedules": invalid, "mismatched_schedules": mismatches}), flush=True)
    return 0 if metadata["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
