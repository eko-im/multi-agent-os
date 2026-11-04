"""Tests for the HITL ledger PROVENANCE signal of synopsis-panel.

The defect these cover, measured on 2026-10-26: `find_hitl_md()` resolves the
WORKING-TREE copy of `hitl/punch-list.md`. A vault 21 commits behind its upstream,
with a dirty ledger, rendered 16 open items — the SAME count as the tracked copy,
with three already-closed items shown and three real ones hidden. The matching
count is what hid the error, and nothing in the output named the file that was read.

Contract under test (the minimum that stops an agent measuring the wrong file
WITHOUT KNOWING, while never breaking a human who is editing the ledger on purpose):

  1. a divergent working ledger (dirty, or repo behind upstream) PRODUCES a warning;
  2. a clean, up-to-date ledger produces NO warning at all;
  3. every render NAMES the file that was read, warning or not;
  4. the engine stays READ-ONLY and never substitutes a different file.

The git fixtures build real repositories in tmp_path — no mocks — because the
signal being tested IS the git state.
"""

import json
import os
import subprocess
import sys

import pytest

LEDGER = """---
id: hitl-punch-list
next_id: 3
---

# HITL punch-list

<!-- hitl:open:start -->
| ID | Sev | Tipo | R | Decidir | Pediu | Aberto | Idade | Prazo | Status | Link |
|----|-----|------|---|---------|-------|--------|-------|-------|--------|------|
| H-0001 | 🔴 URGENTE | 🔑 credencial | R3 | Primeiro item | agente | 2026-10-20 | 6 d | - | pendente | (sem ticket) |
<!-- hitl:open:end -->
"""

LEDGER_EDITED = LEDGER.replace("Primeiro item", "Primeiro item, editado no working tree")


def _git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True, check=check)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "test")
    _git(path, "config", "commit.gpgsign", "false")
    return path


@pytest.fixture
def clean_repo(tmp_path):
    """An origin + a clone whose ledger is tracked, clean and up to date."""
    origin = _init_repo(tmp_path / "origin")
    hitl = origin / "hitl"
    hitl.mkdir()
    (hitl / "punch-list.md").write_text(LEDGER, encoding="utf-8")
    _git(origin, "add", "hitl/punch-list.md")
    _git(origin, "commit", "-qm", "ledger")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    return clone


@pytest.fixture
def dirty_repo(clean_repo):
    """Same clone, but the working-tree ledger is modified relative to HEAD."""
    (clean_repo / "hitl" / "punch-list.md").write_text(LEDGER_EDITED, encoding="utf-8")
    return clean_repo


@pytest.fixture
def behind_repo(clean_repo):
    """Same clone, left N commits behind its upstream (ledger itself untouched)."""
    origin = clean_repo.parent / "origin"
    (origin / "hitl" / "punch-list.md").write_text(
        LEDGER.replace("next_id: 3", "next_id: 4"), encoding="utf-8")
    _git(origin, "commit", "-qam", "ledger moves on")
    _git(clean_repo, "fetch", "-q", "origin")
    return clean_repo


# ── 1 + 2: the warning fires on divergence and is SILENT when clean ───────────────
def test_clean_ledger_produces_no_warning(synopsis_fuse, clean_repo):
    prov = synopsis_fuse.ledger_provenance(clean_repo / "hitl" / "punch-list.md")
    assert prov["in_git"] is True
    assert prov["dirty"] is False
    assert prov["behind"] == 0
    assert prov["warning"] is None, (
        "a clean, up-to-date ledger must not warn — warning on the legitimate case "
        "is worse than the defect, because the signal stops meaning anything")


def test_dirty_ledger_warns(synopsis_fuse, dirty_repo):
    prov = synopsis_fuse.ledger_provenance(dirty_repo / "hitl" / "punch-list.md")
    assert prov["dirty"] is True
    assert prov["warning"], "a working-tree ledger modified against HEAD must warn"
    assert "MODIFIED" in prov["warning"]


def test_repo_behind_upstream_warns(synopsis_fuse, behind_repo):
    prov = synopsis_fuse.ledger_provenance(behind_repo / "hitl" / "punch-list.md")
    assert prov["dirty"] is False, "the file itself is untouched in this fixture"
    assert prov["behind"] == 1
    assert prov["warning"], (
        "being behind upstream is the exact shape of the measured defect: a clean "
        "file that is nonetheless not the current ledger")
    assert "BEHIND" in prov["warning"]


def test_ledger_outside_git_reports_path_without_warning(synopsis_fuse, tmp_path):
    p = tmp_path / "loose-punch-list.md"
    p.write_text(LEDGER, encoding="utf-8")
    prov = synopsis_fuse.ledger_provenance(p)
    assert prov["path"] == str(p)
    assert prov["in_git"] is False
    assert prov["warning"] is None


def test_missing_ledger_is_named_as_missing(synopsis_fuse):
    prov = synopsis_fuse.ledger_provenance(None)
    assert prov["path"] is None
    assert "not found" in prov["warning"]


# ── 3: every render NAMES the file, warning or not ────────────────────────────────
def _run(script_path, ledger, fmt="tree"):
    # `--scope all` because THIS file measures the ledger PROVENANCE, not the
    # session scope: the fixture ledger has no session provenance, so the
    # default (this conversation's items) would show nothing and the
    # provenance facts would be unreadable. The scope contract has its own
    # module: skills/synopsis-panel/tests/test_hitl_session_scope.py.
    proc = subprocess.run(
        [sys.executable, str(script_path), "--hitl-only", "--compass-json", "-",
         "--hitl-md", str(ledger), "--scope", "all", "--format", fmt],
        input="{}", capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.parametrize("fmt", ["tree", "mermaid", "html"])
def test_render_names_the_ledger_it_read(script_path, clean_repo, fmt):
    ledger = clean_repo / "hitl" / "punch-list.md"
    out = _run(script_path, ledger, fmt)
    assert str(ledger) in out, f"{fmt} render must say which ledger file it read"


def test_json_envelope_carries_provenance(script_path, dirty_repo):
    ledger = dirty_repo / "hitl" / "punch-list.md"
    env = json.loads(_run(script_path, ledger, "json"))
    meta = env["meta"]
    assert meta["hitl_source"] == str(ledger)
    assert meta["hitl_source_dirty"] is True
    assert meta["hitl_warning"] and "MODIFIED" in meta["hitl_warning"]


def test_tree_render_shows_the_warning(script_path, dirty_repo):
    out = _run(script_path, dirty_repo / "hitl" / "punch-list.md", "tree")
    assert "\u26a0" in out and "MODIFIED" in out


def test_clean_render_shows_no_warning_glyph(script_path, clean_repo):
    out = _run(script_path, clean_repo / "hitl" / "punch-list.md", "tree")
    assert "\u26a0" not in out
    assert "BEHIND" not in out and "MODIFIED" not in out


# ── 4: still READ-ONLY and still the file the caller asked for ────────────────────
def test_engine_does_not_mutate_the_repo_or_swap_the_file(script_path, dirty_repo):
    ledger = dirty_repo / "hitl" / "punch-list.md"
    before = ledger.read_text(encoding="utf-8")
    status_before = _git(dirty_repo, "status", "--porcelain").stdout
    env = json.loads(_run(script_path, ledger, "json"))
    assert ledger.read_text(encoding="utf-8") == before
    assert _git(dirty_repo, "status", "--porcelain").stdout == status_before
    # the working-tree edit is what was PARSED — the engine warned, it did not substitute
    decidir = env["tree"]["hitl_unattached"][0]["decidir"]
    assert "editado no working tree" in decidir, (
        "a human editing the ledger on purpose must still see their own edits")


# Execute the real consumer with an isolated HOME; never consult the user's queue.
def _binding_env(home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in {
        "HITL_LEDGER", "MAOS_SELF_SESSION_ID", "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_SESSION_ID", "PI_SESSION_FILE"}}
    env.update(HOME=str(home), MAOS_SELF_SESSION_ID="binding-session", **extra)
    return env


def _binding_ledger(home, relative, title):
    path = home / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (LEDGER.replace("Primeiro item", title)
            .replace("| Link |", "| Link | Sessão |")
            .replace("| (sem ticket) |", "| (sem ticket) | binding-session |"))
    path.write_text(body, encoding="utf-8")
    return path


def _binding_run(script_path, env, *extra, fmt="json", digest=True):
    cmd = [sys.executable, "-I", "-B", str(script_path), "--compass-json", "-",
           "--format", fmt, *extra]
    if digest:
        cmd.append("--hitl-only")
    proc = subprocess.run(cmd, input="{}", capture_output=True, text=True,
                          env=env, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if fmt in {"json", "ask-user-question"} else proc.stdout


def test_default_reads_active_vault_not_legacy(script_path, tmp_path):
    active = _binding_ledger(tmp_path, "Projects/eko-engram/hitl/punch-list.md", "Active")
    _binding_ledger(tmp_path, "eko-engram/hitl/punch-list.md", "Legacy")
    result = _binding_run(script_path, _binding_env(tmp_path))
    assert result["meta"]["hitl_source"] == str(active)
    assert result["meta"]["hitl_source_available"] is True
    assert result["meta"]["hitl_session_ids"] == ["binding-session"]
    assert result["tree"]["hitl_unattached"][0]["decidir"] == "Active"


@pytest.mark.parametrize("explicit", [False, True])
def test_ledger_override_precedence(script_path, tmp_path, explicit):
    _binding_ledger(tmp_path, "Projects/eko-engram/hitl/punch-list.md", "Default")
    env_ledger = _binding_ledger(tmp_path, "env.md", "Environment")
    cli_ledger = _binding_ledger(tmp_path, "cli.md", "CLI")
    extra = ["--hitl-md", str(cli_ledger)] if explicit else []
    result = _binding_run(script_path, _binding_env(tmp_path, HITL_LEDGER=str(env_ledger)), *extra)
    assert result["meta"]["hitl_source"] == str(cli_ledger if explicit else env_ledger)
    assert result["tree"]["hitl_unattached"][0]["decidir"] == ("CLI" if explicit else "Environment")


@pytest.mark.parametrize("override", [False, True])
def test_command_invocation_uses_active_binding(script_path, tmp_path, override):
    root = script_path.parents[3]
    active = _binding_ledger(tmp_path, "Projects/eko-engram/hitl/punch-list.md", "Active")
    _binding_ledger(tmp_path, "eko-engram/hitl/punch-list.md", "Legacy")
    other = _binding_ledger(tmp_path, "override.md", "Override")
    env = _binding_env(tmp_path, CLAUDE_PLUGIN_ROOT=str(root))
    if override:
        env["HITL_LEDGER"] = str(other)
    # The markdown command is an instruction surface, not an executable file:
    # execute its default invocation, stopping before the alternative examples.
    command = (root / "commands" / "hitl-digest.md").read_text(encoding="utf-8")
    invocation = command.split("```bash\n", 1)[1].split("\n```", 1)[0].split("# MESMO digest", 1)[0]
    proc = subprocess.run(["bash", "-c", invocation], capture_output=True, text=True,
                          env=env, cwd=tmp_path, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert str(other if override else active) in proc.stdout
    assert ("Override" if override else "Active") in proc.stdout
    assert "Legacy" not in proc.stdout


@pytest.mark.parametrize("fmt", ["tree", "mermaid", "html", "json", "ask-user-question"])
@pytest.mark.parametrize("digest", [False, True])
def test_missing_default_is_unavailable_not_empty(script_path, tmp_path, fmt, digest):
    # A legacy/other queue exists but must never be silently substituted.
    _binding_ledger(tmp_path, "eko-engram/hitl/punch-list.md", "Legacy")
    _binding_ledger(tmp_path, "Projects/backup/hitl/punch-list.md", "Backup")
    result = _binding_run(script_path, _binding_env(tmp_path), fmt=fmt, digest=digest)
    if isinstance(result, dict):
        meta = result.get("meta", result)
        assert meta["hitl_source_available"] is False
        assert meta["hitl_ledger_total"] is None
        assert meta["hitl_source"] == str(tmp_path / "Projects/eko-engram/hitl/punch-list.md")
        assert "NOT an empty queue" in meta["hitl_warning"]
        if fmt == "ask-user-question":
            assert result["no_decisions"] is False
            assert result["ask_user_question"] is None
            assert "nenhuma decisão pendente" not in "\n".join(result["preamble"])
    else:
        assert "NOT an empty queue" in result
    assert "Legacy" not in json.dumps(result) and "Backup" not in json.dumps(result)


def test_missing_explicit_source_does_not_fall_back(script_path, tmp_path):
    _binding_ledger(tmp_path, "Projects/eko-engram/hitl/punch-list.md", "Active")
    missing = tmp_path / "missing.md"
    result = _binding_run(script_path, _binding_env(tmp_path), "--hitl-md", str(missing),
                          fmt="ask-user-question")
    assert result["hitl_source"] == str(missing)
    assert result["hitl_source_available"] is False
    assert result["no_decisions"] is False


@pytest.mark.parametrize("kind", ["md", "json", "json-stdin"])
def test_available_empty_sources_remain_valid(script_path, tmp_path, kind):
    source = tmp_path / "empty"
    source.write_text("", encoding="utf-8")
    args = ["--hitl-json", "-"] if kind == "json-stdin" else [
        "--hitl-md" if kind == "md" else "--hitl-json", str(source)]
    # A stdin HITL source cannot share stdin with the compass.
    compass = tmp_path / "compass.json"
    compass.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-I", "-B", str(script_path), "--hitl-only",
         "--compass-json", str(compass), "--format", "ask-user-question", *args],
        input="", capture_output=True, text=True, env=_binding_env(tmp_path), timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["hitl_source_available"] is True
    assert result["hitl_ledger_total"] == 0
    assert result["no_decisions"] is True
    assert result["hitl_warning"] is None
