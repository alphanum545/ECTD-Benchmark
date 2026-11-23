"""Check the frozen Python IPEFT policy against the exact pinned C++ program.

Run from any directory with --inputs pointing to the complete generated
3,072-candidate JSONL gzip. The 120 inputs are selected without outcomes:
20 per family, five per processor count, covering all four regimes and all
three source sizes in every family/processor stratum. No source is edited.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from ectdbench.engine import validate_schedule
from ectdbench.ipeft import run_ipeft
from ectdbench.model import Problem

FAMILIES = ("FFT", "GE", "Genome", "LA", "LIGO", "Montage")
PROCESSORS = (8, 16, 32, 64)
REGIMES = ("entry_transfer", "mixed_affinity", "lookahead_traps", "branch_affinity")
PINNED_BLOB = "841cba1c1840d8d9c50b484f4386aeedc96c6418"
PINNED_COMMIT = "3741b6d4a61a9599284f78c23a826658b81f7500"


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def priority(record):
    return hashlib.sha256(("ipeft-native-parity-v1/" + record["id"]).encode()).hexdigest()


def select_inputs(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    bins = defaultdict(list)
    for record in records:
        bins[record["family"], record["p"]].append(record)
    selected = []
    for family in FAMILIES:
        for p_index, p in enumerate(PROCESSORS):
            pool = sorted(bins[family, p], key=priority)
            sizes = sorted({r["provenance"]["original_n"] for r in pool})
            if len(sizes) != 3:
                raise ValueError(f"Expected three sizes in {(family,p)}, found {sizes}")
            used = set()
            for r_index, regime in enumerate(REGIMES):
                size = sizes[(r_index + p_index) % len(sizes)]
                matches = [r for r in pool if r["provenance"]["regime"] == regime
                           and r["provenance"]["original_n"] == size]
                if not matches:
                    raise ValueError(f"Missing {(family,p,size,regime)} source stratum")
                selected.append(matches[0])
                used.add(matches[0]["id"])
            selected.append(next(r for r in pool if r["id"] not in used))
    if len(selected) != 120 or len({r["id"] for r in selected}) != 120:
        raise ValueError("The deterministic audit must contain 120 distinct inputs")
    return selected, len(records)


def native_input(record):
    n, p = record["n"], record["p"]
    if len(record["costs"]) != n or any(len(r) != p for r in record["costs"]):
        raise ValueError("Malformed cost matrix")
    matrix = [[-1] * n for _ in range(n)]
    for u, v, communication in record["edges"]:
        if type(communication) is not int:
            raise ValueError("Native parity input communication must be integer")
        matrix[u][v] = communication
    if any(type(value) is not int for row in record["costs"] for value in row):
        raise ValueError("Native parity execution costs must be integer")
    rows = [f"{n} {p}"]
    rows.extend(" ".join(map(str, row)) for row in record["costs"])
    rows.extend(" ".join(map(str, row)) for row in matrix)
    return "\n".join(rows) + "\n"


def parse_native(output, n):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    order = [int(x) - 1 for x in lines[0].split()]
    if len(order) != n or set(order) != set(range(n)):
        raise ValueError("Native output order is not a task permutation")
    if lines[1].split() != ["TASKS", "AST", "AFT", "PRO"]:
        raise ValueError("Unexpected native schedule header")
    events = {}
    for line in lines[2:]:
        task, start, finish, processor = map(int, line.split())
        events[task - 1] = (start, finish, processor - 1)
    if len(events) != n or set(events) != set(range(n)):
        raise ValueError("Native output misses a task")
    return order, events


def evaluate(record, executable):
    result = {"id": record["id"], "family": record["family"], "n": record["n"],
              "original_n": record["provenance"]["original_n"], "p": record["p"],
              "regime": record["provenance"]["regime"],
              "input_sha256": record["input_sha256"]}
    try:
        native = subprocess.run([str(executable)], input=native_input(record), text=True,
                                capture_output=True, check=True, timeout=30)
        order, native_events = parse_native(native.stdout, record["n"])
        problem = Problem.from_record(record)
        schedule = run_ipeft(problem, insertion=False)
        checked = validate_schedule(problem, schedule)
        differences = []
        for task in range(record["n"]):
            event = schedule.primary[task]
            actual = (event.start, event.finish, event.processor)
            if native_events[task] != actual:
                differences.append({"task": task, "native": native_events[task], "python": actual})
        result.update(order_matches=order == schedule.selection_order,
                      task_events_compared=record["n"],
                      task_events_match=not differences,
                      differing_task_count=len(differences),
                      first_differences=differences[:10],
                      native_makespan=max(event[1] for event in native_events.values()),
                      python_makespan=schedule.makespan,
                      python_schedule_valid=checked["valid"],
                      validation_errors=checked["errors"])
        result["passed"] = result["order_matches"] and result["task_events_match"] and checked["valid"]
    except Exception as exc:
        result.update(passed=False, error=repr(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--native-source", type=Path, default=PROJECT / "source_evidence/ipeft.cpp")
    parser.add_argument("--output", type=Path, default=PROJECT / "validation/ipeft_native_parity.json")
    args = parser.parse_args(argv)
    source_bytes = args.native_source.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(source_bytes)).encode() + b"\0" + source_bytes).hexdigest()
    if blob != PINNED_BLOB:
        raise ValueError("C++ source differs from the pinned upstream blob")
    compiler = shutil.which("g++")
    if not compiler:
        raise RuntimeError("g++ is required for native parity verification")
    before = {p: file_hash(PROJECT / p) for p in
              ("ectdbench/ipeft.py", "ectdbench/model.py", "ectdbench/engine.py")}
    selected, pool_size = select_inputs(args.inputs)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="ectd-ipeft-native-") as tmp:
        executable = Path(tmp) / "ipeft"
        flags = ["-std=c++17", "-O2"]
        subprocess.run([compiler, *flags, str(args.native_source), "-o", str(executable)],
                       check=True, capture_output=True, text=True, timeout=60)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda record: evaluate(record, executable), selected))
    after = {p: file_hash(PROJECT / p) for p in before}
    if before != after:
        raise RuntimeError("A policy or shared-engine file changed during this audit")
    failures = [r for r in results if not r["passed"]]
    coverage = {}
    for family in FAMILIES:
        items = [r for r in selected if r["family"] == family]
        coverage[family] = {
            "cases": len(items),
            "processors": dict(sorted(Counter(r["p"] for r in items).items())),
            "original_task_counts": sorted({r["provenance"]["original_n"] for r in items}),
            "actual_task_counts": sorted({r["n"] for r in items}),
            "regimes": dict(sorted(Counter(r["provenance"]["regime"] for r in items).items())),
        }
    receipt = {
        "audit": "native C++ versus Python IPEFT append schedule parity",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_repository": "https://github.com/alphanum545/scheduling-benchmark",
        "source_commit": PINNED_COMMIT,
        "source_path": "algorithms/makespan/ipeft.cpp",
        "native_source_git_blob": blob,
        "native_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "native_source_bytes": len(source_bytes),
        "python_policy_sources_sha256": before,
        "source_files_unchanged": before == after,
        "input_archive_sha256": file_hash(args.inputs),
        "input_pool_size": pool_size,
        "compiler": subprocess.run([compiler, "--version"], capture_output=True, text=True,
                                   check=True).stdout.splitlines()[0],
        "compiler_flags": flags,
        "python": platform.python_version(),
        "selection": "Fixed SHA256 order, five cases per family/processor stratum; all four regimes and all three original sizes covered in every stratum; no outcome-based choice.",
        "scope": "Append placement only; the native program has no insertion implementation. This is code-level parity on 120 inputs, not a proof for all possible inputs or external publication fidelity.",
        "cases": len(results), "passed": len(results) - len(failures),
        "failed": len(failures),
        "task_events_compared": sum(r.get("task_events_compared", 0) for r in results),
        "elapsed_seconds_including_compile": round(time.perf_counter() - started, 3),
        "coverage": coverage,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("cases", "passed", "failed", "task_events_compared", "elapsed_seconds_including_compile")}))
    if failures:
        print(json.dumps({"first_failures": failures[:3]}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
