#!/usr/bin/env python3
"""Render docs/optimizations/OPTIMIZATIONS.md from the registry and the artifacts.

The rule this enforces: no optimization is described in prose alone. Every entry
in ``registry.json`` carries a mechanism (why it should help, in algorithm
terms), a claim (the direction it is expected to move the result), and a
decision (what was concluded and why). This script reads the measured numbers
out of the artifact the entry names and renders them into the document, so the
prose cannot drift from the data the way a hand-written table does.

It also checks the claim. If an entry says "better" and the artifact says worse,
the script fails. That is the point: an optimization cannot be documented as an
improvement on the strength of its own argument.

Usage:
    python3 scripts/render_optimizations.py            # render, fail on mismatch
    python3 scripts/render_optimizations.py --check    # verify only, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(ROOT, "docs", "optimizations", "registry.json")
OUT = os.path.join(ROOT, "docs", "optimizations", "OPTIMIZATIONS.md")

STATUS_LABEL = {
    "accepted": "ACCEPTED",
    "rejected": "REJECTED",
    "inconclusive": "INCONCLUSIVE",
    "proposed": "PROPOSED",
}
STATUS_ORDER = ["accepted", "inconclusive", "proposed", "rejected"]


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def pooled_of(summary, key):
    """Pooled geomean makespan for a policy key, or None if absent."""
    return (summary.get("pooled_geomean_makespan") or {}).get(key)


def pct_delta(value, reference):
    if value is None or not reference:
        return None
    return 100.0 * (value - reference) / reference


def check_equivalence(entry, root):
    """Verify a refactor entry against its committed equivalence report.

    A refactor has no policy key and no makespan, so it cannot be checked
    against the benchmark artifact the way an algorithm change is. Its evidence
    is a report committed to the tree, produced by scripts/check_equivalence.py.
    Requiring the report to exist and to record EQUIVALENT is the whole point:
    without it, a refactor entry is an assertion with nothing behind it, and the
    gate would pass it vacuously.

    Returns (ok, detail).
    """
    block = entry.get("equivalence") or {}
    report_path = block.get("report")
    if not report_path:
        return False, "refactor entry has no equivalence.report"

    full = os.path.join(root, report_path)
    if not os.path.exists(full):
        return False, "equivalence report not committed: %s" % report_path

    try:
        report = load_json(full)
    except Exception as exc:
        return False, "equivalence report unreadable: %s" % exc

    verdict = report.get("verdict")
    if verdict != "EQUIVALENT":
        return False, "report verdict is %r, not EQUIVALENT" % verdict

    # A report that claims EQUIVALENT while carrying failures is contradictory.
    rank_failures = (report.get("rank_equality") or {}).get("failures") or []
    schedule_diffs = (report.get("schedule_equality") or {}).get("differences") or []
    invalid = report.get("invalid_schedules") or []
    if rank_failures or schedule_diffs or invalid:
        return False, ("report says EQUIVALENT but records %d rank failures, "
                       "%d schedule differences, %d invalid schedules"
                       % (len(rank_failures), len(schedule_diffs), len(invalid)))

    compared = (report.get("schedule_equality") or {}).get("compared")
    checked = (report.get("rank_equality") or {}).get("checked")
    if not compared or not checked:
        return False, "report records no comparisons"

    return True, "%s: %d rank cases, %d instances, EQUIVALENT" % (
        report_path, checked, compared)


def check_validation(entry, root):
    """Verify a validation entry against its committed held-out report.

    A validation entry makes no claim about makespan, so there is nothing in the
    benchmark artifact to check it against. What it claims is that a parameter
    choice survives instances the choice was not made on, and the evidence for
    that is a report committed to the tree, produced by
    ``scripts/held_out_validation.py``.

    The gate requires three things, and each of them closes a way the entry
    could otherwise pass while being worthless:

    - the report exists, so the claim is not prose alone;
    - it ran enough trials to say something about stability, since a single
      split is a single sample and would pass on luck;
    - the parameter actually selected on the training half is the one the entry
      names, because a validation entry that validates a different policy than
      the one shipped is a non-sequitur.

    Returns (ok, detail).
    """
    block = entry.get("validation") or {}
    report_path = block.get("report")
    if not report_path:
        return False, "validation entry has no validation.report"

    full = os.path.join(root, report_path)
    if not os.path.exists(full):
        return False, "held-out report not committed: %s" % report_path

    try:
        report = load_json(full)
    except Exception as exc:
        return False, "held-out report unreadable: %s" % exc

    trials = int(report.get("trials") or 0)
    minimum = int(block.get("min_trials") or 20)
    if trials < minimum:
        return False, "report ran %d trials, entry requires %d" % (trials, minimum)

    expected = block.get("policy_key")
    if not expected:
        return False, "validation entry has no validation.policy_key"

    counts = report.get("selection_counts") or {}
    if not counts:
        return False, "report records no selections"
    selected = max(counts, key=lambda k: counts[k])
    if selected != expected:
        return False, ("training half selected %r, entry names %r"
                       % (selected, expected))

    regret = (report.get("regret_pct") or {}).get("max")
    if regret is None:
        return False, "report records no regret"

    return True, "%s: %d trials, selected %s in %d/%d, max regret %.3f%%" % (
        report_path, trials, selected, counts[selected], trials, regret)


def check_claim(entry, summary, baseline_key, reference_key, root):
    """Verify the entry's recorded OUTCOME against the artifact.

    The gate is the outcome, not the claim. A rejected entry is precisely one
    whose prediction failed, so gating on the prediction would make a rejection
    impossible to record. What must be true is that the outcome written down is
    the outcome the artifact shows; the prediction is reported separately as
    whether it held.

    Returns (ok, detail, prediction_held).
    """
    kind = entry.get("kind", "algorithm")
    if kind == "refactor":
        ok, detail = check_equivalence(entry, root)
        return ok, detail, None
    if kind == "validation":
        ok, detail = check_validation(entry, root)
        return ok, detail, None
    if kind != "algorithm":
        return False, "unknown entry kind %r" % kind, None

    claim = entry.get("outcome") or {}
    code = entry.get("code") or {}
    key = code.get("policy_key")
    # An algorithm entry without a policy key has no measurement behind it. This
    # used to return ok=True, which let an unmeasured entry clear the gate.
    if not key:
        return False, "algorithm entry has no code.policy_key", None

    mine = pooled_of(summary, key)
    if mine is None:
        return False, "policy %r is not in the artifact" % key, None

    # `vs` names either "baseline", "reference", or an explicit policy key such
    # as "v:own_cost". Resolving anything unknown to the reference would compare
    # against the wrong policy and pass an outcome that is actually false, so an
    # unrecognised name is an error rather than a fallback.
    vs = claim.get("vs", "baseline")
    if vs == "baseline":
        ref_key = baseline_key
    elif vs == "reference":
        ref_key = reference_key
    else:
        ref_key = vs
    ref = pooled_of(summary, ref_key)
    if ref is None:
        return False, "reference policy %r is not in the artifact" % ref_key, None

    delta = pct_delta(mine, ref)
    direction = claim.get("direction")
    min_pct = float(claim.get("min_pct", 0.0) or 0.0)
    tol = float(claim.get("tolerance_pct", 0.005) or 0.005)

    # Negative delta means faster, which is better.
    if direction == "equal":
        ok = abs(delta) <= tol
        detail = "%+.3f%% vs %s (recorded equal within %.3f%%)" % (delta, ref_key, tol)
    elif direction == "better":
        ok = delta <= -min_pct
        detail = "%+.3f%% vs %s (recorded better by >= %.2f%%)" % (delta, ref_key, min_pct)
    elif direction == "worse":
        ok = delta >= min_pct
        detail = "%+.3f%% vs %s (recorded worse by >= %.2f%%)" % (delta, ref_key, min_pct)
    else:
        return True, "%+.3f%% vs %s (no recorded direction)" % (delta, ref_key), None

    # Did the prediction hold? Reported, never gated.
    predicted = (entry.get("claim") or {}).get("direction")
    held = None if predicted is None else (predicted == direction)
    return ok, detail, held


def fmt_pct(delta):
    if delta is None:
        return "n/a"
    return "%+.2f%%" % delta


def fmt_num(value):
    if value is None:
        return "n/a"
    return "%.2f" % value


def emit_paragraphs(add, items):
    """Join the registry's line list into paragraphs.

    The registry stores prose as a list of lines where an empty string is a
    paragraph break. Emitting each line separately would break sentences across
    blank lines, so consecutive non-empty lines are joined with a space.
    """
    buf = []
    for line in items:
        if line.strip() == "":
            if buf:
                add(" ".join(buf))
                add("")
                buf = []
        else:
            buf.append(line.strip())
    if buf:
        add(" ".join(buf))
        add("")


def render(registry, summary):
    baseline_key = registry["baseline"]["policy_key"]
    reference_key = registry["reference"]["policy_key"]
    base_val = pooled_of(summary, baseline_key)
    ref_val = pooled_of(summary, reference_key)

    entries = registry["entries"]
    by_status = {}
    for e in entries:
        by_status.setdefault(e.get("status", "proposed"), []).append(e)

    lines = []
    add = lines.append

    add("# Optimization log")
    add("")
    add("Every change to a scheduling policy, with the reason it should work, the")
    add("measurement that decides it, and the decision. Generated by")
    add("`scripts/render_optimizations.py` from `registry.json` and the benchmark")
    add("artifact; do not edit by hand.")
    add("")
    add("The rule this document exists to enforce: **a change is not an optimization")
    add("until it has a mechanism and a measurement, and the measurement agrees with")
    add("the mechanism.** An entry whose claim the artifact contradicts fails the")
    add("build rather than being quietly softened in the prose.")
    add("")

    add("## Provenance")
    add("")
    add("| | |")
    add("|---|---|")
    add("| Artifact | `docs/benchmark/summary.json` |")
    add("| Instances scored | %s |" % summary.get("instances_scored", "n/a"))
    add("| Instances failed | %s |" % summary.get("instances_failed", "n/a"))
    add("| Baseline | `%s` = %s |" % (baseline_key, fmt_num(base_val)))
    add("| Strongest published baseline | `%s` = %s |" % (reference_key, fmt_num(ref_val)))
    add("")

    add("## Summary")
    add("")
    add("| Change | Kind | Status | vs `%s` | vs `%s` |" % (baseline_key, reference_key))
    add("|---|---|---|---:|---:|")
    for status in STATUS_ORDER:
        for e in by_status.get(status, []):
            key = (e.get("code") or {}).get("policy_key")
            val = pooled_of(summary, key) if key else None
            kind = e.get("kind", "algorithm")
            add("| %s | %s | %s | %s | %s |" % (
                e["title"],
                kind,
                STATUS_LABEL.get(status, status.upper()),
                fmt_pct(pct_delta(val, base_val)),
                fmt_pct(pct_delta(val, ref_val)),
            ))
    add("")
    add("A refactor row has no makespan by design: it is required to change no")
    add("schedule at all, so its evidence is an equivalence report rather than a")
    add("delta. See the entry for the committed report.")
    add("")

    add("## The scoring rule these changes act on")
    add("")
    add("`_place_scored` picks a processor by minimising")
    add("")
    add("```")
    add("score = start + self_weight * w[task][q] + tail[task][q]")
    add("```")
    add("")
    add("because it computes `eft = start + w[task][q]` and then adds the tail on")
    add("top. `self_weight = 1` is stock ECTD. Every scoring change below is a")
    add("statement about `self_weight` or about `tail`, which is why they are")
    add("comparable rather than being unrelated tweaks.")
    add("")

    for status in STATUS_ORDER:
        group = by_status.get(status, [])
        if not group:
            continue
        add("## %s" % {
            "accepted": "Accepted",
            "rejected": "Rejected",
            "inconclusive": "Inconclusive",
            "proposed": "Proposed, not yet measured",
        }[status])
        add("")
        for e in group:
            key = (e.get("code") or {}).get("policy_key")
            val = pooled_of(summary, key) if key else None
            kind = e.get("kind", "algorithm")
            add("### `%s` — %s" % (e["id"], e["title"]))
            add("")
            add("**Status:** %s  " % STATUS_LABEL.get(status, status.upper()))
            add("**Kind:** %s" % kind)
            if key:
                add("")
                add("**Measured:** `%s` = %s pooled, %s vs `%s`, %s vs `%s`" % (
                    key, fmt_num(val),
                    fmt_pct(pct_delta(val, base_val)), baseline_key,
                    fmt_pct(pct_delta(val, ref_val)), reference_key))
            if kind == "refactor":
                block = e.get("equivalence") or {}
                add("")
                add("**Equivalence:** `%s`" % block.get("report", "(none)"))
                if block.get("scope"):
                    add("")
                    add("Scope: %s" % block["scope"])
            if kind == "validation":
                block = e.get("validation") or {}
                add("")
                add("**Held-out report:** `%s`" % block.get("report", "(none)"))
                if block.get("scope"):
                    add("")
                    add("Scope: %s" % block["scope"])
            add("")
            add("**Mechanism.** Why this should move the result, in algorithm terms.")
            add("")
            emit_paragraphs(add, e.get("mechanism", []))
            claim = e.get("claim") or {}
            if claim.get("statement"):
                add("**Claim before measuring:** %s" % claim["statement"])
                add("")
            outcome = e.get("outcome") or {}
            if outcome.get("statement"):
                add("**Measured outcome:** %s" % outcome["statement"])
                add("")
            add("**Decision.**")
            add("")
            emit_paragraphs(add, e.get("decision", []))
            ev = e.get("evidence") or []
            if ev:
                add("**Evidence:** " + "; ".join("`%s`" % x for x in ev))
                add("")

    add("## How to add an entry")
    add("")
    add("An **algorithm** entry changes what the policy computes, so it is judged on")
    add("quality and needs a measured delta:")
    add("")
    add("1. Add the variant to `scripts/ectd_variants.py` (or a new module) and give")
    add("   it a `v:` prefixed name so it cannot be mistaken for a published policy.")
    add("2. Add an entry to `registry.json` with `status: \"proposed\"`, the mechanism,")
    add("   and the claim. A proposed entry cannot be merged.")
    add("3. Run the ablation workflow. It scores every variant on the real corpus.")
    add("4. Run `python3 scripts/render_optimizations.py`. If the artifact contradicts")
    add("   the claim, it fails. Fix the claim or the code, not the document.")
    add("5. Set the status to `accepted`, `rejected` or `inconclusive` and record the")
    add("   reasoning in `decision`. Rejected entries stay: they are the record of")
    add("   what has already been ruled out.")
    add("")
    add("A **refactor** entry changes how the policy is computed but not what it")
    add("computes, so it is judged on identity and needs no delta:")
    add("")
    add("1. Set `kind: \"refactor\"` and give an `equivalence` block naming a report")
    add("   committed to the tree, plus a `scope` line saying what the change does")
    add("   and does not buy. A refactor that claims a bound improvement it does not")
    add("   deliver is the failure mode this field exists to prevent.")
    add("2. Run the equivalence workflow. It writes `equivalence-report.json`.")
    add("3. Commit that report to the path the entry names. The gate requires the")
    add("   file to exist and to record `verdict: EQUIVALENT` with no failures.")
    add("")
    add("A **validation** entry makes no makespan claim, so it is judged on whether")
    add("a parameter choice survives data the choice was not made on:")
    add("")
    add("1. Set `kind: \"validation\"` and give a `validation` block naming a report")
    add("   committed to the tree, the policy the selection is expected to land on,")
    add("   and a `min_trials` floor, plus a `scope` line saying what the split does")
    add("   and does not establish.")
    add("2. Run `python3 scripts/held_out_validation.py --results <shard dir>`. It")
    add("   splits within every cell, re-selects on the training half, and repeats.")
    add("3. Commit that report to the path the entry names. The gate requires the")
    add("   file to exist, to have run at least `min_trials`, and to have selected")
    add("   the policy the entry names.")
    add("")
    add("The gate rejects an algorithm entry with no `code.policy_key`, a refactor")
    add("entry with no committed report, and a validation entry whose report does not")
    add("select the policy it names. None can pass on prose alone.")
    add("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify claims, write nothing")
    args = ap.parse_args()

    registry = load_json(REGISTRY)
    artifact = os.path.join(ROOT, registry["baseline"]["artifact"])
    if not os.path.exists(artifact):
        raise SystemExit("artifact not found: %s" % artifact)
    summary = load_json(artifact)

    baseline_key = registry["baseline"]["policy_key"]
    reference_key = registry["reference"]["policy_key"]

    failures = []
    surprises = []
    print("%-24s %-13s %-6s %-9s %s" % (
        "entry", "status", "gate", "predicted", "measured"))
    for e in registry["entries"]:
        ok, detail, held = check_claim(e, summary, baseline_key, reference_key, ROOT)
        mark = "ok" if ok else "FAIL"
        pred = {True: "held", False: "missed", None: "-"}[held]
        print("%-24s %-13s %-6s %-9s %s" % (
            e["id"], e.get("status", "?"), mark, pred, detail))
        if not ok:
            failures.append((e["id"], detail))
        if held is False:
            surprises.append((e["id"], (e.get("claim") or {}).get("direction"),
                              (e.get("outcome") or {}).get("direction")))

    if surprises:
        print("\n%d prediction(s) did not hold (recorded, not a failure):" % len(surprises))
        for eid, pred, got in surprises:
            print("  %s: predicted %s, measured %s" % (eid, pred, got))

    if failures:
        print("\n%d recorded outcome(s) contradicted by the artifact:" % len(failures))
        for eid, detail in failures:
            print("  %s: %s" % (eid, detail))
        print("\nThe document was not written. Fix the registry or the code.")
        return 1

    if args.check:
        print("\nall claims hold; --check so nothing written")
        return 0

    text = render(registry, summary)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(text)
    print("\nwrote %s (%d bytes)" % (OUT, len(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
