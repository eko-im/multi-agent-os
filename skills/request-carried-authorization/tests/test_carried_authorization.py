#!/usr/bin/env python3
"""Tests for carried_authorization.py: dogfood fixtures plus mutation checks.

A mutation check flips ONE field of a case that yields A and asserts the verdict
changes. A guard that returns the same verdict with and without the defect proves nothing.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "carried_authorization.py"
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(SCRIPT.parent))

import carried_authorization as ca  # noqa: E402


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class DogfoodFixtures(unittest.TestCase):
    def test_every_fixture_matches_its_expected_verdict(self):
        files = sorted(FIXTURES.glob("*.json"))
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            case = json.loads(f.read_text(encoding="utf-8"))
            with self.subTest(fixture=f.name):
                got = ca.evaluate(case)
                self.assertEqual(got["verdict"], case["expect"], got["reasons"])
                if "expect_kind" in case:
                    self.assertEqual(got.get("kind"), case["expect_kind"], got["reasons"])

    def test_cli_exit_codes(self):
        for name, code in (("merge-the-pr", 0), ("grant-inside-agent-note", 30)):
            with self.subTest(fixture=name):
                p = subprocess.run(
                    [sys.executable, str(SCRIPT), str(FIXTURES / f"{name}.json")],
                    capture_output=True, text=True,
                )
                self.assertEqual(p.returncode, code, p.stdout + p.stderr)

    def test_cli_bad_input_exits_2(self):
        p = subprocess.run([sys.executable, str(SCRIPT)], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)


class MutationChecks(unittest.TestCase):
    """Start from the A case; each single defect must move the verdict off A."""

    def setUp(self):
        self.base = load("merge-the-pr")
        self.assertEqual(ca.evaluate(self.base)["verdict"], "A")

    def mutate(self, fn):
        case = copy.deepcopy(self.base)
        fn(case)
        return ca.evaluate(case)

    def assert_off_a(self, fn, verdict="C", kind=None):
        got = self.mutate(fn)
        self.assertEqual(got["verdict"], verdict, got["reasons"])
        if kind:
            self.assertEqual(got.get("kind"), kind, got["reasons"])

    def test_each_hard_flag_blocks(self):
        for flag in ca.HARD_FLAGS:
            with self.subTest(flag=flag):
                self.assert_off_a(lambda c, f=flag: c["action"]["flags"].__setitem__(f, True),
                                  kind="hard")

    def test_missing_hard_flag_fails_closed(self):
        self.assert_off_a(lambda c: c["action"]["flags"].pop("spend"), kind="hard")

    def test_every_data_origin_blocks(self):
        for origin in sorted(ca.DATA_ORIGINS):
            with self.subTest(origin=origin):
                self.assert_off_a(lambda c, o=origin: c["request"].__setitem__("origin", o),
                                  kind="hard")

    def test_conductor_decision_needs_authority_origin(self):
        self.assert_off_a(lambda c: c["request"].__setitem__("origin", "conductor_decision"),
                          kind="hard")
        got = self.mutate(lambda c: c["request"].update(
            origin="conductor_decision", authority_origin="operator turn, session X"))
        self.assertEqual(got["verdict"], "A", got["reasons"])

    def test_operator_refusal_blocks(self):
        self.assert_off_a(lambda c: c["request"].__setitem__("operator_said_no", True), kind="hard")

    def test_each_unanswered_mind_blocks(self):
        for mind in ca.MINDS:
            with self.subTest(mind=mind):
                self.assert_off_a(lambda c, m=mind: c["minds"].__setitem__(m, "  "), kind="ladder")

    def test_suspicious_doubt_blocks(self):
        self.assert_off_a(lambda c: c.__setitem__("suspicious_doubt", True), kind="hard")

    def test_no_via_blocks(self):
        self.assert_off_a(lambda c: c["action"].__setitem__("via", "none"), kind="ladder")

    def test_scope_extension_blocks(self):
        self.assert_off_a(lambda c: c["action"].__setitem__("consequence_matches_request", False),
                          kind="ladder")

    def test_implicit_needs_necessary_and_proportional(self):
        for field in ("necessary", "proportional"):
            with self.subTest(field=field):
                self.assert_off_a(lambda c, f=field: c["action"].update(via="implicit", **{f: False}),
                                  kind="ladder")

    def test_costly_second_reading_blocks(self):
        self.assert_off_a(lambda c: c["action"].__setitem__("readings", "multiple_diff_cost"),
                          kind="ladder")

    def test_evidence_against_request_blocks(self):
        self.assert_off_a(lambda c: c["action"].__setitem__("evidence_against_request", True),
                          kind="ladder")

    def test_non_trivial_effect_needs_verified_undo(self):
        self.assert_off_a(lambda c: c["action"].__setitem__("effect", "significant"), kind="ladder")
        self.assert_off_a(lambda c: c["action"].update(effect="significant", undo="git revert <sha>",
                                                       undo_verified=False), kind="ladder")
        got = self.mutate(lambda c: c["action"].update(effect="significant", undo="git revert <sha>",
                                                       undo_verified=True))
        self.assertEqual(got["verdict"], "B", got["reasons"])

    def test_c_always_carries_escalation_card(self):
        got = self.mutate(lambda c: c["action"].__setitem__("via", "none"))
        card = got["escalation_card"]
        for key in ("what_it_is", "what_it_is_for", "impact_if_yes", "impact_if_no", "recommendation"):
            self.assertIn(key, card)


if __name__ == "__main__":
    unittest.main(verbosity=2)
