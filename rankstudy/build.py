"""Rebuild three frozen, outcome-selected exploratory cohorts from source evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path

from .evidence import (
    FAMILIES, METHODS, MODES, classify, export_inputs, file_hash, id_set_hash,
    json_bytes, load_evidence, require, summarize,
)

PROJECT = Path(__file__).resolve().parents[1]
PROFILES = {
    "latest_497": "revised_order_near_original_fraction",
    "full_order_209": "full_order_original_fraction_minone",
    "full_order_225": "full_order_majority",
}


def write_membership(path, chosen, inputs, scores):
    fields = ["id", "family", "cohort", "n", "p", "input_sha256", "source_id",
              "parent_source_sha256", "source_topology_sha256", "seed", "regime",
              "entry_treatment", "original_n", "original_root_count"]
    fields += [f"{mode}_{method}_makespan" for mode in MODES for method in METHODS]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for identifier in chosen:
            record = inputs[identifier]
            provenance = record["provenance"]
            row = {"id": identifier, "family": record["family"],
                   "cohort": classify(scores[identifier]), "n": record["n"],
                   "p": record["p"], "input_sha256": record["input_sha256"],
                   "source_id": provenance["source_id"],
                   "parent_source_sha256": provenance["source_sha256"],
                   "source_topology_sha256": provenance["source_topology_sha256"],
                   "seed": provenance["seed"], "regime": provenance["regime"],
                   "entry_treatment": provenance["entry_treatment"],
                   "original_n": provenance["original_n"],
                   "original_root_count": provenance["original_root_count"]}
            row.update({f"{mode}_{method}_makespan": scores[identifier][mode][method]["makespan"]
                        for mode in MODES for method in METHODS})
            writer.writerow(row)


def build_profile(profile, frozen_name, evidence, selection, output, inputs, scores, hashes):
    frozen_ids_path = selection / (frozen_name + "_ids.json")
    frozen_analysis_path = selection / (frozen_name + "_analysis.json")
    chosen = json.loads(frozen_ids_path.read_text())
    receipt = json.loads(frozen_analysis_path.read_text())
    reference = receipt["selection"]
    require(chosen == sorted(set(chosen)), f"{profile}: IDs are not unique and sorted")
    require(len(chosen) == reference["count"], f"{profile}: unexpected count")
    require(set(chosen) <= set(inputs), f"{profile}: unknown input ID")
    require(id_set_hash(chosen) == reference["ids_sha256"], f"{profile}: frozen membership differs")
    require(hashes["full_pool_all_3072_results.csv"] == receipt["source_sha256"],
            f"{profile}: optimizer input source differs")
    require(len({inputs[i]["input_sha256"] for i in chosen}) == len(chosen),
            f"{profile}: duplicate input content")
    classes = Counter(classify(scores[i]) for i in chosen)
    require(classes == {"ectd_strict_both": reference["strict_wins_both"],
                        "ectd_loss_both": reference["losses_both"]},
            f"{profile}: winner/loss classification differs")
    families = {}
    for family in FAMILIES:
        identifiers = [i for i in chosen if inputs[i]["family"] == family]
        counts = Counter(classify(scores[i]) for i in identifiers)
        families[family] = {"wins": counts["ectd_strict_both"],
                            "losses": counts["ectd_loss_both"], "total": len(identifiers)}
        require(families[family] == reference["families"][family],
                f"{profile}: family composition differs")
        require(min(families[family]["wins"], families[family]["losses"]) >=
                receipt["constraints"]["family_min_each_group"],
                f"{profile}: family minimum violated")
    fraction = classes["ectd_strict_both"] / len(chosen)
    interval = receipt["constraints"]["winner_fraction_range"]
    if interval:
        require(interval[0] <= fraction <= interval[1], f"{profile}: winner fraction violated")
    else:
        require(classes["ectd_strict_both"] - 0.5 * len(chosen) >= 1,
                f"{profile}: majority constraint violated")
    selected = summarize(chosen, scores)
    observed_margins = {}
    required_margin = receipt["constraints"]["strict_margin_relative"]
    pairs = receipt["constraints"]["pairs"]
    expected_order = [pairs[0][0]] + [b for _, b in pairs]
    for mode in MODES:
        actual = selected["placements"][mode]
        require(actual["ranking_lowest_makespan_first"] == expected_order,
                f"{profile}: aggregate order differs")
        require(actual["win_tie_loss_vs_best"]["ECTD"] == {
            "strict_wins": reference["strict_wins_both"], "tied_best": 0,
            "beaten": reference["losses_both"]}, f"{profile}: ECTD W/T/L differs")
        geomeans = actual["geometric_makespans"]
        for method in METHODS:
            require(math.isclose(geomeans[method], reference["placements"][mode]["geomeans"][method],
                                 rel_tol=1e-12, abs_tol=1e-9),
                    f"{profile}: geometric mean differs from selection receipt")
        margins = {f"{a}<{b}": 100 * (1 - geomeans[a] / geomeans[b]) for a, b in pairs}
        require(all(value >= required_margin * 100 for value in margins.values()),
                f"{profile}: aggregate margin constraint violated")
        observed_margins[mode] = margins
    output.mkdir()
    exports = export_inputs(evidence / "candidates.jsonl.gz", output, {
        "inputs.jsonl.gz": set(chosen),
        "inputs_winners.jsonl.gz": {i for i in chosen if classify(scores[i]) == "ectd_strict_both"},
        "inputs_losses.jsonl.gz": {i for i in chosen if classify(scores[i]) == "ectd_loss_both"},
    })
    expected_path = output / "expected_results.jsonl.gz"
    with expected_path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6) as stream:
            for identifier in chosen:
                record = {"id": identifier, "family": inputs[identifier]["family"],
                          "input_sha256": inputs[identifier]["input_sha256"],
                          "placements": scores[identifier]}
                stream.write(json_bytes(record) + b"\n")
    write_membership(output / "membership.csv", chosen, inputs, scores)
    for name in ("expected_results.jsonl.gz", "membership.csv"):
        exports[name] = {"sha256": file_hash(output / name), "bytes": (output / name).stat().st_size}
    summary = {
        "schema_version": 1, "profile": profile, "frozen_selection_name": frozen_name,
        "execution_environment": "local", "ci": None,
        "interpretation": "Outcome-selected synthetic derived cohort; aggregate order was an explicit membership constraint.",
        "membership_ids_sha256": id_set_hash(chosen),
        "membership_source_sha256": file_hash(frozen_ids_path),
        "selection_receipt_sha256": file_hash(frozen_analysis_path),
        "source_files_sha256": hashes, "algorithms": list(METHODS), "placements": list(MODES),
        "constraints": receipt["constraints"], "solver": receipt["solver"],
        "winner_fraction": fraction, "families": families,
        "selected": selected, "adjacent_margins_percent": observed_margins,
        "exports": exports,
        "input_records_copied_byte_for_byte": True,
        "all_1467_original_winners_retained": False,
        "retained_original_winners": reference["strict_wins_both"],
        "omitted_original_winners": 1467 - reference["strict_wins_both"],
        "minimum_margin_is_population_evidence": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=PROJECT / "source_evidence")
    parser.add_argument("--selection", type=Path, default=PROJECT / "selection_evidence")
    parser.add_argument("--output", type=Path, default=PROJECT / "cohorts")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing to overwrite an existing cohort output directory")
    inputs, scores, hashes = load_evidence(args.evidence)
    pool_counts = dict(Counter(classify(scores[i]) for i in sorted(inputs)))
    require(pool_counts == {"ectd_strict_both": 1467, "ectd_loss_both": 1112, "other": 493},
            "full pool classifications changed")
    args.output.mkdir(parents=True)
    summaries = {}
    for profile, frozen_name in PROFILES.items():
        summary = build_profile(profile, frozen_name, args.evidence, args.selection,
                                args.output / profile, inputs, scores, hashes)
        summaries[profile] = {"instances": summary["selected"]["instances"],
                              "classifications": summary["selected"]["both_mode_classifications"],
                              "ids_sha256": summary["membership_ids_sha256"],
                              "summary_sha256": file_hash(args.output / profile / "summary.json")}
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "full_pool": summarize(sorted(inputs), scores), "pool_group_counts": pool_counts,
              "full_pool_input_hashes_checked": len(inputs),
              "retained_algorithm_mode_makespans_checked_against_csv": 3072 * 6 * 2,
              "source_files_sha256": hashes, "profiles": summaries,
              "build_source_sha256": file_hash(Path(__file__)),
              "execution_environment": "local", "ci": None}
    (args.output / "build_summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"source_inputs_checked": len(inputs), "profiles": summaries}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
