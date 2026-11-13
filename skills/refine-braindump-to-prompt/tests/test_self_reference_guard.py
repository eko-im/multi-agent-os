#!/usr/bin/env python3
"""Deterministic tests for scripts/self_reference_guard.py. stdlib-only.
Run: python3 skills/refine-braindump-to-prompt/tests/test_self_reference_guard.py

Covers the correctness invariant of the guard:
  * the self-referential braindump (a copy of its own wrapping prompt) is detected and
    answered with a base-case prompt, not a loop;
  * the base-case prompt fed back is a fixed point (`clean`), so there is no recursion;
  * two neighbour inputs (a normal braindump, a braindump whose slot was filled) pass;
  * each guard line is mutation-checked: removing it makes the matching assertion fail.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "..", "scripts", "self_reference_guard.py")
FIX = os.path.join(HERE, "fixtures")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(*args, src=GUARD):
    p = subprocess.run([sys.executable, src, *args], capture_output=True, text=True)
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip() else None)


def load_mutant(marker):
    """Copy the guard with the line carrying `MUTATION-POINT:<marker>` neutralized."""
    src = _read(GUARD)
    lines = src.splitlines()
    hit = [i for i, l in enumerate(lines) if f"MUTATION-POINT:{marker}" in l]
    assert len(hit) == 1, f"mutation point {marker} must exist exactly once"
    i = hit[0]
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    lines[i] = f"{indent}if False:  # mutated {marker}"
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def tmp_input(case, text):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    case.addCleanup(os.remove, path)
    return path


class SelfReferenceGuard(unittest.TestCase):
    def test_self_reference_detected_with_base_case(self):
        code, out = run("--input", os.path.join(FIX, "self-reference.txt"))
        self.assertEqual(code, 3)
        self.assertEqual(out["verdict"], "self_reference")
        self.assertIn("envelope_copy", out["signals"])
        self.assertIn("self_pointer", out["signals"])
        self.assertIn("braindump", out["unfilled_slots"])
        bc = out["base_case_prompt"]
        self.assertTrue(out["meta_depth_rule"])
        self.assertIn("BASE CASE", bc)
        self.assertIn("STOP: after one pass", bc)
        self.assertNotIn("{{", bc)

    def test_base_case_is_fixed_point(self):
        _, out = run("--input", os.path.join(FIX, "self-reference.txt"))
        path = tmp_input(self, "Refine the braindump below.\n<braindump>\n" + out["base_case_prompt"] + "\n</braindump>\n")
        code, again = run("--input", path)
        self.assertEqual((code, again["verdict"]), (0, "clean"))

    def test_depth_bound_refuses_second_level(self):
        code, out = run("--input", os.path.join(FIX, "self-reference.txt"), "--depth", "1")
        self.assertEqual((code, out["verdict"]), (4, "recursion_limit"))

    def test_normal_braindump_is_clean(self):
        code, out = run("--input", os.path.join(FIX, "normal.txt"))
        self.assertEqual((code, out["verdict"], out["signals"]), (0, "clean", []))

    def test_filled_placeholder_is_clean(self):
        code, out = run("--input", os.path.join(FIX, "filled-placeholder.txt"))
        self.assertEqual((code, out["verdict"]), (0, "clean"))
        self.assertLess(out["similarity_to_envelope"], out["threshold"])

    def test_unfilled_slot_without_self_pointer(self):
        code, out = run("--input", tmp_input(self, "Refine this.\n<braindump>\nship {{feature}} by friday\n</braindump>\n"))
        self.assertEqual((code, out["verdict"], out["unfilled_slots"]), (3, "unfilled", ["feature"]))

    def test_empty_object(self):
        code, out = run("--input", tmp_input(self, "Refine this.\n<braindump>\n   \n</braindump>\n"))
        self.assertEqual((code, out["verdict"]), (3, "empty"))

    def test_partial_copy_inside_longer_envelope(self):
        steps = "1. Search similar artifacts inside and outside.\n2. Critique the dump against them and validate again.\n"
        framing = "You are a careful reviewer. Read every line twice. Keep a log of each decision you take.\n" * 4
        code, out = run("--input", tmp_input(self, framing + steps + "<braindump>\n" + steps + "</braindump>\n"))
        self.assertEqual(out["verdict"], "self_reference")
        self.assertIn("envelope_copy", out["signals"])

    def test_normal_dump_has_no_meta_rule(self):
        _, out = run("--input", os.path.join(FIX, "normal.txt"))
        self.assertFalse(out["meta_depth_rule"])

    # --- mutation checks: a guard that passes with and without its line proves nothing ---
    def test_mutation_envelope_copy_is_caught(self):
        mutant = load_mutant("envelope_copy")
        _, out = run("--input", os.path.join(FIX, "self-reference.txt"), src=mutant)
        self.assertNotIn("envelope_copy", out["signals"], "mutant must lose the signal")
        _, out = run("--input", os.path.join(FIX, "self-reference.txt"))
        self.assertIn("envelope_copy", out["signals"], "original must keep it")

    def test_mutation_self_pointer_is_caught(self):
        mutant = load_mutant("self_pointer")
        _, out = run("--input", os.path.join(FIX, "self-reference.txt"), src=mutant)
        self.assertNotIn("self_pointer", out["signals"])

    def test_mutation_both_lines_flips_verdict(self):
        """With both self-reference lines gone the quine degrades to `unfilled`:
        the base case vanishes, which is exactly the defect the guard exists to stop."""
        src = _read(GUARD)
        for m in ("self_pointer", "envelope_copy"):
            src = "\n".join(
                (l[: len(l) - len(l.lstrip())] + f"if False:  # mutated {m}") if f"MUTATION-POINT:{m}" in l else l
                for l in src.splitlines()
            )
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(src + "\n")
        _, out = run("--input", os.path.join(FIX, "self-reference.txt"), src=path)
        self.assertEqual(out["verdict"], "unfilled")
        self.assertNotIn("base_case_prompt", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
