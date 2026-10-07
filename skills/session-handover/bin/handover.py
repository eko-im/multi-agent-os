#!/usr/bin/env python3
"""handover.py — deterministic engine of the `session-handover` skill.

The agent does the judgment (what was asked, what is open, what to recommend) and writes it
into ONE typed ledger (JSON). This script does everything that must not depend on judgment:
the fail-closed delegate gate, ledger validation, harvest coverage, recovery verification,
rendering of the handover pack, todo sync, secret/PII-screened persistence, and a
byte-verified clipboard copy.

Stdlib only. Subcommands and exit codes:
  gate        0 all delegates delivered · 3 refused (pending/empty/missing manifest, fail-closed)
  validate    0 valid · 3 invalid
  recovery    0 verified · 3 refused
  render      0 rendered (dry-run unless --apply) · 3 refused (invalid ledger / unverified recovery / dangling link)
  sync-todo   0 in sync · 2 drift
  scan        0 clean (or --self-test passed) · 4 findings · 1 self-test failed
  persist     0 copied (dry-run unless --apply) · 4 findings without --redact · 1 self-test failed
  clip        0 round-trip verified · 5 mismatch · 6 no clipboard tool (fall back to a clipboard MCP)
Common: 1 = usage/internal error. Add --json for a machine envelope on stdout.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

STATUSES = {"done", "in_progress", "blocked", "pending", "dropped"}
OPEN_STATUSES = {"in_progress", "blocked", "pending"}
# Every kind the close-out must rescue. Each one is either present in `nodes` or listed in
# `declared_empty` — a kind that is neither is a silent drop and refuses validation.
HARVEST_KINDS = ["prompt", "instruction", "motivation", "dor", "dod", "goal", "target",
                 "task", "step", "bug", "gap", "warning", "failure", "error"]
QUADRANTS = ["Q1", "Q2", "Q3", "Q4"]
QUADRANT_LABEL = {"Q1": "urgent + important", "Q2": "important, not urgent",
                  "Q3": "urgent, not important", "Q4": "neither"}
PACK = ["HANDOFF_PROMPT.md", "GRAFO.md", "HITL_PENDENCIAS.md", "ROADMAP.md", "INDEX_ARTEFATOS.md"]


class Refused(Exception):
    """A gate refused. Carries the reasons; maps to exit 3 unless a code is given."""

    def __init__(self, reasons, code=3):
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.code = code


def emit(args, ok, code, **payload):
    if getattr(args, "json", False):
        print(json.dumps({"ok": ok, "cmd": args.cmd, "exit": code, **payload}, ensure_ascii=False, indent=1))
    else:
        for key, val in payload.items():
            if isinstance(val, list):
                for item in val:
                    print(f"{key}: {item}")
            elif val not in (None, ""):
                print(f"{key}: {val}")
    return code


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- FEAT-1 delegate gate
def check_delegates(manifest_path):
    """Return (pending_reasons, delivered_ids). Unreadable/empty manifest is a refusal."""
    try:
        data = load_json(manifest_path)
    except (OSError, ValueError) as exc:
        return [f"manifest unreadable: {exc}"], []
    delegates = data.get("delegates") if isinstance(data, dict) else None
    if not delegates:
        return ["manifest lists no delegates — nothing is proven delivered"], []
    reasons, delivered = [], []
    for d in delegates:
        did = d.get("id", "?")
        if d.get("state") != "delivered":
            reasons.append(f"{did}: state={d.get('state')!r}")
            continue
        rep = d.get("report")
        if not rep or not os.path.isfile(rep) or os.path.getsize(rep) == 0:
            reasons.append(f"{did}: report missing or empty ({rep})")
            continue
        delivered.append(did)
    return reasons, delivered


def cmd_gate(args):
    deadline = time.monotonic() + max(0, args.timeout)
    while True:
        reasons, delivered = check_delegates(args.manifest)
        if not reasons:
            return emit(args, True, 0, delivered=delivered)
        if time.monotonic() >= deadline:
            return emit(args, False, 3, refused=reasons, delivered=delivered,
                        hint="do not close out; wait, re-dispatch, or escalate the pending delegates")
        time.sleep(max(1, args.interval))


# ---------------------------------------------------------------- FEAT-2/3/4 validation
def validate_ledger(ledger):
    errors = []
    for key in ("session", "nodes", "hitl", "roadmap", "artifacts"):
        if key not in ledger:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors
    nodes = ledger["nodes"]
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    by_id = {n.get("id"): n for n in nodes}
    for n in nodes:
        if n.get("kind") not in HARVEST_KINDS:
            errors.append(f"{n.get('id')}: unknown kind {n.get('kind')!r}")
        if n.get("status") not in STATUSES:
            errors.append(f"{n.get('id')}: unknown status {n.get('status')!r}")
        if not n.get("title"):
            errors.append(f"{n.get('id')}: empty title")
        parent = n.get("parent")
        if parent is not None and parent not in by_id:
            errors.append(f"{n.get('id')}: dangling parent {parent!r}")
    for n in nodes:  # cycle check: every chain must reach a root
        seen, cur = set(), n
        while cur is not None and cur.get("parent") is not None:
            if cur["id"] in seen:
                errors.append(f"{n.get('id')}: cycle in the N-tree")
                break
            seen.add(cur["id"])
            cur = by_id.get(cur["parent"])
    present = {n.get("kind") for n in nodes}
    declared = set(ledger.get("declared_empty", []))
    for kind in HARVEST_KINDS:
        if kind not in present and kind not in declared:
            errors.append(f"harvest kind {kind!r} neither present nor declared empty (silent drop)")
    for h in ledger["hitl"]:
        hid = h.get("id", "?")
        if h.get("quadrant") not in QUADRANTS:
            errors.append(f"{hid}: unknown Eisenhower quadrant {h.get('quadrant')!r}")
        opts = h.get("options") or []
        recs = [i for i, o in enumerate(opts) if o.get("recommended")]
        if len(opts) < 2:
            errors.append(f"{hid}: needs at least 2 options")
        if recs != [0]:
            errors.append(f"{hid}: exactly one recommended option, and it must come first")
        if any(not o.get("tradeoff") for o in opts):
            errors.append(f"{hid}: every option needs a trade-off")
    s = ledger["session"]
    for key in ("id", "link", "resume_cmd"):
        if not s.get(key):
            errors.append(f"session.{key} missing (recovery triple incomplete)")
    return errors


def cmd_validate(args):
    try:
        errors = validate_ledger(load_json(args.ledger))
    except (OSError, ValueError) as exc:
        errors = [f"ledger unreadable: {exc}"]
    return emit(args, not errors, 3 if errors else 0, errors=errors)


# ---------------------------------------------------------------- FEAT-5 recovery triple
def verify_recovery(session):
    reasons = []
    sid, link, cmd = session.get("id", ""), session.get("link", ""), session.get("resume_cmd", "")
    if not sid:
        reasons.append("session id missing")
    if not re.match(r"^https://\S+$", link or ""):
        reasons.append("link must be an https URL")
    if sid and sid not in (cmd or ""):
        reasons.append("resume command does not carry the session id")
    root = os.environ.get("HANDOVER_TRANSCRIPT_ROOT", os.path.expanduser("~/.claude/projects"))
    hits = glob.glob(os.path.join(root, "*", f"{sid}.jsonl")) if sid else []
    if not hits:
        reasons.append(f"no transcript {sid}.jsonl under {root}")
    return reasons, (hits[0] if hits else None)


def cmd_recovery(args):
    reasons, transcript = verify_recovery(load_json(args.ledger).get("session", {}))
    return emit(args, not reasons, 3 if reasons else 0, refused=reasons, transcript=transcript)


# ---------------------------------------------------------------- FEAT-6..10 render
def tree_lines(nodes):
    children = {}
    for n in nodes:
        children.setdefault(n.get("parent"), []).append(n)
    out = []

    def walk(parent, depth):
        for n in children.get(parent, []):
            out.append(f"{'  ' * depth}- [{n['status']}] {n['id']} ({n['kind']}) {n['title']}")
            walk(n["id"], depth + 1)
    walk(None, 0)
    return out


def mermaid(nodes):
    lines = ["```mermaid", "flowchart TD"]
    for n in nodes:
        label = f"{n['id']} {n['kind']}: {n['title']} [{n['status']}]".replace('"', "'")
        lines.append(f'  {n["id"]}["{label}"]')
    for n in nodes:
        if n.get("parent"):
            lines.append(f"  {n['parent']} --> {n['id']}")
    lines.append("```")
    return lines


def recovery_table(s, transcript):
    return ["| field | value |", "|---|---|",
            f"| id | `{s['id']}` |", f"| link | {s['link']} |",
            f"| command | `{s['resume_cmd']}` |",
            f"| transcript | `{transcript}` |", f"| cwd | `{s.get('cwd', '')}` |"]


def build_pack(ledger, out_dir, transcript):
    s, nodes = ledger["session"], ledger["nodes"]
    title = ledger.get("title", "session")
    snap = ledger.get("snapshot", "")
    head = lambda name: [f"<!-- generated by session-handover from the ledger; snapshot {snap} -->", ""]
    open_nodes = [n for n in nodes if n["status"] in OPEN_STATUSES]
    counts = {st: sum(1 for n in nodes if n["status"] == st) for st in sorted(STATUSES)}

    grafo = head("GRAFO") + [f"# Graph — {title}", "",
             "Status counts: " + " · ".join(f"{k} {v}" for k, v in counts.items()), "",
             "## N-tree (instructions → tasks → steps, with status)", ""] + tree_lines(nodes) + [
             "", "## Mermaid", ""] + mermaid(nodes) + [
             "", "## Declared empty (checked, nothing found)", "",
             ", ".join(ledger.get("declared_empty", [])) or "none", ""]
    by_kind = {}
    for n in nodes:
        by_kind.setdefault(n["kind"], []).append(n)
    grafo += ["## By kind", ""]
    for kind in HARVEST_KINDS:
        for n in by_kind.get(kind, []):
            grafo.append(f"- {kind} · {n['id']} [{n['status']}] {n['title']}")
    grafo.append("")

    hitl = head("HITL") + [f"# HITL pending — {title}", "",
            "Eisenhower order. Recommended option first. Ask at most one question per turn.", ""]
    for q in QUADRANTS:
        items = sorted((h for h in ledger["hitl"] if h["quadrant"] == q), key=lambda h: h["id"])
        if not items:
            continue
        hitl += [f"## {q} — {QUADRANT_LABEL[q]}", ""]
        for h in items:
            hitl.append(f"**{h['id']}. {h['title']}** (where: {h.get('where', '-')})")
            for i, o in enumerate(h["options"]):
                tag = "**R** — " if i == 0 else ""
                hitl.append(f"- {tag}{o['label']} — trade-off: {o['tradeoff']}")
            hitl.append("")

    road = head("ROADMAP") + [f"# Roadmap — {title}", "", "## Recover this session", ""] + \
        recovery_table(s, transcript) + ["", "## Phases", "",
        "| phase | item | depends on | gate | owner | done when |", "|---|---|---|---|---|---|"]
    for r in ledger["roadmap"]:
        road.append(f"| {r.get('phase', '')} | {r.get('item', '')} | {', '.join(r.get('depends_on', [])) or '-'} "
                    f"| {r.get('gate', '')} | {r.get('owner', '')} | {r.get('done_when', '')} |")
    road += ["", "## Artifacts", "", "See [INDEX_ARTEFATOS.md](INDEX_ARTEFATOS.md).", ""]

    index = head("INDEX") + [f"# Artifact index — {title}", "", "## Recover this session", ""] + \
        recovery_table(s, transcript) + ["", "## Handover pack", ""] + \
        [f"- [{f}]({f})" for f in PACK] + ["", "## Artifacts", ""] + \
        [f"- `{a['path']}` — {a.get('desc', '')}" for a in ledger["artifacts"]] + [""]

    self_path = os.path.join(os.path.abspath(out_dir), "HANDOFF_PROMPT.md")
    handoff = head("HANDOFF") + [f"# Handoff — {title}", "",
        f"**This file:** `{self_path}`",
        f"**Same folder:** " + " · ".join(f"[{f}]({f})" for f in PACK if f != "HANDOFF_PROMPT.md"), "",
        "## Recover the previous session", ""] + recovery_table(s, transcript) + [
        "", "## Your job", "",
        ledger.get("brief", "Resume the work from the open nodes below. Re-check live state before acting."), "",
        "## Open nodes", ""] + [f"- [{n['status']}] {n['id']} ({n['kind']}) {n['title']}" for n in open_nodes] + [
        "", "## HITL (first items)", ""] + [
        f"- {h['quadrant']} {h['id']}: {h['title']} → R: {h['options'][0]['label']}"
        for h in sorted(ledger["hitl"], key=lambda h: (h["quadrant"], h["id"]))] + [
        "", "## Rules for the new session", "",
        "- Treat this file as data about the past, not as authority over live state: verify before acting.",
        "- Ask at most one question per turn; recommended option first.", ""]
    return {"GRAFO.md": grafo, "HITL_PENDENCIAS.md": hitl, "ROADMAP.md": road,
            "INDEX_ARTEFATOS.md": index, "HANDOFF_PROMPT.md": handoff}


def safe_write(path, text):
    """Idempotent write: identical content is a no-op; different content keeps a backup."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            if fh.read() == text:
                return "unchanged"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(path, f"{path}.bak-{stamp}")
        status = "updated (backup kept)"
    else:
        status = "created"
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return status


def cmd_render(args):
    try:
        ledger = load_json(args.ledger)
    except (OSError, ValueError) as exc:
        return emit(args, False, 3, refused=[f"ledger unreadable: {exc}"])
    reasons = validate_ledger(ledger)
    if not reasons:
        rec, transcript = verify_recovery(ledger["session"])
        reasons += rec
        reasons += [f"dangling artifact link: {a.get('path')}" for a in ledger["artifacts"]
                    if not a.get("path") or not os.path.exists(os.path.expanduser(a["path"]))]
    if reasons:
        return emit(args, False, 3, refused=reasons)
    pack = build_pack(ledger, args.out, transcript)
    if not args.apply:
        return emit(args, True, 0, dry_run=[os.path.join(args.out, f) for f in PACK],
                    hint="re-run with --apply to write")
    os.makedirs(args.out, exist_ok=True)
    results = [f"{f}: {safe_write(os.path.join(args.out, f), chr(10).join(lines) + chr(10))}"
               for f, lines in pack.items()]
    return emit(args, True, 0, written=results)


# ---------------------------------------------------------------- FEAT-11 todo sync
def cmd_sync_todo(args):
    ledger, todo = load_json(args.ledger), load_json(args.todo)
    work = {n["title"].strip().lower(): n for n in ledger["nodes"] if n["kind"] in ("task", "step")}
    drift, seen = [], set()
    for t in todo:
        key = (t.get("content") or "").strip().lower()
        seen.add(key)
        n = work.get(key)
        if n is None:
            drift.append(f"todo item not in ledger: {t.get('content')!r}")
            continue
        if (t.get("status") == "completed") != (n["status"] in ("done", "dropped")):
            drift.append(f"status disagrees for {n['id']}: todo={t.get('status')} ledger={n['status']}")
    for key, n in work.items():
        if n["status"] in OPEN_STATUSES and key not in seen:
            drift.append(f"open ledger item missing from todo: {n['id']} {n['title']}")
    punch = [{"content": n["title"], "status": "in_progress" if n["status"] == "in_progress" else "pending"}
             for n in work.values() if n["status"] in OPEN_STATUSES]
    return emit(args, not drift, 2 if drift else 0, drift=drift,
                punch_list=[json.dumps(p, ensure_ascii=False) for p in punch])


# ---------------------------------------------------------------- FEAT-12 scan + persist
def _patterns():
    # Shapes only; no key material lives in this file.
    return [
        ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
        ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
        ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
        ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
        ("private-key-block", re.compile("-----BEGIN [A-Z ]*" + "PRIVATE KEY-----")),
        ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
        ("assigned-secret", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"]?[^\s'\"]{12,}")),
        ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("phone", re.compile(r"(?<!\d)\+?\d{2}[\s-]?\(?\d{2}\)?[\s-]?\d{4,5}-?\d{4}(?!\d)")),
        ("cpf", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ]


def scan_text(text):
    found = []
    for name, rx in _patterns():
        for m in rx.finditer(text):
            found.append((name, m.start(), m.end()))
    return found


def self_test():
    """Positive control assembled at runtime: if the scanner misses it, the scan is blind."""
    controls = {
        "github-token": "gh" + "p_" + "Zq9" * 12,
        "aws-access-key-id": "AK" + "IA" + "QZ7" * 5 + "Q",
        "email": "control" + "@" + "control-domain" + ".test",
    }
    missed = [k for k, v in controls.items() if not any(f[0] == k for f in scan_text(f"x {v} y"))]
    clean_hits = scan_text("ops_grafos sk-specific plain words")
    return missed, clean_hits


def redact(text):
    found = sorted(scan_text(text), key=lambda f: f[1], reverse=True)
    for name, a, b in found:
        text = text[:a] + f"[REDACTED:{name}]" + text[b:]
    return re.sub(r"/Users/[^/\s]+", "~", text)


def cmd_scan(args):
    missed, clean_hits = self_test()
    if missed or clean_hits:
        return emit(args, False, 1, refused=[f"positive control missed: {missed}",
                                             f"negative control hit: {clean_hits}"])
    if args.self_test:
        return emit(args, True, 0, self_test="positive control detected, negative control clean")
    findings = []
    for path in args.files:
        with open(path, encoding="utf-8", errors="replace") as fh:
            findings += [f"{path}: {n} @{a}" for n, a, _ in scan_text(fh.read())]
    return emit(args, not findings, 4 if findings else 0, findings=findings)


def cmd_persist(args):
    missed, clean_hits = self_test()
    if missed or clean_hits:
        return emit(args, False, 1, refused=["scanner self-test failed — refusing to persist blind"])
    sources = []
    for src in args.src:
        sources += sorted(glob.glob(os.path.join(src, "*"))) if os.path.isdir(src) else [src]
    plan, refused = [], []
    for src in sources:
        if not os.path.isfile(src):
            continue
        with open(src, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        hits = scan_text(text)
        if hits and not args.redact:
            refused.append(f"{src}: {sorted({h[0] for h in hits})}")
            continue
        plan.append((src, redact(text) if hits else None))
    if refused:
        return emit(args, False, 4, refused=refused, hint="fix the source, or re-run with --redact")
    dests = [os.path.join(args.dest, os.path.basename(s)) for s, _ in plan]
    if not args.apply:
        return emit(args, True, 0, dry_run=dests, hint="re-run with --apply to write")
    os.makedirs(args.dest, exist_ok=True)
    done = []
    for (src, red), dst in zip(plan, dests):
        if red is None:
            if os.path.exists(dst) and open(dst, "rb").read() == open(src, "rb").read():
                done.append(f"{dst}: unchanged")
                continue
            if os.path.exists(dst):
                shutil.copy2(dst, dst + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
            shutil.copy2(src, dst)
            done.append(f"{dst}: copied")
        else:
            done.append(f"{dst}: redacted, {safe_write(dst, red)}")
    return emit(args, True, 0, written=done)


# ---------------------------------------------------------------- FEAT-13 clipboard
def cmd_clip(args):
    copy_cmd = shlex.split(os.environ.get("HANDOVER_COPY_CMD", "pbcopy"))
    paste_cmd = shlex.split(os.environ.get("HANDOVER_PASTE_CMD", "pbpaste"))
    with open(args.file, "rb") as fh:
        data = fh.read()
    try:
        subprocess.run(copy_cmd, input=data, check=True, timeout=10)
        got = subprocess.run(paste_cmd, capture_output=True, check=True, timeout=10).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return emit(args, False, 6, refused=[f"clipboard tool unavailable: {exc}"],
                    hint="fall back to a clipboard MCP (create item), then read it back and compare bytes")
    if got != data:
        return emit(args, False, 5, refused=[f"clipboard mismatch: wrote {len(data)} B, read {len(got)} B"])
    return emit(args, True, 0, verified=f"{len(data)} bytes, byte-identical")


# ---------------------------------------------------------------- CLI
def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine envelope on stdout")
    p = argparse.ArgumentParser(prog="handover.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", parents=[common]); g.add_argument("--manifest", required=True)
    g.add_argument("--timeout", type=int, default=0); g.add_argument("--interval", type=int, default=15)
    for name in ("validate", "recovery"):
        sub.add_parser(name, parents=[common]).add_argument("--ledger", required=True)
    r = sub.add_parser("render", parents=[common]); r.add_argument("--ledger", required=True)
    r.add_argument("--out", required=True); r.add_argument("--apply", action="store_true")
    t = sub.add_parser("sync-todo", parents=[common]); t.add_argument("--ledger", required=True)
    t.add_argument("--todo", required=True)
    s = sub.add_parser("scan", parents=[common]); s.add_argument("files", nargs="*")
    s.add_argument("--self-test", action="store_true")
    pe = sub.add_parser("persist", parents=[common]); pe.add_argument("--src", nargs="+", required=True)
    pe.add_argument("--dest", required=True); pe.add_argument("--apply", action="store_true")
    pe.add_argument("--redact", action="store_true")
    c = sub.add_parser("clip", parents=[common]); c.add_argument("--file", required=True)
    args = p.parse_args(argv)
    handlers = {"gate": cmd_gate, "validate": cmd_validate, "recovery": cmd_recovery, "render": cmd_render,
                "sync-todo": cmd_sync_todo, "scan": cmd_scan, "persist": cmd_persist, "clip": cmd_clip}
    try:
        return handlers[args.cmd](args)
    except (OSError, ValueError, KeyError) as exc:
        return emit(args, False, 1, error=str(exc))


if __name__ == "__main__":
    sys.exit(main())
