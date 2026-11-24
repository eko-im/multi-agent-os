#!/usr/bin/env python3
"""lint_braindump.py - deterministic pre-pass for refine-braindump-to-prompt.

The skill is HYBRID. The cognitive part (RECOVER/DRAFT/REFINE/RED-TEAM) stays with
the agent; this script does the parts that must give the same answer every time:

  1. verb collapse    - map every directive verb (en + pt) to ONE canonical phase,
                        report synonyms and repeats (e.g. "validate" twice,
                        fix/solve/improve/enhance/expand -> REFINE.correct).
  2. placeholders     - find {{name}} tokens with no binding (S-unbound).
  3. self-reference   - detect a dump whose object is the refine pipeline itself
                        (meta-dump), so the agent applies the meta-depth=1 rule.
  4. stop / DoD       - flag a dump with no stop rule and no done-condition.
  5. sanitize         - scan for secrets / PII before any PUBLIC sink.
  6. sink split       - when the dump names both public and private sinks, say so
                        (the caller passes the sink names; nothing is hardcoded).

stdlib only. Output: one JSON object on stdout.

Exit codes:
  0  clean (the agent may proceed)
  1  findings that HALT (unbound placeholder, or secret/PII with a public sink)
  2  usage error
  3  internal error - stdout carries a self_heal block for an AI harness
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
import unicodedata

SELF_NAME = "refine-braindump-to-prompt"

# (canonical verb, phase, surface regexes). Order matters only for readability.
# Surface forms are matched on accent-stripped, lower-cased text, on word edges.
VERBS: list[tuple[str, str, tuple[str, ...]]] = [
    ("analyze", "RECOVER.dissect", (r"analy[sz]e", r"analise", r"analisar", r"decompo[sn]\w*", r"dissect")),
    ("reuse-scan", "RECOVER.reuse-scan", (r"busque semelhantes", r"search (?:for )?similar\w*", r"find similar\w*", r"prior art")),
    ("relate", "RECOVER.relate", (r"cruze", r"cross(?:-check)?", r"compare", r"relate")),
    ("critique", "REFINE.critique", (r"meta-?critique", r"meta-?critica", r"critique", r"critica", r"criticar")),
    ("validate", "REFINE.validate", (r"validate", r"valide", r"validar", r"verify", r"verifique")),
    ("correct", "REFINE.correct", (r"fix", r"solve", r"corrija", r"resolva", r"improve", r"melhore", r"enhance", r"aprimore", r"expand", r"expanda")),
    ("harmonize", "REFINE.harmonize", (r"harmoni[sz]e", r"harmonizar?")),
    ("sanitize", "RENDER.sanitize", (r"saniti[sz]e", r"sanitizar?")),
    ("delegate", "HANDOFF", (r"delegue", r"delegate", r"anima", r"forge")),
    ("closeout", "CLOSEOUT", (r"git-cycle", r"diy-pr-review", r"house-(?:cleaning|keeping)", r"boy-scout", r"signoff")),
]

# Bare "ate" (pt "ate" = until, but also en "ate") and bare "max" matched ordinary prose, so
# only the phrase forms count.
STOP_MARKERS = (r"\buntil\b", r"\bate que\b", r"\bate (?:zero|o fim|convergir)\b", r"\bstop\b",
                r"\bpare\b", r"\bdod\b", r"\bdone when\b", r"\bcriterio\b", r"\baceite\b",
                r"\bacceptance\b", r"\bmax[- ]rounds?\b")

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][\w.-]*)\s*\}\}")

# Secret / PII detectors. Kept narrow: a false "clean" is worse than a noisy flag,
# but a noisy flag on every run teaches people to ignore it.
SECRETS: list[tuple[str, re.Pattern[str]]] = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone-e164", re.compile(r"(?<![\w+])\+\d{11,15}\b")),
]


def fold(text: str) -> str:
    """Lower-case and strip accents so 'análise' and 'analise' match the same rule."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def mask(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 5) + value[-2:]


def collapse_verbs(folded: str) -> dict:
    canon: dict[str, dict] = {}
    for name, phase, forms in VERBS:
        hits: list[str] = []
        for form in dict.fromkeys(forms):  # de-dup while keeping order
            for m in re.finditer(r"(?<![\w-])" + form + r"(?![\w-])", folded):
                hits.append(m.group(0))
        if hits:
            canon[name] = {"phase": phase, "count": len(hits), "surface": sorted(set(hits))}
    redundant = {k: v for k, v in canon.items() if v["count"] > 1 or len(v["surface"]) > 1}
    phases = sorted({v["phase"] for v in canon.values()})
    return {"canonical": canon, "redundant": redundant, "phases": phases}


def find_placeholders(text: str, bindings: set[str]) -> dict:
    names = sorted(set(PLACEHOLDER.findall(text)))
    return {"found": names, "unbound": [n for n in names if n not in bindings]}


def self_reference(folded: str, phases: list[str], self_name: str) -> dict:
    reasons = []
    if fold(self_name) in folded:
        reasons.append("names-self")
    pipeline_phases = [p for p in phases if p.split(".")[0] in ("RECOVER", "REFINE")]
    # "braindump" alone is ordinary ("analyse the braindump and validate it"). The dump is
    # meta only when it is a TEMPLATE over braindumps ({{braindump}}), or when it spells out
    # most of the refine pipeline itself (>= 5 of the 7 RECOVER/REFINE phases).
    if "{{braindump" in folded.replace(" ", ""):
        reasons.append("templates-over-braindumps")
    elif "braindump" in folded and len(pipeline_phases) >= 5:
        reasons.append("object-is-braindump+pipeline-verbs")
    return {"meta": bool(reasons), "reasons": reasons}


def has_stop(folded: str) -> bool:
    return any(re.search(p, folded) for p in STOP_MARKERS)


def scan_secrets(text: str, allow: set[str]) -> list[dict]:
    allowed = {a.casefold() for a in allow}
    out = []
    for kind, rx in SECRETS:
        for m in rx.finditer(text):
            if m.group(0).casefold() in allowed:
                continue
            out.append({"kind": kind, "masked": mask(m.group(0)), "offset": m.start()})
    return out


def _named(name: str, folded: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(fold(name)) + r"(?![\w-])", folded) is not None


def sinks(folded: str, public: list[str], private: list[str]) -> dict:
    """A sink passed by the caller IS a destination, named in the dump or not.

    `declared_*` drives the halt (a secret bound for a declared public sink must stop
    even if the dump calls it "the OSS repo"). `mentioned_*` is information only.
    """
    return {
        "declared_public": list(public),
        "declared_private": list(private),
        "mentioned_public": [s for s in public if _named(s, folded)],
        "mentioned_private": [s for s in private if _named(s, folded)],
        "split_required": bool(public and private),
    }


def lint(text: str, bindings: set[str], public: list[str], private: list[str],
         self_name: str = SELF_NAME, allow: set[str] | None = None) -> dict:
    if not text.strip():
        return {"status": "halt", "halts": ["empty-dump"], "warnings": []}
    folded = fold(text)
    verbs = collapse_verbs(folded)
    ph = find_placeholders(text, bindings)
    meta = self_reference(folded, verbs["phases"], self_name)
    stop = has_stop(folded)
    secrets = scan_secrets(text, allow or set())
    sk = sinks(folded, public, private)

    halts, warnings = [], []
    if ph["unbound"]:
        halts.append("unbound-placeholder")
    if secrets and sk["declared_public"]:
        halts.append("secret-or-pii-with-public-sink")
    elif secrets:
        warnings.append("secret-or-pii-present")
    if meta["meta"]:
        warnings.append("meta-dump: apply meta-depth=1")
    if not stop:
        warnings.append("no-stop-rule")
    if verbs["redundant"]:
        warnings.append("redundant-verbs")
    if sk["split_required"]:
        warnings.append("world-split: public and private sinks named")

    return {
        "status": "halt" if halts else "ok",
        "halts": halts,
        "warnings": warnings,
        "verbs": verbs,
        "placeholders": ph,
        "self_reference": meta,
        "stop_rule_present": stop,
        "secrets": secrets,
        "sinks": sk,
    }


def self_heal(exc: BaseException, text: str) -> dict:
    """Structured hand-off so an AI harness can repair the run instead of a human."""
    return {
        "status": "error",
        "error": f"{type(exc).__name__}: {exc}",
        "self_heal": {
            "harness_prompt": (
                "lint_braindump.py raised an internal error. Read the traceback, fix the "
                "script or its input encoding, add a regression test in "
                "test_lint_braindump.py that fails before the fix, and re-run. Do not "
                "skip the lint: the agent must not proceed on an unlinted dump."
            ),
            "traceback": traceback.format_exc(limit=5),
            "input_sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dump", help="path to the braindump, or '-' for stdin")
    ap.add_argument("--bind", action="append", default=[],
                    help="placeholder name bound by the enclosing object (repeatable)")
    ap.add_argument("--public-sink", action="append", default=[],
                    help="name of a PUBLIC destination, e.g. an open-source repo (repeatable)")
    ap.add_argument("--private-sink", action="append", default=[],
                    help="name of a PRIVATE destination, e.g. a personal vault (repeatable)")
    ap.add_argument("--allow", action="append", default=[],
                    help="exact string the secret/PII scan must ignore (repeatable)")
    ap.add_argument("--self-name", default=SELF_NAME)
    args = ap.parse_args(argv)

    text = ""
    try:
        if args.dump == "-":
            text = sys.stdin.read()
        else:
            with open(args.dump, encoding="utf-8") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        # Not a content halt (exit 1) and not a script bug (exit 3): the input is unreadable.
        print(json.dumps({"status": "usage-error", "error": f"{type(exc).__name__}: {exc}"}))
        return 2

    try:
        report = lint(text, set(args.bind), args.public_sink, args.private_sink,
                      args.self_name, set(args.allow))
    except Exception as exc:  # noqa: BLE001 - self-heal boundary
        print(json.dumps(self_heal(exc, text), ensure_ascii=False, indent=2))
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "halt" else 0


if __name__ == "__main__":
    sys.exit(main())
