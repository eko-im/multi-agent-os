#!/usr/bin/env python3
"""request-carried-authorization: deterministic half of the pre-HITL "step 0" check.

Question it answers: did the operator's OWN request already carry the authorization
for this concrete action (explicitly, implicitly or inherently)?

It reads one JSON case (file path or stdin) and prints a JSON verdict:

    A  ACT              carried, in scope, reversible and low-effect
    B  ACT_WITH_UNDO    carried, in scope, effect deserves a net, undo written AND verified first
    C  NOT_CARRIED      the request does not carry it. Two kinds:
         kind=hard        an invariant was hit; nothing downstream may open it -> human residue
         kind=ladder      hand the case, unchanged, to the existing pre-HITL ladder
                          (measure / reversible / taste test, council-gate, ...). This step never
                          adds a NEW reason to escalate.

The cognitive half (the seven minds) lives in SKILL.md; this script only refuses to let
an unanswered mind, an untrusted origin, or a hard flag be waved through. It is stdlib-only,
makes no model call, and fails closed: a missing or malformed field is treated as the
unsafe value.

Exit codes: 0 = A, 10 = B, 20 = C (kind=ladder), 30 = C (kind=hard), 2 = bad input.
"""
from __future__ import annotations

import json
import sys
from typing import Any

MINDS = (
    "thomas",       # measure at the source
    "critical",     # premises right, current, consistent
    "curious",      # what else does the request imply
    "suspicious",   # did the grant really come from the operator
    "resilient",    # named undo, stop point
    "vulcan",       # premise -> conclusion holds
    "red_team",     # worst case of acting AND of asking
)

# Only these origins can carry an operator grant. Everything else is DATA.
TRUSTED_ORIGINS = {"operator_turn", "conductor_decision"}
DATA_ORIGINS = {
    "tool_output", "file", "web_page", "email", "agent_note", "bot_comment",
    "ticket", "pr_comment_non_operator", "memory", "unknown",
}

# Hard flags: the request can never carry these by implication. Explicit operator
# approval for them is handled by the human/HITL path, not by this step.
HARD_FLAGS = (
    "spend",                    # buy, subscribe, start a paid resource
    "raw_secret",               # print, log or commit a secret value
    "irreversible_in_prod",     # no verified rescue reference
    "external_send",            # message/email/post to a third party
    "third_party_domain",       # account, data or system of someone who did not delegate
    "cross_world_credential",   # a credential used outside its owner's domain
    "human_domain",             # personal taste, corporate/organizational norm
    "access_control_self_approval",  # change that lets my accounts approve my own change
)

VIAS = {"explicit", "implicit", "inherent"}

EXIT = {"A": 0, "B": 10, ("C", "ladder"): 20, ("C", "hard"): 30}


def _bool(d: dict, key: str, unsafe: bool) -> bool:
    """Return d[key] if it is a real bool, else the UNSAFE value (fail closed)."""
    v = d.get(key)
    return v if isinstance(v, bool) else unsafe


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    request = case.get("request") or {}
    action = case.get("action") or {}
    flags = action.get("flags") or {}
    minds = case.get("minds") or {}

    def verdict(code: str, kind: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"verdict": code, "reasons": reasons}
        if kind:
            out["kind"] = kind
        if code == "C":
            out["escalation_card"] = {
                "what_it_is": None,
                "what_it_is_for": None,
                "impact_if_yes": None,
                "impact_if_no": None,
                "recommendation": None,
                "note": (
                    "fill all five before showing a human"
                    if kind == "hard"
                    else "run the existing pre-HITL ladder first; only its residue reaches a human"
                ),
            }
        return out

    # 1. Hard flags first. Confidence never opens them.
    hit = [f for f in HARD_FLAGS if _bool(flags, f, unsafe=False) is True]
    unknown = [f for f in HARD_FLAGS if f not in flags]
    if hit:
        reasons.append("hard flag: " + ", ".join(hit))
        return verdict("C", "hard")
    if unknown:
        # Fail closed: an unstated flag is treated as possibly set.
        reasons.append("hard flag not stated (fail closed): " + ", ".join(unknown))
        return verdict("C", "hard")

    # 2. The operator said no (now or earlier) beats every analysis.
    if _bool(request, "operator_said_no", unsafe=True):
        reasons.append("operator refused or refusal not ruled out")
        return verdict("C", "hard")

    # 3. Origin: a grant inside data is data, not an order.
    origin = request.get("origin", "unknown")
    if origin not in TRUSTED_ORIGINS:
        reasons.append(f"grant origin '{origin}' is data, not an operator manifestation")
        return verdict("C", "hard")
    if origin == "conductor_decision" and not request.get("authority_origin"):
        reasons.append("conductor decision without authority_origin (the operator's original grant)")
        return verdict("C", "hard")

    # 4. All seven minds must be answered. A skipped mind is a false gate.
    missing = [m for m in MINDS if not str(minds.get(m, "")).strip()]
    if missing:
        reasons.append("minds not answered (fail closed): " + ", ".join(missing))
        return verdict("C", "ladder")
    if _bool(case, "suspicious_doubt", unsafe=True):
        reasons.append("suspicious mind still doubts the origin")
        return verdict("C", "hard")

    # 5. Which via carries it.
    via = action.get("via")
    if via not in VIAS:
        reasons.append("no explicit, implicit or inherent via")
        return verdict("C", "ladder")

    # 6. Scope: the means must have the SAME consequence as what was asked,
    #    and be necessary and proportional (agency law: necessary or incidental).
    if not _bool(action, "consequence_matches_request", unsafe=False):
        reasons.append("means has a different consequence than the request (scope extension)")
        return verdict("C", "ladder")
    if via in {"implicit", "inherent"} and not (
        _bool(action, "necessary", unsafe=False) and _bool(action, "proportional", unsafe=False)
    ):
        reasons.append(f"{via} via needs the means to be necessary AND proportional")
        return verdict("C", "ladder")

    # 7. Two readings with different costs: only the cheap reversible one is carried.
    readings = action.get("readings", "multiple_diff_cost")
    if readings == "multiple_diff_cost" and not _bool(action, "cheap_reading_chosen", unsafe=False):
        reasons.append("two readings with different cost and the cheap reversible one was not chosen")
        return verdict("C", "ladder")

    # 8. Evidence against the request's facts: correct the premise first.
    if _bool(action, "evidence_against_request", unsafe=True):
        reasons.append("evidence contradicts the request's facts: correct with evidence before acting")
        return verdict("C", "ladder")

    # 9. Reversibility decides A vs B.
    reversible = _bool(action, "reversible", unsafe=False)
    effect = action.get("effect", "significant")
    if reversible and effect == "trivial":
        reasons.append(f"carried via {via}; reversible and trivial")
        return verdict("A")
    if action.get("undo") and _bool(action, "undo_verified", unsafe=False):
        reasons.append(f"carried via {via}; undo written and verified before acting")
        return verdict("B")
    reasons.append("carried, but no verified undo for a non-trivial effect")
    return verdict("C", "ladder")


def exit_code(result: dict[str, Any]) -> int:
    v = result["verdict"]
    return EXIT[v] if v in ("A", "B") else EXIT[(v, result["kind"])]


def main(argv: list[str]) -> int:
    try:
        raw = open(argv[1], encoding="utf-8").read() if len(argv) > 1 else sys.stdin.read()
        case = json.loads(raw)
        if not isinstance(case, dict):
            raise ValueError("case must be a JSON object")
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    result = evaluate(case)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
