#!/usr/bin/env python3
"""Tests for lint_braindump.py. Run: python3 -m unittest test_lint_braindump.py

Each test pins one rule. The fixture META_DUMP is the real self-referential dump
that motivated v0.4.0 (names neutralised: the sinks are passed as arguments).
"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_braindump as lb  # noqa: E402

META_DUMP = (
    "Analise o {{braindump}}, busque semelhantes interno/externo, cruze, compare, "
    "critique, valide, meta-critique, valide, fix, solve, improve, enhance, expand, "
    "harmonize, sanitize, delegue para [anima, forge] salvar e criar um ou mais "
    "agentic-tools em [public-repo, private-vault] + git-cycle + diy-pr-review + "
    "house-cleaning + boy-scout. Nota: Nao execute o {{braindump}} pois ele e o "
    "objeto de sua manipulacao."
)


def run(text, **kw):
    return lb.lint(text, kw.get("bind", set()), kw.get("public", []),
                   kw.get("private", []), allow=kw.get("allow"))


class VerbCollapse(unittest.TestCase):
    def test_validate_twice_is_redundant(self):
        r = run(META_DUMP, bind={"braindump"})
        self.assertEqual(r["verbs"]["canonical"]["validate"]["count"], 2)
        self.assertIn("validate", r["verbs"]["redundant"])

    def test_five_correct_synonyms_collapse_to_one_phase(self):
        r = run(META_DUMP, bind={"braindump"})
        c = r["verbs"]["canonical"]["correct"]
        self.assertEqual(c["phase"], "REFINE.correct")
        self.assertEqual(set(c["surface"]), {"fix", "solve", "improve", "enhance", "expand"})

    def test_meta_critique_not_double_counted_as_critique(self):
        r = run("critique e meta-critique")
        self.assertEqual(r["verbs"]["canonical"]["critique"]["count"], 2)
        self.assertEqual(set(r["verbs"]["canonical"]["critique"]["surface"]), {"critique", "meta-critique"})

    def test_accents_folded(self):
        r = run("Análise e crítica")
        self.assertIn("critique", r["verbs"]["canonical"])

    def test_forge_inside_a_slug_is_not_a_verb(self):
        r = run("use agentic-tool-forge later")
        self.assertNotIn("delegate", r["verbs"]["canonical"])


class Placeholders(unittest.TestCase):
    def test_unbound_halts(self):
        r = run(META_DUMP)
        self.assertEqual(r["placeholders"]["unbound"], ["braindump"])
        self.assertIn("unbound-placeholder", r["halts"])
        self.assertEqual(r["status"], "halt")

    def test_bound_by_wrapper_passes(self):
        r = run(META_DUMP, bind={"braindump"})
        self.assertEqual(r["placeholders"]["unbound"], [])
        self.assertNotIn("unbound-placeholder", r["halts"])


class SelfReference(unittest.TestCase):
    def test_meta_dump_detected(self):
        r = run(META_DUMP, bind={"braindump"})
        self.assertTrue(r["self_reference"]["meta"])
        self.assertIn("meta-dump: apply meta-depth=1", r["warnings"])

    def test_names_self(self):
        r = run("run refine-braindump-to-prompt on this")
        self.assertIn("names-self", r["self_reference"]["reasons"])

    def test_ordinary_dump_not_meta(self):
        r = run("migrate the billing table, then compare row counts until they match")
        self.assertFalse(r["self_reference"]["meta"])


class StopRule(unittest.TestCase):
    def test_meta_dump_has_no_stop_rule(self):
        r = run(META_DUMP, bind={"braindump"})
        self.assertFalse(r["stop_rule_present"])
        self.assertIn("no-stop-rule", r["warnings"])

    def test_until_counts(self):
        self.assertTrue(run("loop until clean")["stop_rule_present"])

    def test_ordinary_ate_and_max_are_not_stop_rules(self):
        self.assertFalse(run("I ate lunch and maxed out")["stop_rule_present"])
        self.assertTrue(run("repita ate zero achado")["stop_rule_present"])


class Sanitize(unittest.TestCase):
    KEY = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file is not itself a finding

    def test_secret_with_public_sink_halts(self):
        r = run(f"push {self.KEY} to public-repo", public=["public-repo"])
        self.assertIn("secret-or-pii-with-public-sink", r["halts"])
        self.assertNotIn(self.KEY, json.dumps(r))  # value is masked, never echoed

    def test_secret_without_public_sink_warns(self):
        r = run(f"note {self.KEY}")
        self.assertEqual(r["status"], "ok")
        self.assertIn("secret-or-pii-present", r["warnings"])

    def test_email_is_pii(self):
        r = run("mail someone@example.org")
        self.assertEqual(r["secrets"][0]["kind"], "email")

    def test_allow_list(self):
        r = run("mail someone@example.org", allow={"someone@example.org"})
        self.assertEqual(r["secrets"], [])

    def test_allow_list_ignores_case(self):
        r = run("mail Someone@Example.org", allow={"someone@example.org"})
        self.assertEqual(r["secrets"], [])


class Sinks(unittest.TestCase):
    def test_world_split(self):
        r = run(META_DUMP, bind={"braindump"}, public=["public-repo"], private=["private-vault"])
        self.assertTrue(r["sinks"]["split_required"])
        self.assertEqual(r["sinks"]["mentioned_public"], ["public-repo"])

    def test_declared_public_sink_halts_even_when_not_named(self):
        r = run("note someone@example.org for the OSS repo", public=["public-repo"])
        self.assertIn("secret-or-pii-with-public-sink", r["halts"])
        self.assertEqual(r["sinks"]["mentioned_public"], [])

    def test_mention_uses_word_edges(self):
        r = run("see the repository", public=["repo"])
        self.assertEqual(r["sinks"]["mentioned_public"], [])


class Cli(unittest.TestCase):
    def _cli(self, argv, stdin=""):
        buf = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(buf):
            code = lb.main(argv)
        return code, json.loads(buf.getvalue())

    def test_exit_1_on_halt(self):
        code, out = self._cli(["-"], META_DUMP)
        self.assertEqual(code, 1)
        self.assertEqual(out["status"], "halt")

    def test_exit_0_when_bound(self):
        code, _ = self._cli(["-", "--bind", "braindump"], META_DUMP)
        self.assertEqual(code, 0)

    def test_empty_dump_halts(self):
        code, out = self._cli(["-"], "   ")
        self.assertEqual((code, out["halts"]), (1, ["empty-dump"]))

    def test_missing_file_is_usage_error(self):
        code, out = self._cli(["/nonexistent/dump.md"])
        self.assertEqual((code, out["status"]), (2, "usage-error"))

    def test_non_utf8_file_is_usage_error_not_halt(self):
        import tempfile
        with tempfile.NamedTemporaryFile("wb", suffix=".md", delete=False) as fh:
            fh.write(b"Braindump: caf\xe9")
        try:
            code, out = self._cli([fh.name])
        finally:
            os.unlink(fh.name)
        self.assertEqual((code, out["status"]), (2, "usage-error"))
        self.assertIn("UnicodeDecodeError", out["error"])

    def test_internal_error_emits_self_heal(self):
        with mock.patch.object(lb, "collapse_verbs", side_effect=RuntimeError("boom")):
            code, out = self._cli(["-"], "analyze this")
        self.assertEqual(code, 3)
        self.assertEqual(out["status"], "error")
        self.assertIn("harness_prompt", out["self_heal"])
        self.assertEqual(len(out["self_heal"]["input_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
