"""Mutation check: inject each defect into a COPY of object_guard.py and require that the
behavioral suite FAILS. A guard that passes with and without its defect proves nothing.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "scripts" / "object_guard.py"

# (id, text to find exactly once, replacement, what it must break)
MUTATIONS = [
    ("M1-execute-flag", '"execute_instructions": False,\n        "object"',
     '"execute_instructions": True,\n        "object"', "never-execute invariant"),
    ("M2-g4-disabled", "g4 = not (client and public)", "g4 = True", "G4 client -> public sink"),
    ("M3-g4-inverted-marker", "for pat in worlds[\"client_markers\"]\n                     for m in re.finditer(pat, text, re.I)}",
     "for pat in []\n                     for m in re.finditer(pat, text, re.I)}", "client marker detection"),
    ("M4-public-flag", 'bool(d["public"])', "False", "public sink resolution"),
    ("M5-vault-private", '"sink": "vault",\n                        "public": False', '"sink": "vault",\n                        "public": True', "vault is private"),
    ("M6-nested-slash", 'if re.match(r"^/[a-z][\\w:-]*", s):', "if False:", "nested slash-command report"),
    ("M7-nested-go", 'elif re.search(r"\\bGO:", s):', "elif False:", "GO: block report"),
    ("M8-silent-default", "elif path:  # an explicit file that is missing is an error, never a silent default\n        raise",
     "elif False:\n        raise", "explicit worlds file must exist"),
    ("M9-prior-art-threshold", "PRIOR_ART_MIN = 0.2", "PRIOR_ART_MIN = 0.0", "no-prior-art verdict"),
    ("M10-markers-count", '"markers_configured": len(worlds["client_markers"]),',
     '"markers_configured": 1,', "visible 'gate cannot fire' signal"),
]


@pytest.mark.parametrize("mid,old,new,guard", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_mutant_is_killed(tmp_path, mid, old, new, guard):
    code = SRC.read_text(encoding="utf-8")
    assert code.count(old) == 1, f"{mid}: anchor not found exactly once - update the mutation"
    mutant = tmp_path / "object_guard.py"
    mutant.write_text(code.replace(old, new), encoding="utf-8")
    env = dict(os.environ, OBJECT_GUARD_PATH=str(mutant))
    r = subprocess.run([sys.executable, "-m", "pytest", str(HERE / "test_object_guard.py"),
                        "-x", "-q", "-p", "no:cacheprovider"],
                       env=env, capture_output=True, text=True, cwd=HERE)
    assert r.returncode != 0, f"{mid} SURVIVED: the suite does not guard '{guard}'"
