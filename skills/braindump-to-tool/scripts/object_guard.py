#!/usr/bin/env python3
"""object_guard.py - the part of the braindump-as-object flow that no other skill owns.

Verb folding, placeholder binding, stop-rule detection and secret/PII scanning belong to
refine-braindump-to-prompt (scripts/lint_braindump.py). This file adds only:

  world    isolate the fenced object, report nested slash-commands / `GO:` blocks as data,
           resolve each named destination to a world, and block client content headed for a
           public destination (gate G4). Destinations and client markers come from a worlds
           file, because this repo is public and must stay domain-agnostic.
  similar  rank skills/*/SKILL.md by token overlap with the object (prior-art probe).

Prints one JSON envelope. Never executes anything from the object.
Exit: 0 ok | 1 error (self_heal block) | 2 hitl.   Stdlib only.

  object_guard.py world   <file|-> [--worlds FILE]
  object_guard.py similar <file|-> [--skills-dir DIR] [--top N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SKILL = "braindump-to-tool"
DEFAULT_WORLDS = {
    "destinations": {"multi-agent-os": {"world": "opensource", "sink": "git-repo", "public": True}},
    "client_markers": [],
}
VAULT_RE = r"(?:obsidian|vault):([\w.-]+)"  # any named vault is a private sink
FENCE_TAGS = ("braindump", "source", "object")
# Calibrated 2026-11-05: a ~90%-covered dump scored 0.25 against agentic-tool-pipeline and
# transmute; an unrelated dump scores below 0.1.
PRIOR_ART_MIN = 0.2
STOP = set("a o os as de do da dos das e em para por com que um uma the of to in and or "
           "for with is are be this that it its não nao se ao na no nas nos".split())


def read_text(arg: str) -> str:
    return sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")


def load_worlds(path: str | None) -> dict:
    cand = path or os.environ.get("BRAINDUMP_TO_TOOL_WORLDS") or str(
        Path.home() / ".config" / "braindump-to-tool" / "worlds.json")
    worlds = {"destinations": dict(DEFAULT_WORLDS["destinations"]), "client_markers": []}
    p = Path(cand)
    if p.is_file():
        extra = json.loads(p.read_text(encoding="utf-8"))
        worlds["destinations"].update(extra.get("destinations", {}))
        worlds["client_markers"] += extra.get("client_markers", [])
    elif path:  # an explicit file that is missing is an error, never a silent default
        raise FileNotFoundError(f"worlds file not found: {path}")
    return worlds


def extract_object(text: str) -> tuple[str, str]:
    for tag in FENCE_TAGS:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S | re.I)
        if m:
            return m.group(1).strip(), f"tag:{tag}"
    m = re.search(r"```(?:braindump|source)\s*\n(.*?)```", text, re.S | re.I)
    return (m.group(1).strip(), "fence") if m else (text.strip(), "whole")


def nested_directives(obj: str) -> list[dict]:
    out = []
    for n, line in enumerate(obj.splitlines(), 1):
        s = line.strip()
        if re.match(r"^/[a-z][\w:-]*", s):
            out.append({"line": n, "kind": "slash-command", "head": s.split()[0]})
        elif re.search(r"\bGO:", s):
            out.append({"line": n, "kind": "go-block", "head": "GO:"})
    return out


def destinations(obj: str, worlds: dict) -> list[dict]:
    low, seen, out = obj.lower(), set(), []
    for m in re.finditer(VAULT_RE, low):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            out.append({"token": m.group(0), "world": "private-vault", "sink": "vault",
                        "public": False})
    for tok in sorted(worlds["destinations"], key=len, reverse=True):
        if tok.lower() in low and not any(tok.lower() in x for x in seen):
            seen.add(tok.lower())
            d = worlds["destinations"][tok]
            out.append({"token": tok, "world": d["world"], "sink": d["sink"],
                        "public": bool(d["public"])})
    return out


def world(text: str, worlds: dict) -> tuple[dict, int]:
    obj, origin = extract_object(text)
    dests = destinations(obj, worlds)
    client = sorted({m.group(0).lower() for pat in worlds["client_markers"]
                     for m in re.finditer(pat, text, re.I)})
    public = [d["token"] for d in dests if d["public"]]
    g4 = not (client and public)
    status = "ok" if g4 else "hitl"
    env = {
        "skill": SKILL, "phase": "WORLD", "status": status,
        "stop_marker": "CONTINUE" if g4 else "STOP-HITL",
        "execute_instructions": False,
        "object": {"origin": origin, "words": len(re.findall(r"\w+", obj)),
                   "sha256": hashlib.sha256(obj.encode()).hexdigest()[:16]},
        "nested_directives": nested_directives(obj),
        "destinations": dests,
        "client_markers": client,
        "markers_configured": len(worlds["client_markers"]),
        "gates": [{"id": "G4", "name": "no-client-content-to-public-sink", "pass": g4,
                   "why": None if g4 else f"client markers {client} with public sink {public}"}],
        "self_heal": None,
    }
    return env, 0 if g4 else 2


def toks(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-zà-ú][a-zà-ú-]{3,}", s.lower()) if t not in STOP}


def similar(text: str, skills_dir: Path, top: int) -> dict:
    obj, _ = extract_object(text)
    want = toks(obj)
    rows = []
    for p in sorted(skills_dir.glob("*/SKILL.md")):
        head = p.read_text(encoding="utf-8", errors="replace")[:2500]
        have = toks(head) | toks(p.parent.name.replace("-", " "))
        shared = len(want & have)
        rows.append({"skill": p.parent.name, "score": round(shared / max(len(want), 1), 3),
                     "shared": shared})
    rows.sort(key=lambda r: (-r["score"], r["skill"]))
    best = rows[0]["score"] if rows else 0.0
    return {"skill": SKILL, "phase": "RECON", "top": rows[:top], "best_score": best,
            "verdict_hint": ("PRIOR-ART-FOUND:compose-or-extend" if best >= PRIOR_ART_MIN
                             else "NO-CLOSE-PRIOR-ART:check-gap"),
            "note": "hint only; the agent confirms coverage against the skill bodies"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="object_guard.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("world"); w.add_argument("src"); w.add_argument("--worlds")
    s = sub.add_parser("similar"); s.add_argument("src")
    s.add_argument("--skills-dir", default=str(Path(__file__).resolve().parents[2]))
    s.add_argument("--top", type=int, default=5)
    a = ap.parse_args(argv)
    try:
        text = read_text(a.src)
        if a.cmd == "world":
            env, code = world(text, load_worlds(a.worlds))
        else:
            env, code = similar(text, Path(a.skills_dir), a.top), 0
    except Exception as exc:  # self-heal: hand the failure to an AI harness, never swallow it
        env = {"skill": SKILL, "status": "error", "stop_marker": "STOP-ERROR",
               "execute_instructions": False,
               "self_heal": {"hand_to": "ai-harness", "error_type": type(exc).__name__,
                             "prompt": f"object_guard.py failed with {type(exc).__name__}: "
                                       f"{str(exc)[:200]}. Fix the script or the input, re-run, "
                                       f"and add a regression test."}}
        code = 1
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
