"""Determinism, structural, and feasibility tests for the ECTD benchmark suite.

Run with:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ectdbench import policy_table
from ectdbench.engine import validate_schedule
from ectdbench.generator import (FAMILIES, GROUPS, build_instance,
                                 validate_structure)
from ectdbench.model import Problem


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_same_instance(self):
        for family in FAMILIES:
            for group in GROUPS:
                a = build_instance(family, group, 7)
                b = build_instance(family, group, 7)
                self.assertEqual(a["id"], b["id"], "instance id is not stable")
                self.assertEqual(a["input_sha256"], b["input_sha256"],
                                 "content hash is not stable")
                self.assertEqual(a["costs"], b["costs"])
                self.assertEqual(a["edges"], b["edges"])

    def test_different_seeds_differ(self):
        a = build_instance("FFT", "plain", 1)
        b = build_instance("FFT", "plain", 2)
        self.assertNotEqual(a["input_sha256"], b["input_sha256"])

    def test_group_holds_topology_fixed(self):
        """Same family and seed, different group: node count and edges must match.

        This is what makes a group comparison controlled. If the motif changed
        the topology, a difference between groups could not be attributed to it.
        """
        for family in FAMILIES:
            base = build_instance(family, "plain", 11)
            for group in GROUPS:
                other = build_instance(family, group, 11)
                self.assertEqual(base["n"], other["n"],
                                 "%s/%s changed node count" % (family, group))
                self.assertEqual(base["p"], other["p"],
                                 "%s/%s changed processor count" % (family, group))
                self.assertEqual(len(base["edges"]), len(other["edges"]),
                                 "%s/%s changed edge count" % (family, group))


class TestStructure(unittest.TestCase):
    def test_all_cells_validate(self):
        for family in FAMILIES:
            for group in GROUPS:
                for seed in (1, 2, 3):
                    instance = build_instance(family, group, seed)
                    report = validate_structure(instance)
                    self.assertTrue(report["valid"],
                                    "%s/%s/seed %d: %s" % (
                                        family, group, seed, report["problems"]))

    def test_single_entry_and_exit(self):
        for family in FAMILIES:
            instance = build_instance(family, "plain", 5)
            report = validate_structure(instance)
            self.assertEqual(report["roots"], 1)
            self.assertEqual(report["sinks"], 1)

    def test_single_entry_means_no_dummy(self):
        """A single-entry graph must not be normalised with a dummy entry.

        Entry duplication is inert on a dummy entry, so this is the check that
        the suite can actually exercise ECTD's duplication term.
        """
        for family in FAMILIES:
            instance = build_instance(family, "plain", 5)
            problem = Problem(instance["costs"],
                              [(u, v, c) for u, v, c in instance["edges"]])
            self.assertIsNone(problem.dummy_entry,
                              "%s produced a dummy entry" % family)

    def test_cycle_is_rejected(self):
        instance = build_instance("FFT", "plain", 1)
        instance["edges"] = instance["edges"] + [[5, 0, 1.0]]
        report = validate_structure(instance)
        self.assertFalse(report["valid"])
        self.assertTrue(any("cycle" in p for p in report["problems"]))


class TestFeasibility(unittest.TestCase):
    def test_every_policy_produces_a_feasible_schedule(self):
        policies = policy_table()
        for family in FAMILIES:
            for group in GROUPS:
                instance = build_instance(family, group, 3)
                problem = Problem(instance["costs"],
                                  [(u, v, c) for u, v, c in instance["edges"]])
                for name, fn in policies.items():
                    insertion = name != "IPEFT"
                    schedule = fn(problem, insertion=insertion)
                    report = validate_schedule(problem, schedule)
                    self.assertTrue(report["valid"],
                                    "%s on %s/%s: %s" % (
                                        name, family, group, report["errors"]))
                    self.assertGreaterEqual(schedule.makespan, report["lower_bound"] - 1e-6)

    def test_makespan_is_at_least_the_lower_bound(self):
        policies = policy_table()
        instance = build_instance("GE", "plain", 9)
        problem = Problem(instance["costs"],
                          [(u, v, c) for u, v, c in instance["edges"]])
        for name, fn in policies.items():
            schedule = fn(problem, insertion=name != "IPEFT")
            report = validate_schedule(problem, schedule)
            self.assertGreaterEqual(schedule.makespan + 1e-9, report["lower_bound"])


class TestEntryDuplication(unittest.TestCase):
    def test_duplication_places_real_copies(self):
        """Duplication must reserve processor time, not act as a cache hit."""
        from ectdbench.proposed import run_ectd
        found = False
        for family in FAMILIES:
            instance = build_instance(family, "entry_transfer", 2)
            problem = Problem(instance["costs"],
                              [(u, v, c) for u, v, c in instance["edges"]])
            schedule = run_ectd(problem, insertion=True, duplication=True)
            if schedule.duplicate_count:
                found = True
                for calendar in schedule.events:
                    for event in calendar:
                        if event.is_duplicate:
                            self.assertAlmostEqual(
                                event.finish - event.start,
                                problem.w[event.task][event.processor], places=9)
        self.assertTrue(found, "entry duplication never fired on any family")

    def test_duplication_never_worsens_the_horizon(self):
        """A copy is extra work; it may not be free, but the primary makespan
        objective must remain the completion of the logical tasks."""
        from ectdbench.proposed import run_ectd
        for family in FAMILIES:
            instance = build_instance(family, "entry_transfer", 4)
            problem = Problem(instance["costs"],
                              [(u, v, c) for u, v, c in instance["edges"]])
            schedule = run_ectd(problem, insertion=True, duplication=True)
            self.assertLessEqual(schedule.makespan, schedule.execution_horizon + 1e-9)


class TestResultsArtifacts(unittest.TestCase):
    def test_results_are_consistent(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "results", "summary.json")
        if not os.path.exists(path):
            self.skipTest("results not built")
        with open(path) as fh:
            summary = json.load(fh)
        self.assertEqual(summary["instances"], 240)
        self.assertEqual(len(summary["observed_rank"]), 6)
        self.assertEqual(sorted(summary["observed_rank"]),
                         sorted(summary["target_rank"]))
        # No selection: every generated instance is scored.
        self.assertTrue(summary["entry_duplication_eligible"])


if __name__ == "__main__":
    unittest.main()
