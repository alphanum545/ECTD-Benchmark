"""Import frozen study bytes, replay 20 shards, and publish verified CI receipts."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPOSITORY = "alphanum545/ECTD-Benchmark"
BRANCH = "research/ranking-revision-2026-11-23"
PROFILES = {"latest_497": 497, "full_order_209": 209, "full_order_225": 225}
MODES = ("append", "insertion")
ALGORITHM_NAMES = {"ECTD", "AEFT", "BPPTS", "HEFT", "LSTD", "IPEFT"}
FIELDS = ("makespan", "execution_horizon", "duplicate_count", "duplicate_work", "schedule_sha256")
SHARDS = 20
WORKERS = 4
UNION_INPUTS = 546
CORE_FILES = 83
HELPERS = ("ci/run_study.py", "ci/transport_manifest.json", "ci/README.md")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_path(root, relative):
    path = PurePosixPath(relative)
    require(isinstance(relative, str) and str(path) == relative and not path.is_absolute()
            and bool(path.parts) and not {"..", ".git"}.intersection(path.parts),
            f"Unsafe path: {relative!r}")
    current = root
    for part in path.parts:
        current /= part
        require(not current.is_symlink(), f"Symlink rejected: {relative}")
    require(current.resolve().is_relative_to(root.resolve()), f"Path escapes workspace: {relative}")
    return current


def manifest(root=ROOT):
    value = load(root / "ci/transport_manifest.json")
    require(value["schema_version"] == 1 and value["repository"] == REPOSITORY
            and value["branch"] == BRANCH, "Unexpected transport identity")
    entries = {row["path"]: row for row in value["core_files"]}
    require(len(entries) == len(value["core_files"]) == CORE_FILES, "Core manifest must list exactly 83 unique files")
    for row in entries.values():
        safe_path(root, row["path"])
        require(row["mode"] == "100644", "Only ordinary nonexecutable study files are allowed")
    rebuilt = value["regenerated_paths"]
    require(len(rebuilt) == len(set(rebuilt)) == 18, "Expected 18 regenerable cohort files")
    transported = [row["path"] for row in value["transported_files"]]
    direct = value["direct_paths"]
    require(len(direct + transported + rebuilt) == CORE_FILES
            and set(direct + transported + rebuilt) == set(entries), "Transport partition is incomplete or duplicated")
    parts = [part["path"] for row in value["transported_files"] for part in row["chunks"]]
    require(len(parts) == len(set(parts)), "Duplicate transport chunk")
    for name in parts:
        safe_path(root, name)
        require(name.startswith("transport/chunks/") and name.endswith(".part"), "Unowned chunk path")
    return value, entries


def verify_bytes(data, spec, label):
    require(len(data) == spec["size"] and digest(data) == spec["sha256"], f"Byte digest mismatch: {label}")
    if "git_blob_sha1" in spec:
        blob = b"blob " + str(len(data)).encode() + b"\0" + data
        require(hashlib.sha1(blob).hexdigest() == spec["git_blob_sha1"], f"Git blob mismatch: {label}")


def core_tree(entries):
    tree = {}
    for row in entries.values():
        cursor = tree
        parts = PurePosixPath(row["path"]).parts
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = row["git_blob_sha1"]

    def visit(node):
        body = b""
        for name in sorted(node, key=lambda key: (key + ("/" if isinstance(node[key], dict) else "")).encode()):
            child = node[name]
            folder = isinstance(child, dict)
            body += (b"40000 " if folder else b"100644 ") + name.encode() + b"\0"
            body += visit(child) if folder else bytes.fromhex(child)
        return hashlib.sha1(b"tree " + str(len(body)).encode() + b"\0" + body).digest()
    return visit(tree).hex()


def verify_core(root=ROOT):
    value, entries = manifest(root)
    for name, spec in entries.items():
        verify_bytes(safe_path(root, name).read_bytes(), spec, name)
    tree = core_tree(entries)
    require(tree == value["expected_core_tree_sha"], "Frozen core tree differs")
    return {"file_count": len(entries), "bytes": sum(row["size"] for row in entries.values()),
            "expected_core_tree_sha": tree, "all_sha256_and_git_blob_sha1_match": True}


def context():
    import numpy
    require(sys.version_info[:2] == (3, 12), "Python 3.12 is required")
    require(numpy.__version__ == "2.3.5", "numpy 2.3.5 is required")
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    ci = None
    if in_actions:
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
                and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH,
                "This workflow is restricted to the authorized repository and feature branch")
        keys = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF", "GITHUB_JOB",
                "RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "ImageOS", "ImageVersion")
        ci = {key: os.environ.get(key) for key in keys}
        ci["url"] = f"https://github.com/{REPOSITORY}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return {"execution_environment": "github-actions" if in_actions else "local",
            "ci": ci, "python": sys.version, "numpy": numpy.__version__,
            "platform": platform.platform(), "logical_cpus_observed": os.cpu_count(),
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": digest((ROOT / "ci/transport_manifest.json").read_bytes()),
            "ci_script_sha256": digest(Path(__file__).read_bytes())}


def source_hashes(root=ROOT):
    return {path.relative_to(root).as_posix(): digest(path.read_bytes())
            for folder in ("ectdbench", "rankstudy") for path in sorted((root / folder).glob("*.py"))}


def prepare(args):
    metadata = context()
    value, entries = manifest()
    restored = []
    for row in value["transported_files"]:
        target = safe_path(ROOT, row["path"])
        if target.exists():
            verify_bytes(target.read_bytes(), entries[row["path"]], row["path"])
            continue
        blocks = []
        for chunk in row["chunks"]:
            block = safe_path(ROOT, chunk["path"]).read_bytes()
            verify_bytes(block, chunk, chunk["path"])
            blocks.append(block)
        wire = b"".join(blocks)
        require(len(wire) == row["wire_size"] and digest(wire) == row["wire_sha256"], "Transport wire mismatch")
        require(row["codec"] in ("raw", "gzip"), "Unknown transport codec")
        data = gzip.decompress(wire) if row["codec"] == "gzip" else wire
        verify_bytes(data, entries[row["path"]], row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        restored.append(row["path"])
    for name in value["direct_paths"]:
        verify_bytes(safe_path(ROOT, name).read_bytes(), entries[name], name)
    before = source_hashes()
    with tempfile.TemporaryDirectory(prefix="ectd-build-") as temporary:
        output = Path(temporary) / "cohorts"
        subprocess.run([sys.executable, "-m", "rankstudy.build", "--output", str(output)], cwd=ROOT, check=True)
        build_receipt = load(output / "build_summary.json")
        require(build_receipt["full_pool_input_hashes_checked"] == 3072
                and build_receipt["retained_algorithm_mode_makespans_checked_against_csv"] == 36864,
                "Source evidence validation is incomplete")
        for name in value["regenerated_paths"]:
            require(name.startswith("cohorts/"), "Regeneration target is outside cohorts")
            data = (output / PurePosixPath(name).relative_to("cohorts")).read_bytes()
            verify_bytes(data, entries[name], name)
            target = safe_path(ROOT, name)
            if target.exists():
                verify_bytes(target.read_bytes(), entries[name], name)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        metadata["source_validation"] = {
            "full_pool_input_hashes_checked": build_receipt["full_pool_input_hashes_checked"],
            "retained_algorithm_mode_makespans_checked_against_csv": build_receipt["retained_algorithm_mode_makespans_checked_against_csv"],
            "pool_group_counts": build_receipt["pool_group_counts"],
            "source_files_sha256": build_receipt["source_files_sha256"],
        }
    require(source_hashes() == before, "Study source files changed during build")
    metadata.update(core=verify_core(), restored_paths=restored,
                    regenerated_paths=value["regenerated_paths"],
                    regenerated_files_byte_identical=18, source_sha256=before,
                    passed=True, finished_at_utc=datetime.now(timezone.utc).isoformat())
    artifact = Path(args.output).resolve()
    require(not artifact.exists(), "Artifact directory already exists")
    artifact.mkdir(parents=True)
    for name in list(entries) + list(HELPERS):
        source = safe_path(ROOT, name)
        target = safe_path(artifact, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    write_json(artifact / "ci/prepare_receipt.json", metadata)
    require(not (artifact / ".git").exists(), "Git metadata must never enter the workspace artifact")
    print(json.dumps({"prepared": True, "core_files_verified": CORE_FILES, "regenerated_files_verified": 18}))


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def union_data(root=ROOT):
    inputs, expected, memberships = {}, {}, {}
    for profile, count in PROFILES.items():
        folder = root / "cohorts" / profile
        records = read_rows(folder / "inputs.jsonl.gz")
        saved = read_rows(folder / "expected_results.jsonl.gz")
        rows = {row["id"]: row for row in records}
        outcomes = {row["id"]: row for row in saved}
        summary = load(folder / "summary.json")
        ids = sorted(rows)
        require(len(rows) == len(records) == len(saved) == len(outcomes) == count
                and set(rows) == set(outcomes), f"Invalid {profile} membership")
        require(summary["profile"] == profile and summary["selected"]["instances"] == count
                and digest("\n".join(ids).encode()) == summary["membership_ids_sha256"], "Frozen membership mismatch")
        memberships[profile] = ids
        for identifier in ids:
            record, outcome = rows[identifier], outcomes[identifier]
            core = {key: record[key] for key in ("n", "p", "costs", "edges")}
            require(digest(canonical(core)) == record["input_sha256"] == outcome["input_sha256"], "Input core hash mismatch")
            require(record["family"] == outcome["family"], "Input family mismatch")
            require(set(outcome["placements"]) == set(MODES), "Expected placements differ")
            for mode in MODES:
                require(set(outcome["placements"][mode]) == ALGORITHM_NAMES, "Expected algorithm set differs")
            if identifier in inputs:
                require(inputs[identifier] == record and expected[identifier] == outcome,
                        "Profiles disagree about an overlapping input or saved result")
            inputs[identifier], expected[identifier] = record, outcome
    require(len(inputs) == UNION_INPUTS and sum(map(len, memberships.values())) == 931, "Unexpected union coverage")
    return inputs, expected, memberships


def compare(result, expected):
    failures = []
    require(set(result["placements"]) == set(MODES), "Replayed placement set differs")
    require(all(result[key] == expected[key] for key in ("id", "family", "input_sha256")), "Replayed identity differs")
    for mode in MODES:
        require(set(result["placements"][mode]) == ALGORITHM_NAMES, "Replayed algorithm set differs")
        for name in sorted(ALGORITHM_NAMES):
            outcome = result["placements"][mode][name]
            saved = expected["placements"][mode][name]
            fields = [key for key in FIELDS if outcome[key] != saved[key]]
            if fields or outcome["valid"] is not True or outcome["errors"]:
                failures.append({"id": result["id"], "placement": mode, "algorithm": name,
                                 "mismatched_fields": fields, "valid": outcome["valid"], "errors": outcome["errors"]})
    return failures


def shard(args):
    from rankstudy.algorithms import ALGORITHMS
    from rankstudy.replay import evaluate
    require(set(ALGORITHMS) == ALGORITHM_NAMES, "Registered algorithms differ")
    require(0 <= args.index < SHARDS, "Shard index must be 0 through 19")
    metadata = context()
    metadata["core"] = verify_core()
    inputs, expected, memberships = union_data()
    ids = sorted(inputs)[args.index::SHARDS]
    before = source_hashes()
    metadata.update(shard_index=args.index, shard_count=SHARDS, workers=WORKERS,
                    source_sha256=before, input_ids=ids, input_count=len(ids),
                    profile_memberships={name: [i for i in ids if i in group] for name, group in memberships.items()},
                    fields_compared=list(FIELDS), algorithms=sorted(ALGORITHM_NAMES), placements=list(MODES))
    output = Path(args.output).resolve()
    require(not output.exists(), "Refusing to overwrite an existing shard")
    output.mkdir(parents=True)
    write_json(output / "run_metadata.json", metadata)
    start = time.perf_counter()
    failures = []
    result_path = output / "replayed_results.jsonl.gz"
    with result_path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6) as stream:
            with ProcessPoolExecutor(max_workers=WORKERS) as pool:
                for count, result in enumerate(pool.map(evaluate, [inputs[i] for i in ids], chunksize=1), 1):
                    failures.extend(compare(result, expected[result["id"]]))
                    stream.write(canonical(result) + b"\n")
                    print(json.dumps({"shard": args.index, "replayed_inputs": count,
                                      "checked_schedules": count * 12, "failures": len(failures)}), flush=True)
    require(source_hashes() == before, "Study source files changed during replay")
    metadata.update(checked_schedules=len(ids) * 12, failures=failures,
                    mismatched_schedules=sum(bool(row["mismatched_fields"]) for row in failures),
                    invalid_schedules=sum(row["valid"] is not True or bool(row["errors"]) for row in failures),
                    elapsed_seconds=time.perf_counter() - start,
                    replayed_results_sha256=digest(result_path.read_bytes()),
                    finished_at_utc=datetime.now(timezone.utc).isoformat(), passed=not failures)
    write_json(output / "run_metadata.json", metadata)
    require(not failures, "Schedule replay differs from frozen expected results")


def same_run(receipt, current):
    require(receipt["execution_environment"] == current["execution_environment"], "Receipt execution environment differs")
    require(receipt["manifest_sha256"] == current["manifest_sha256"]
            and receipt["ci_script_sha256"] == current["ci_script_sha256"], "CI source identity differs")
    if current["ci"]:
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF"):
            require(receipt["ci"][key] == current["ci"][key], f"Receipt belongs to another run: {key}")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def finalize(args):
    from rankstudy.evidence import summarize
    current = context()
    prepared = Path(args.prepared).resolve()
    require((prepared / "ci/transport_manifest.json").read_bytes() == (ROOT / "ci/transport_manifest.json").read_bytes(),
            "Prepared manifest differs from trigger checkout")
    require((prepared / "ci/run_study.py").read_bytes() == Path(__file__).read_bytes(), "Prepared CI script differs")
    core = verify_core(prepared)
    preparation = load(prepared / "ci/prepare_receipt.json")
    same_run(preparation, current)
    require(preparation["passed"] and preparation["regenerated_files_byte_identical"] == 18, "Preparation failed")
    inputs, expected, memberships = union_data(prepared)
    source_digest = source_hashes(prepared)
    all_results = {}
    receipts = []
    shard_root = Path(args.shards).resolve()
    for index in range(SHARDS):
        folder = shard_root / f"ectd-shard-{index}"
        receipt = load(folder / "run_metadata.json")
        same_run(receipt, current)
        ids = sorted(inputs)[index::SHARDS]
        require(receipt["shard_index"] == index and receipt["shard_count"] == SHARDS
                and receipt["workers"] == WORKERS and receipt["source_sha256"] == source_digest,
                "Shard configuration differs")
        require(receipt["passed"] and not receipt["failures"] and receipt["mismatched_schedules"] == 0
                and receipt["invalid_schedules"] == 0 and receipt["checked_schedules"] == len(ids) * 12
                and receipt["input_ids"] == ids, "Shard validation failed")
        raw = folder / "replayed_results.jsonl.gz"
        require(digest(raw.read_bytes()) == receipt["replayed_results_sha256"], "Shard artifact hash differs")
        rows = read_rows(raw)
        require([row["id"] for row in rows] == ids, "Shard output membership differs")
        for row in rows:
            require(row["id"] not in all_results, "Duplicate input across shards")
            require(not compare(row, expected[row["id"]]), "Final independent field comparison failed")
            all_results[row["id"]] = row
        receipts.append(receipt)
    require(set(all_results) == set(inputs), "Union replay coverage is incomplete")
    profiles = {}
    scores = {identifier: row["placements"] for identifier, row in all_results.items()}
    for name, ids in memberships.items():
        observed = summarize(ids, scores)
        frozen = load(prepared / "cohorts" / name / "summary.json")["selected"]
        require(observed == frozen, f"Recomputed aggregate result differs: {name}")
        profiles[name] = {"inputs": len(ids), "checked_schedules": len(ids) * 12,
                          "aggregate_exact_match": True, "selected": observed}
    current.update(core=core, shards=SHARDS, workers_per_shard=WORKERS,
                   requested_max_parallel_jobs=SHARDS, unique_inputs_replayed=len(inputs),
                   unique_schedules_checked=len(inputs) * 12,
                   profile_membership_schedules_checked=sum(len(ids) * 12 for ids in memberships.values()),
                   profiles=profiles, invalid_schedules=0, mismatched_schedules=0,
                   source_sha256=source_digest, regenerated_files_byte_identical=18,
                   interpretation="Outcome-selected exploratory cohorts; aggregate order was a membership constraint.",
                   finished_at_utc=datetime.now(timezone.utc).isoformat(), passed=True)
    if current["ci"]:
        run_id = current["ci"]["GITHUB_RUN_ID"]
        attempt = current["ci"]["GITHUB_RUN_ATTEMPT"]
        require(re.fullmatch(r"[0-9]+", run_id) and re.fullmatch(r"[0-9]+", attempt), "Unsafe run identity")
        receipt_relative = f"validation/github-actions/{run_id}/attempt-{attempt}"
    else:
        receipt_relative = "validation/local-ci-check"
    destination = safe_path(ROOT, receipt_relative)
    require(not destination.exists(), "Run receipt already exists")
    destination.mkdir(parents=True)
    write_json(destination / "summary.json", current)
    write_json(destination / "prepare.json", preparation)
    for index, receipt in enumerate(receipts):
        write_json(destination / "shards" / f"{index}.json", receipt)
        shutil.copyfile(shard_root / f"ectd-shard-{index}" / "replayed_results.jsonl.gz",
                        destination / "shards" / f"{index}.jsonl.gz")
    value, entries = manifest()
    for name, spec in entries.items():
        data = safe_path(prepared, name).read_bytes()
        target = safe_path(ROOT, name)
        if target.exists():
            verify_bytes(target.read_bytes(), spec, name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    verify_core()
    if args.publish:
        require(current["execution_environment"] == "github-actions", "Publishing is only available in GitHub Actions")
        trigger = current["ci"]["GITHUB_SHA"]
        require(git("rev-parse", "HEAD") == trigger, "Checkout is not the triggering commit")
        head = git("ls-remote", "--heads", "origin", "refs/heads/" + BRANCH).split()
        require(head == [trigger, "refs/heads/" + BRANCH], "Feature branch changed; refusing to overwrite another commit")
        removed = []
        for row in value["transported_files"]:
            for chunk in row["chunks"]:
                path = safe_path(ROOT, chunk["path"])
                if path.exists():
                    verify_bytes(path.read_bytes(), chunk, chunk["path"])
                    path.unlink()
                    removed.append(chunk["path"])
        current["transport_chunks_removed"] = removed
        current["parent_commit"] = trigger
        write_json(destination / "summary.json", current)
        subprocess.run(["git", "add", "--", *entries, receipt_relative, *removed], cwd=ROOT, check=True)
        allowed = set(entries) | set(removed)
        staged = git("diff", "--cached", "--name-only").splitlines()
        require(all(name in allowed or name.startswith(receipt_relative + "/") for name in staged), "Unexpected staged path")
        subprocess.run(["git", "-c", "user.name=github-actions[bot]", "-c",
                        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                        "commit", "-m", "Restore frozen study and record verified GitHub Actions reproduction"], cwd=ROOT, check=True)
        # A concurrent branch update is rejected by this ordinary fast-forward push.
        subprocess.run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], cwd=ROOT, check=True)
        published = git("rev-parse", "HEAD")
        require(git("ls-remote", "--heads", "origin", "refs/heads/" + BRANCH).split()[0] == published,
                "Published branch head could not be verified")
        print(json.dumps({"published_commit": published, "receipt_path": receipt_relative}))
    print(json.dumps({"passed": True, "unique_schedules": 6552, "profile_membership_schedules": 11172,
                      "invalid": 0, "mismatches": 0, "receipt_path": receipt_relative}))
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as stream:
            stream.write("## Verified study reproduction\n\n"
                         "83 frozen files and 18 regenerated cohort files matched exactly. "
                         "20 shards replayed 546 unique inputs / 6,552 schedules, covering "
                         "11,172 profile schedule memberships. Zero invalid schedules or mismatches.\n\n"
                         f"Receipts: `{receipt_relative}`. The main branch was not a write target.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("prepare")
    first.add_argument("--output", required=True)
    second = commands.add_parser("shard")
    second.add_argument("--index", type=int, required=True)
    second.add_argument("--output", required=True)
    third = commands.add_parser("finalize")
    third.add_argument("--prepared", required=True)
    third.add_argument("--shards", required=True)
    third.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "shard": shard, "finalize": finalize}[args.command](args)


if __name__ == "__main__":
    main()
