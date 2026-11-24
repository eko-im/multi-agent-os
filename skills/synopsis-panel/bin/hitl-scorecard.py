#!/usr/bin/env python3
"""hitl-scorecard — scorecard view + selection panel of the HITL digest (spec §8).

Extension of the synopsis-panel engine: it reuses the engine's option builder
(`_card_options`, recommended option first, only with an evidence pointer) and its
overflow line; `/hitl-digest` stays the entry point. Python 3 stdlib only.

  render     decisions JSON -> scorecard (--format text|ansi|markdown, --layout full|compact)
  ask        decisions JSON -> AskUserQuestion payload (--target claude) or HTML form (--target omp)
  parse      answer (digest text line, AskUserQuestion result, OMP form values) -> decisions + `fechado`
  aggregate  decision JSON files and/or NEEDS-OPERATOR lines from N sessions -> ordered queue JSON
  lint       spec checks on the input and on every generated surface (or on given artifacts)

Safety invariant: nothing is ever pre-selected. Timeout, idle auto-resolve, cancel, an
unanswered question, free text, or an OMP form without the explicit confirmation box
is PENDING, never consent.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

_FUSE_PATH = Path(__file__).resolve().parent / "synopsis-fuse.py"
_spec = importlib.util.spec_from_file_location("synopsis_fuse_for_scorecard", _FUSE_PATH)
fuse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fuse)

SCHEMA = "hitl-scorecard/v1"
COLS = 80
BODY_MAX = 15                     # attention contract v1.1: body lines
IND = "    "                      # card body indentation
EFFECT_MAX = 60                   # source budget for an option effect (full card line, panel)
LETTERS = "ABCD"
URG = {"alta": ("\u23eb", "ALTA", "1;31"), "media": ("\U0001f53c", "MÉDIA", "1;33"),
       "baixa": ("\U0001f53d", "BAIXA", "32")}
URG_RANK = {"alta": 0, "media": 1, "baixa": 2}
URG_ALIAS = {"alta": "alta", "high": "alta", "urgente": "alta", "\u23eb": "alta",
             "media": "media", "média": "media", "medium": "media", "\U0001f53c": "media",
             "baixa": "baixa", "low": "baixa", "\U0001f53d": "baixa"}
URG_TO_SEV = {"alta": "URGENTE", "media": "ALTA", "baixa": "NORMAL"}  # engine severity names
OWNER = "\U0001f464 SÓ VOCÊ"
DOOR = {True: "\u21a9\ufe0f REVERSÍVEL", False: "\U0001f6aa SEM VOLTA"}
DOOR_GLYPH = {True: "\u21a9\ufe0f", False: "\U0001f6aa"}
DOOR_UNKNOWN = "? REVERSÍVEL NÃO INFORMADO"
HIGH_CONF = {"alta", "high"}
REC = " (recomendado)"
NO_REC = "sem recomendação: falta ponteiro de evidência"
CODE_RE = re.compile(r"K\d{6}-\d{4}-[0-9A-Za-z]{8}", re.I)
TOKEN_RE = re.compile(r"(?:(K\d{6}-\d{4}-[0-9A-Za-z]{8})\.)?(\d+):(\S+)", re.I)
EXPIRED_FLAGS = ("timedOut", "timed_out", "timeout", "expired", "cancelled", "canceled", "dismissed")
CONFIRM_YES = {"sim", "yes", "on", "true", "1"}


class InputError(Exception):
    pass


# ---------------------------------------------------------------- text helpers
def _s(v) -> str:
    return " ".join(str(v if v is not None else "").split())


# Display columns: one measure for the digest, the ⏭ line and the lint (spec §2: an emoji
# counts as 2, box drawing stays 1). The engine owns it; this module never re-implements it.
cols = fuse._cols



def wrap(text: str, first: str, cont: str | None = None, n: int = COLS) -> list[str]:
    """Word wrap within n columns; a word longer than a line is split, never dropped."""
    cont = first if cont is None else cont
    lines, line, fresh = [], first, True
    for word in _s(text).split(" "):
        if not word:
            continue
        trial = line + word if fresh else f"{line} {word}"
        if cols(trial) <= n:
            line, fresh = trial, False
            continue
        if not fresh:
            lines.append(line)
            line, fresh = cont, True
        while word and cols(line + word) > n:      # very long token: hard split
            room = ""
            for ch in word:
                if cols(line + room + ch) > n:
                    break
                room += ch
            room = room or word[0]
            lines.append(line + room)
            word, line = word[len(room):], cont
        if word:
            line, fresh = line + word, False
    if not fresh:
        lines.append(line)
    return lines or [first.rstrip()]


# ---------------------------------------------------------------- model
def _option_index(ref, opts: list[dict]):
    if isinstance(ref, bool) or ref is None:
        return None
    if isinstance(ref, int):
        return ref if 0 <= ref < len(opts) else None
    r = _s(ref)
    for i, o in enumerate(opts):
        if _s(o.get("label")).casefold() == r.casefold():
            return i
    if len(r) == 1 and r.upper() in LETTERS and LETTERS.index(r.upper()) < len(opts):
        return LETTERS.index(r.upper())
    return None


def normalize(d: dict) -> dict:
    """One decision (schema hitl-scorecard/v1) -> card: display order, letters, recommendation."""
    if not isinstance(d, dict):
        raise InputError("decision must be an object")
    opts = [o for o in (d.get("options") or []) if isinstance(o, dict) and _s(o.get("label"))]
    multi = bool(d.get("multi"))
    raw = d.get("recommended")
    refs = raw if isinstance(raw, list) else ([] if raw in (None, "", False) else [raw])
    rec = []
    for r in refs:
        i = _option_index(r, opts)
        if i is not None and i not in rec and _s(opts[i].get("evidence")):   # spec §3
            rec.append(i)
    if not multi:
        rec = rec[:1]
        order = rec + [i for i in range(len(opts)) if i not in rec]
    else:
        order = list(range(len(opts)))
    rev = d.get("reversible")      # legacy card-level door: default of every option
    shown = []
    for k, i in enumerate(order):
        o = opts[i]
        orev = o.get("reversible")
        orev = orev if isinstance(orev, bool) else (rev if isinstance(rev, bool) else None)
        shown.append({"letter": LETTERS[k] if k < len(LETTERS) else "?", "label": _s(o.get("label")),
                      "effect": _s(o.get("effect")), "confidence": _s(o.get("confidence")),
                      "evidence": _s(o.get("evidence")), "recommended": i in rec, "reversible": orev})
    origin = d.get("origin") if isinstance(d.get("origin"), dict) else {}
    origins = [o for o in (d.get("origins") or []) if isinstance(o, dict)] or [origin]
    return {"id": _s(d.get("id")), "title": _s(d.get("title")),
            "origin": {k: _s(origin.get(k)) for k in ("harness", "repo", "session")},
            "extra_origins": max(len(origins) - 1, 0),
            "context": _s(d.get("context")), "ask": _s(d.get("ask")),
            "urgency": URG_ALIAS.get(_s(d.get("urgency")).casefold(), "media"),
            "owner_only": bool(d.get("owner_only")),
            "doors": [o["reversible"] for o in shown],
            "cost_of_delay": _s(d.get("cost_of_delay")), "time_to_decide": _s(d.get("time_to_decide")),
            "multi": multi, "rationale": _s(d.get("rationale")),
            "unblocks": int(d.get("unblocks") or 0), "parked": int(d.get("parked") or 0),
            "options": shown, "rec": [o["letter"] for o in shown if o["recommended"]],
            "rec_requested": bool(refs)}


def urgent(c: dict) -> bool:
    return c["urgency"] == "alta" or c["owner_only"]


def needs_letter(c: dict) -> bool:
    """spec §3: `-` is not accepted on ⏫, 👤 or a card without recommendation."""
    return urgent(c) or not c["rec"]


def _rank(c: dict):
    if c["urgency"] == "alta" and c["owner_only"]:
        group = 0
    elif c["urgency"] == "alta":
        group = 1
    elif c["owner_only"]:
        group = 2
    elif c["parked"] >= 2:
        group = 3            # spec §4: parked decision in its third digest
    else:
        group = 4
    return (group, URG_RANK[c["urgency"]], -c["unblocks"])


def plan(cards: list[dict]):
    """spec §4: ≤3 cards (a 4th only for ⏫/👤), ≤3 parked lines, the rest on ⏭."""
    ordered = sorted(cards, key=_rank)
    n_urgent = sum(1 for c in ordered if urgent(c))
    cap = 4 if n_urgent > 3 else 3
    shown, rest = ordered[:cap], ordered[cap:]
    parkable = [c for c in rest if not urgent(c) and c["parked"] < 2]
    parked = sorted(parkable, key=lambda c: -c["parked"])[:3]
    ids = {id(c) for c in parked}
    nxt = [c for c in rest if id(c) not in ids]
    return shown, parked, nxt


def load_doc(path: str) -> dict:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"{path}: invalid JSON ({e})") from e
    if isinstance(doc, list):
        doc = {"decisions": doc}
    elif isinstance(doc, dict) and "decisions" not in doc and "options" in doc:
        doc = {"decisions": [doc]}
    if not isinstance(doc, dict) or not isinstance(doc.get("decisions"), list):
        raise InputError(f"{path}: expected {{\"decisions\": [...]}}")
    return doc


# ---------------------------------------------------------------- session
def root_session(flag: str | None) -> str | None:
    """Root harness session only (spec §2). A child id (e.g. OMP PI_SESSION_ID in a
    subagent) is never read: pass the root id with --session."""
    return flag or os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CODEX_THREAD_ID") or None


def load_cards(doc: dict) -> list[dict]:
    """Cards for render/ask/parse. A decision with fewer than 2 real options is not a
    decision, and more than 4 do not fit a question: refused, never padded (contrato §6)."""
    cards = [normalize(d) for d in doc["decisions"]]
    for i, c in enumerate(cards, 1):
        if not 2 <= len(c["options"]) <= 4:
            raise InputError(f"{c['id'] or f'#{i}'}: {len(c['options'])} opção(ões) real(is); "
                             "uma decisão exige 2–4 (nenhuma opção é inventada)")
    return cards



# ---------------------------------------------------------------- render
def _origin(c: dict) -> str:
    o = c["origin"]
    parts = [o["harness"], o["repo"], o["session"][-8:] if o["session"] else ""]
    text = " · ".join(p for p in parts if p) or "origem desconhecida"
    return text + (f" (+{c['extra_origins']} sessões)" if c["extra_origins"] else "")


def _title_line(c: dict, n) -> str:
    icon, word, _ = URG[c["urgency"]]
    return f"{n} · {icon} {word}" + (f" · {OWNER}" if c["owner_only"] else "") + f" — {c['title']}"


def _glyph(o: dict) -> str:
    return DOOR_GLYPH.get(o["reversible"], "?")


def _doors(c: dict) -> str:
    """Legend of the doors present on the card's options, glyph + CAPS word (contrato §1);
    the per-option glyph sits beside each option."""
    words = [DOOR[False]] if False in c["doors"] else []
    words += [DOOR[True]] if True in c["doors"] else []
    words += [DOOR_UNKNOWN] if None in c["doors"] else []
    return " · ".join(words)


def _badges(c: dict) -> str:
    bits = [f"\u231b sem resposta: {c['cost_of_delay'] or '?'}"]
    if c["time_to_decide"]:
        bits.append(f"\u23f1 {c['time_to_decide']}")
    if c["multi"]:
        bits.append("\u2611 VÁRIAS")
    return " · ".join(bits)


def _ptr(o: dict) -> str:
    return " · ".join(x for x in (o["confidence"], o["evidence"]) if x)


def card_lines(c: dict, n) -> list[str]:
    """Full layout. No card line starts with a header glyph (🔴🟡🟢✅) after its indentation:
    the attention-contract checker (sinal-check) would read it as a misplaced header.
    So an option line starts with its letter (`A ✅ …`) and the BLUF line with `BLUF:`."""
    out = wrap(_title_line(c, n), "", IND)
    out += wrap(f"origem: {_origin(c)}", IND, IND + "  ")
    out += wrap(f"decisão: {c['ask']}", IND, IND + "  ")
    if c["rec"]:
        why = f" porque {c['rationale']}" if c["rationale"] else ""
        out += wrap(f"BLUF: \u2705 recomendo {'+'.join(c['rec'])}{why}", IND, IND + "  ")
    else:
        out.append(f"{IND}BLUF: {NO_REC}")
    out += wrap(f"contexto: {c['context']}", IND, IND + "  ")
    for o in c["options"]:
        mark = "\u2705 " if o["recommended"] else "   "
        door = DOOR.get(o["reversible"], DOOR_UNKNOWN)
        body = o["label"] + (f" → {o['effect']}" if o["effect"] else "") + f" · {door}" \
            + (f" · {_ptr(o)}" if _ptr(o) else "")
        out += wrap(body, f"{IND}{o['letter']} {mark}", " " * 9)
    out += wrap(_badges(c), IND, IND + "  ")
    return out


def pack(tokens: list[str], indent: str = IND) -> list[str]:
    """Join tokens with ` · ` within 80 columns; a token that does not fit moves to the
    next line, and one longer than a line is word-wrapped. Nothing is ever cut."""
    lines, line = [], None
    for t in tokens:
        cand = f"{line} · {t}" if line else indent + t
        if cols(cand) <= COLS:
            line = cand
            continue
        if line:
            lines.append(line)
        w = wrap(t, indent, indent + "  ")
        lines += w[:-1]
        line = w[-1]
    if line:
        lines.append(line)
    return lines


def _rec_line(c: dict) -> str:
    """Compact L2 (BLUF): `A ✅ <action> — porque <rationale> (<conf> · <pointer>)`. The
    letter comes before ✅ so the line never starts with a header glyph (sinal-check)."""
    rec = [o for o in c["options"] if o["recommended"]]
    if not rec:
        return NO_REC
    head = " + ".join(f"{o['letter']} \u2705 {o['label']} {_glyph(o)}" for o in rec)
    why = f" — porque {c['rationale']}" if c["rationale"] else ""
    ptrs = "; ".join(_ptr(o) for o in rec if _ptr(o))
    return head + why + (f" ({ptrs})" if ptrs else "")


def _risk(c: dict, short: bool = False) -> str:
    """L4: ⌛ cost · ⏱ time to decide · door legend. The 3-line card drops the legend: each
    option already carries its own ↩️/🚪 glyph, and a two-door legend there read as if the
    card were both one-way and reversible."""
    bits = [f"\u231b {c['cost_of_delay'] or '?'}"]
    if c["time_to_decide"]:
        bits.append(f"\u23f1 {c['time_to_decide']}")
    if not short:
        bits.append(_doors(c))
    if c["multi"]:
        bits.append("\u2611 VÁRIAS")
    return " · ".join(b for b in bits if b)


def origin_delta(c: dict, foot: dict) -> str:
    """The card's origin fields that differ from the footer (harness · repo · sessão).
    Never omitted when they differ: it is what tells N sessions apart (contrato §1)."""
    o = c["origin"]
    parts = [v for v, f in ((o["harness"], foot["harness"]), (o["repo"], foot["repo"]),
                            (o["session"][-8:], foot["session"])) if v and v != f]
    if c["extra_origins"]:
        parts.append(f"(+{c['extra_origins']} sessões)")
    return " · ".join(parts)


def compact_lines(c: dict, n, foot: dict, short: bool = False) -> list[str]:
    """Compact card (contrato §1), BLUF/Minto order. 5 lines: L1 title · L2 recommendation +
    rationale + pointer · L3 the other options · L4 ⌛ cost · ↩️/🚪 · L5 origin (only when it
    differs from the footer). `short` = 3 lines: L3 carries options, ⌛, door and origin."""
    rest = [o for o in c["options"] if not o["recommended"]] if c["rec"] else c["options"]
    opts = [f"{o['letter']} {o['label']} {_glyph(o)}" for o in rest]
    delta = origin_delta(c, foot)
    out = wrap(_title_line(c, n), "", IND) + wrap(_rec_line(c), IND, IND + "  ")
    if short:
        return out + pack(opts + [_risk(c, short=True)] + ([delta] if delta else []))
    out += pack(opts) + pack([_risk(c)])
    return out + (pack([delta]) if delta else [])




def _hint(need: list[str], total: int) -> str:
    if not need:
        return "(omitido = pendente · - = aceitar A)"
    names = need[0] if len(need) == 1 else ", ".join(need[:-1]) + " e " + need[-1]
    verb = "exige" if len(need) == 1 else "exigem"
    tail = " · - = aceitar A nos demais" if len(need) < total else ""
    return f"({names} {verb} letra · omitido = pendente{tail})"


def header_lines(shown, parked, nxt, code, now) -> list[str]:
    head = fuse._digest_head(code, now) if code else \
        "══ 🟠 HITL DIGEST · sem código (sessão raiz desconhecida) ══"
    lines = [head, f"{len(shown)} + {len(parked)} estac." + (f" + {len(nxt)} próximo digest" if nxt else "")]
    if code and shown:
        # A card without a recommendation offers no letter: `?` is not an answer token the
        # parser accepts, so a pasted Responda line cannot decide it by copy (contrato §10).
        toks = " ".join(f"{i}:{'+'.join(c['rec']) or '?'}" for i, c in enumerate(shown, 1))
        lines.append(f"Responda: {code} {toks}")
        lines.append(_hint([str(i) for i, c in enumerate(shown, 1) if needs_letter(c)], len(shown)))
    elif shown:
        lines.append("(informativo, sem número respondível: use o AskUserQuestion)")
    return lines


def render_text(doc: dict, *, now: int, session: str | None, layout: str = "full",
                harness: str | None = None, repo: str | None = None) -> str:
    return render_with_cards(doc, now=now, session=session, layout=layout,
                             harness=harness, repo=repo)[0]


def render_with_cards(doc: dict, *, now: int, session: str | None, layout: str = "full",
                      harness: str | None = None, repo: str | None = None) -> tuple[str, list[dict]]:
    """Text plus the cards it actually made answerable (after the compact fit). The
    answer manifest is built from these cards, never re-planned at parse time."""
    shown, parked, nxt = plan(load_cards(doc))
    code = fuse._digest_code(now, session)
    foot = {"harness": harness or _s(doc.get("harness")), "repo": repo or _s(doc.get("repo")),
            "session": session[-8:] if session else ""}

    def frame(shown, nxt, parked):
        head = header_lines(shown, parked, nxt, code, now)
        tail = []
        for c in parked:
            act = f"{c['title']}: {c['options'][0]['label']}" if c["rec"] else c["ask"]
            tail += wrap(f"⏸ {min(c['parked'] + 1, 2)}/2 estacionada (informativa): {act}"
                         f" · {c['cost_of_delay'] or '?'}", "", "  ")
        if nxt:
            tail.append(fuse._overflow_line([{"sev": URG_TO_SEV[c["urgency"]], "id": c["id"] or c["title"]}
                                             for c in nxt]))
        tail += wrap(f"harness: {foot['harness'] or '?'} · repo: {foot['repo'] or '?'} · "
                     f"sessão: {foot['session'] or '?'}", "", "  ")
        return head, tail

    nums = lambda shown: [i if code else "•" for i in range(1, len(shown) + 1)]
    if layout == "full":
        head, tail = frame(shown, nxt, parked)
        body = [card_lines(c, k) for c, k in zip(shown, nums(shown))]
        return "\n".join(head + [l for card in body for l in card] + tail) + "\n", shown
    # contrato §1: 5-line cards while the WRAPPED output fits the attention contract (15
    # lines); otherwise the lowest-priority card drops to 3 lines first, then the next one
    # up. If all-3-line still does not fit, informative ⏸ lines move to `⏭ próximo digest`
    # first (they are never answerable now, so a ⏫/👤 card is never hidden to keep them);
    # only then the lowest-priority card moves to ⏭, until it fits. A single card that
    # still does not fit is an error: shorten it at the source (never cut, never exceed).
    while True:
        head, tail = frame(shown, nxt, parked)
        ks = nums(shown)
        body = [compact_lines(c, k, foot) for c, k in zip(shown, ks)]
        for j in reversed(range(len(shown))):
            if len(head) + len(tail) + sum(map(len, body)) <= BODY_MAX:
                break
            body[j] = compact_lines(shown[j], ks[j], foot, short=True)
        if len(head) + len(tail) + sum(map(len, body)) <= BODY_MAX:
            return "\n".join(head + [l for card in body for l in card] + tail) + "\n", shown
        if parked:
            nxt = list(nxt) + [parked[-1]]
            parked = parked[:-1]
            continue
        if len(shown) <= 1:
            raise ValueError(f"render-compact: um card sozinho passa de {BODY_MAX} linhas; "
                             "encurte title/rationale/cost_of_delay/rótulos na fonte")
        nxt = [shown[-1]] + list(nxt)
        shown = shown[:-1]


def ansi(text: str) -> str:
    """Color only adds to icon + CAPS word (spec §8); NO_COLOR (no-color.org) disables it."""
    if os.environ.get("NO_COLOR"):
        return text
    paint = [(f"{URG[k][0]} {URG[k][1]}", URG[k][2]) for k in URG]
    paint += [(OWNER, "1;35"), (DOOR[False], "1;31"), (DOOR[True], "32"), ("\u2705", "32"), ("\u231b", "33")]
    for token, code in paint:
        text = text.replace(token, f"\x1b[{code}m{token}\x1b[0m")
    return text


# ---------------------------------------------------------------- ask (panel)
def _question(c: dict, n: int) -> str:
    """AskUserQuestion keys `answers` by the question text, so the text starts with the
    card number and id (`<n> · <id> — `): two decisions with the same ask never collide."""
    ask = c["ask"].rstrip(" ?") + "?"
    ident = f"{n} · {c['id']} — " if c["id"] else f"{n} — "
    return (f"{ident}{ask} Contexto: {c['context']} Origem: {_origin(c)}. "
            f"Sem resposta: {c['cost_of_delay'] or '?'}.")


def auq_question(c: dict, n: int) -> dict:
    raw = []
    for o in c["options"]:
        door = {True: "Reversível.", False: "Sem volta."}.get(o["reversible"], "Reversibilidade não informada.")
        desc = o["effect"] + ("." if o["effect"] and o["effect"][-1] not in ".!?" else "")
        desc = f"{desc} {door}".strip()
        single_rec = o["recommended"] and not c["multi"]
        if not single_rec and _ptr(o):
            desc = f"{desc} Evidência: {_ptr(o)}.".strip()
        raw.append({"label": o["label"], "description": desc, "recommended": single_rec,
                    "evidence": o["evidence"], "confidence": o["confidence"]})
    opts, _has_rec, _src = fuse._card_options({"idade": "?"}, {"options": raw})   # reused builder
    if c["multi"]:
        # raw carries no `recommended` in a multi card, so `_card_options` keeps the source
        # order and opts[k] is c["options"][k]. The marker goes on after clipping, and the
        # labels are deduplicated with the marker kept: each pick keeps its identity.
        seen: set[str] = set()
        for o, src in zip(opts, c["options"]):
            mark = REC if src["recommended"] else ""
            label, k = fuse._clip(src["label"], fuse.AUQ_LABEL_MAX - len(mark)) + mark, 1
            while label in seen:
                k += 1
                suffix = f" ({k})"
                label = fuse._clip(src["label"], fuse.AUQ_LABEL_MAX - len(mark) - len(suffix)) + suffix + mark
            o["label"] = label
            seen.add(label)
    header = f"{n} {URG[c['urgency']][1]}" + (" \U0001f464" if c["owner_only"] else "")
    return {"question": _question(c, n), "header": header[: fuse.AUQ_HEADER_MAX],
            "options": opts, "multiSelect": c["multi"]}


def ask_claude(doc: dict, *, now: int, session: str | None) -> dict:
    shown, parked, nxt = plan(load_cards(doc))
    code = fuse._digest_code(now, session)
    record = [f"· {i} {URG[c['urgency']][0]} {c['title']} — aberta no AskUserQuestion"
              for i, c in enumerate(shown, 1)]
    return {"schema": "hitl-scorecard/ask-claude/v1", "code": code, "no_preselect": True,
            "timeout_is": "pending",
            "preamble": [l for x in header_lines(shown, parked, nxt, code, now)[:2] + record
                         for l in wrap(x, "", "  ")],
            "ask_user_question": {"questions": [auq_question(c, i) for i, c in enumerate(shown, 1)]}}


def ask_omp(doc: dict, *, now: int, session: str | None) -> str:
    """One HTML form for the OMP `ask` tool. The tool submits the CURRENT values on
    timeout, so nothing is checked/selected/prefilled and an explicit, unchecked
    confirmation box gates every answer (no box ⇒ everything pending)."""
    e = html.escape
    shown, parked, nxt = plan(load_cards(doc))
    code = fuse._digest_code(now, session) or "sem código"
    out = ["<form>", f"<h3>🟠 HITL DIGEST · {e(code)}</h3>",
           "<p>Nenhuma opção vem marcada. Tempo esgotado, cancelamento ou envio sem a caixa "
           "de confirmação = <strong>pendente</strong> (nunca consentimento).</p>"]
    for i, c in enumerate(shown, 1):
        kind = "checkbox" if c["multi"] else "radio"
        rec = (f"✅ recomendo {'+'.join(c['rec'])}" + (f" porque {c['rationale']}" if c["rationale"] else "")
               if c["rec"] else NO_REC)
        out += [f"<fieldset>", f"<legend>{e(_title_line(c, i))}</legend>", "<table>",
                f"<tr><th>Origem</th><td>{e(_origin(c))}</td></tr>",
                f"<tr><th>Contexto</th><td>{e(c['context'])}</td></tr>",
                f"<tr><th>Decisão</th><td>{e(c['ask'])}</td></tr>",
                f"<tr><th>Recomendação</th><td>{e(rec)}</td></tr>",
                f"<tr><th>Risco</th><td>{e(_badges(c))}</td></tr>", "</table>",
                f"<p>{'Marque uma ou mais' if c['multi'] else 'Escolha uma'} (vazio = pendente):</p>"]
        for o in c["options"]:
            label = ("✅ " if o["recommended"] else "") + f"{o['letter']} — {o['label']}" + (REC if o["recommended"] else "")
            detail = " · ".join(x for x in (o["effect"], DOOR.get(o["reversible"], DOOR_UNKNOWN), _ptr(o)) if x)
            out.append(f'<label><input type="{kind}" name="d{i}" value="{o["letter"]}"> {e(label)}'
                       + (f" <small>{e(detail)}</small>" if detail else "") + "</label><br>")
        out.append("</fieldset>")
    out += ["<fieldset>", "<legend>Confirmação</legend>",
            '<label><input type="checkbox" name="confirm" value="sim"> Confirmo as escolhas acima '
            "(sem esta marca nada é executado)</label>", "</fieldset>", "</form>"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- parse
def _item(n, c, status, letters=(), note=""):
    labels = {o["letter"]: o["label"] for o in c["options"]}
    return {"n": n, "id": c["id"], "title": c["title"], "status": status, "letters": list(letters),
            "labels": [labels[x] for x in letters if x in labels], "note": note}


def _fechado(code: str | None, items: list[dict]) -> str:
    toks = " ".join(f"{i['n']}={'+'.join(i['letters']) if i['status'] == 'decided' else 'pendente'}"
                    for i in items)
    return f"{code or 'AskUserQuestion'} fechado: {toks}"


def parse_text(cards, answer: str, code: str | None, closed=(), resolved=None) -> dict:
    resolved = resolved or {}
    if not code:
        return {"status": "rejected", "reason": "digest sem código: sem resposta por texto (spec §2)"}
    found = {m.group(0).upper() for m in CODE_RE.finditer(answer)}
    if not found:
        return {"status": "rejected", "reason": f"sem código; o digest atual é {code}"}
    if found != {code.upper()}:
        return {"status": "rejected", "reason": f"código de outro digest; o atual é {code}"}
    if code.upper() in {c.upper() for c in closed}:
        return {"status": "rejected", "reason": f"{code} já está fechado"}
    seen: dict[int, list[str]] = {}
    for tok in re.split(r"[\s,]+", answer.strip()):
        m = TOKEN_RE.fullmatch(tok)
        if m:
            seen.setdefault(int(m.group(2)), []).append(m.group(3).upper())
    items, extra = [], []
    for n in sorted(seen):
        if not 1 <= n <= len(cards):
            extra.append({"n": n, "status": "rejected", "note": "não é card deste digest; nada executado"})
    if not seen:
        items = [_item(i, c, "pending", note="texto livre: nada decidido") for i, c in enumerate(cards, 1)]
        return {"status": "ok", "code": code, "items": items, "fechado": _fechado(code, items)}
    for i, c in enumerate(cards, 1):
        vals = seen.get(i)
        valid = {o["letter"] for o in c["options"]}
        if i in resolved:
            items.append(_item(i, c, "rejected", note=f"já resolvido: {resolved[i]}") if vals
                         else _item(i, c, "decided", resolved[i].split("+"), "resolvido antes"))
        elif not vals:
            items.append(_item(i, c, "pending", note="omitido = pendente"))
        elif len(vals) > 1:
            items.append(_item(i, c, "pending", note="item repetido (ambíguo); volta no próximo digest"))
        elif vals[0] == "-":
            if needs_letter(c):
                items.append(_item(i, c, "pending", note="'-' não vale em ⏫/👤/sem recomendação; exige letra"))
            else:
                items.append(_item(i, c, "decided", c["rec"], "'-' = aceitar a recomendação"))
        else:
            letters = vals[0].split("+")
            ok = (all(x in valid for x in letters) and len(set(letters)) == len(letters)
                  and (c["multi"] or len(letters) == 1))
            items.append(_item(i, c, "decided", letters) if ok else
                         _item(i, c, "pending", note=f"letra inválida '{vals[0]}'; volta no próximo digest"))
    return {"status": "ok", "code": code, "items": items, "rejected_tokens": extra,
            "fechado": _fechado(code, items)}


def _split_multi(answer: str, labels: list[str]) -> list[int] | None:
    picks = []
    for part in [p.strip() for p in answer.split(",") if p.strip()]:
        if part not in labels:
            return None
        picks.append(labels.index(part))
    return picks or None


def parse_claude(cards, result: dict, code: str | None) -> dict:
    """AskUserQuestion result (Claude Code 2.1.331 schema): answers keyed by question
    text; `afkTimeoutMs` = the dialog auto-resolved while the person was away ⇒ expired."""
    afk = result.get("afkTimeoutMs")
    answers = result.get("answers") if isinstance(result.get("answers"), dict) else {}
    notes = result.get("annotations") if isinstance(result.get("annotations"), dict) else {}
    items = []
    for i, c in enumerate(cards, 1):
        q = auq_question(c, i)
        labels = [o["label"] for o in q["options"]]
        ann = notes.get(q["question"]) if isinstance(notes.get(q["question"]), dict) else {}
        ans = answers.get(q["question"])
        if afk:
            items.append(_item(i, c, "expired", note=f"auto-resolvido por inatividade ({afk} ms): pendente"))
        elif ann.get("unanswered"):
            items.append(_item(i, c, "pending", note=f"não respondida ({ann['unanswered']})"))
        elif not isinstance(ans, str) or not ans.strip():
            items.append(_item(i, c, "pending", note="sem resposta"))
        else:
            idx = _split_multi(ans, labels) if c["multi"] else ([labels.index(ans)] if ans in labels else None)
            if idx is None:
                items.append(_item(i, c, "pending", note="texto livre (Other): nada executado; o agente lê e pergunta de novo"))
            else:
                items.append(_item(i, c, "decided", [LETTERS[k] for k in idx]))
    return {"status": "ok", "code": code, "items": items, "fechado": _fechado(code, items)}


def parse_omp(cards, data: dict, code: str | None) -> dict:
    vals = data
    for key in ("values", "answers", "fields", "form", "data", "result"):
        if isinstance(vals, dict) and isinstance(vals.get(key), dict):
            vals = vals[key]
            break
    expired = any(isinstance(d, dict) and d.get(k) for d in (data, vals) for k in EXPIRED_FLAGS)
    conf = vals.get("confirm") if isinstance(vals, dict) else None
    conf = conf if isinstance(conf, list) else [conf]
    confirmed = any(_s(x).casefold() in CONFIRM_YES for x in conf if x is not None)
    items = []
    for i, c in enumerate(cards, 1):
        if expired:
            items.append(_item(i, c, "expired", note="tempo esgotado/cancelado: pendente"))
            continue
        if not confirmed:
            items.append(_item(i, c, "pending", note="sem a caixa de confirmação: pendente"))
            continue
        v = vals.get(f"d{i}")
        letters = [_s(x).upper() for x in (v if isinstance(v, list) else [v]) if _s(x)]
        valid = {o["letter"] for o in c["options"]}
        if not letters:
            items.append(_item(i, c, "pending", note="vazio = pendente"))
        elif all(x in valid for x in letters) and (c["multi"] or len(letters) == 1):
            items.append(_item(i, c, "decided", letters))
        else:
            items.append(_item(i, c, "pending", note="valor inválido; volta no próximo digest"))
    return {"status": "ok", "code": code, "items": items, "fechado": _fechado(code, items)}


# ---------------------------------------------------------------- aggregate
NEEDS_RE = re.compile(r"NEEDS-OPERATOR:\s*(.+)$")


def _origin_from(text: str) -> dict:
    parts = [p.strip() for p in re.split(r"\s*[·|]\s*", text or "") if p.strip()]
    parts += [""] * (3 - len(parts))
    return {"harness": parts[0], "repo": parts[1], "session": parts[2]}


def needs_line_to_decision(line: str, default_origin: dict) -> dict | None:
    m = NEEDS_RE.search(line)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(";")]
    kv = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip().lower()] = v.strip()
    text = parts[0]
    rec = kv.get("rec", "")
    opts = [{"label": rec, "confidence": kv.get("confidence", ""), "evidence": kv.get("evidence", "")}] if rec else []
    opts += [{"label": a.strip()} for a in kv.get("alt", "").split("|") if a.strip()]
    origin = _origin_from(kv["origin"]) if kv.get("origin") else dict(default_origin)
    for k in ("harness", "repo", "session"):
        origin[k] = kv.get(k, origin.get(k, ""))
    return {"id": kv.get("id", ""), "title": " ".join(text.split()[:6]), "ask": text,
            "context": kv.get("context", ""), "origin": origin,
            "urgency": kv.get("urgency", "media"),
            "owner_only": kv.get("owner", "").casefold() in CONFIRM_YES,
            "reversible": {"sim": True, "yes": True, "true": True, "nao": False, "não": False,
                           "no": False, "false": False}.get(kv.get("reversible", "").casefold()),
            "cost_of_delay": kv.get("cost-of-not-deciding", ""), "time_to_decide": kv.get("ttd", ""),
            "unblocks": int(kv.get("unblocks", "0") or 0) if kv.get("unblocks", "0").isdigit() else 0,
            "options": opts, "recommended": rec or None}


def _key(d: dict) -> tuple[str, str]:
    """Dedupe key (contrato §6): (repo, id) when the decision carries an explicit id;
    otherwise (repo, normalized ask), the legacy path for bare NEEDS-OPERATOR lines. Two
    distinct ids with the same ask in one repo stay two decisions; the same ask in two repos
    is two decisions; the same ask from two sessions of one repo merges (+N sessões). The
    session stands in for the repo only when the repo is unknown (empty or the `?`
    placeholder), so sources of unknown repos never merge across sessions."""
    o = d.get("origin") if isinstance(d.get("origin"), dict) else {}
    repo = _s(o.get("repo")).casefold()
    where = repo if repo not in ("", "?") else f"session:{_s(o.get('session'))}"
    ident = _s(d.get("id")).strip()
    if ident:
        return where, f"id:{ident.casefold()}"
    return where, "ask:" + re.sub(r"[^\w]+", " ", _s(d.get("ask") or d.get("title")).casefold()).strip()


def aggregate(sources: list[tuple[str, str]], default_origin: dict) -> dict:
    """sources: (name, text). JSON documents and NEEDS-OPERATOR lines; dedupe; order.
    A source that is not valid JSON is listed in `rejected` with its name; the others go on."""
    found: list[dict] = []
    rejected: list[dict] = []
    for name, text in sources:
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                doc = json.loads(stripped)
            except json.JSONDecodeError as e:
                rejected.append({"source": name, "reason": f"JSON inválido: {e}"})
                continue
            doc = {"decisions": doc} if isinstance(doc, list) else doc
            found += [d for d in doc.get("decisions", []) if isinstance(d, dict)]
            continue
        origin = dict(default_origin) if any(default_origin.values()) else _origin_from(f"?·?·{Path(name).stem}")
        found += [d for d in (needs_line_to_decision(l, origin) for l in text.splitlines()) if d]
    merged: dict[tuple[str, str], dict] = {}
    for d in found:
        k = _key(d)
        if k not in merged:
            merged[k] = dict(d, origins=[d.get("origin") or {}])
            continue
        m = merged[k]
        m["origins"].append(d.get("origin") or {})
        a, b = URG_ALIAS.get(_s(m.get("urgency")).casefold(), "media"), URG_ALIAS.get(_s(d.get("urgency")).casefold(), "media")
        m["urgency"] = min((a, b), key=URG_RANK.get)
        m["owner_only"] = bool(m.get("owner_only")) or bool(d.get("owner_only"))
        m["unblocks"] = int(m.get("unblocks") or 0) + int(d.get("unblocks") or 0)
    # contrato §6: one real option is not a decision. Never padded with an invented option
    # (a "Manter pendente" filler became a phantom letter B on parse); listed as rejected.
    decisions = []
    for d in merged.values():
        n = len([o for o in (d.get("options") or []) if isinstance(o, dict) and _s(o.get("label"))])
        if 2 <= n <= 4:
            decisions.append(d)
        else:
            rejected.append({"ask": _s(d.get("ask")), "origin": d.get("origin") or {},
                             "reason": f"{n} opção(ões) real(is); uma decisão exige 2–4 (alt=…)"})
    cards = [normalize(d) for d in decisions]
    shown, parked, nxt = plan(cards)
    pos = {id(c): i for i, c in enumerate(cards)}
    order = [pos[id(c)] for c in shown + parked + nxt]
    return {"schema": SCHEMA, "decisions": [decisions[i] for i in order],
            "queue": {"cards": [cards[pos[id(c)]]["title"] for c in shown],
                      "parked": [c["title"] for c in parked], "next": [c["title"] for c in nxt]},
            "deduped": len(found) - len(merged), "rejected": rejected}


# ---------------------------------------------------------------- lint
def lint_text(text: str, name: str = "text") -> list[str]:
    errs = [f"{name}:{n}: {cols(l)} colunas > {COLS}" for n, l in enumerate(text.splitlines(), 1) if cols(l) > COLS]
    m = re.search(r"^Responda: \S+ (.*)$", text, re.M)
    if m and re.search(r"(^|\s)\d+:-(\s|$)", m.group(1)):
        errs.append(f"{name}: a linha Responda oferece '-' (proibido em ⏫/👤)")
    return errs


def lint_auq(payload: dict, name: str = "auq") -> list[str]:
    errs = []
    qs = ((payload.get("ask_user_question") or payload) or {}).get("questions")
    if not isinstance(qs, list) or not 1 <= len(qs) <= 4:
        return [f"{name}: AskUserQuestion exige 1–4 perguntas"]
    for n, q in enumerate(qs, 1):
        opts = q.get("options") or []
        labels = [o.get("label", "") for o in opts]
        if not 2 <= len(opts) <= 4:
            errs.append(f"{name} q{n}: 2–4 opções (tem {len(opts)})")
        if len(set(labels)) != len(labels):
            errs.append(f"{name} q{n}: rótulos repetidos")
        if len(q.get("header", "")) > fuse.AUQ_HEADER_MAX:
            errs.append(f"{name} q{n}: header > {fuse.AUQ_HEADER_MAX} caracteres")
        if not isinstance(q.get("multiSelect"), bool):
            errs.append(f"{name} q{n}: multiSelect deve ser booleano")
        if q.get("multiSelect") and any("," in x for x in labels):
            errs.append(f"{name} q{n}: vírgula em rótulo multi (a resposta vem separada por vírgula)")
    return errs


def lint_html(text: str, name: str = "html") -> list[str]:
    errs = []
    if re.search(r"\b(checked|selected)\b", text, re.I):
        errs.append(f"{name}: opção pré-selecionada (checked/selected) — proibido")
    if re.search(r"<input\b(?=[^>]*\btype=\"?(text|number|hidden|email|search)\b)(?=[^>]*\bvalue=)", text, re.I):
        errs.append(f"{name}: campo com value pré-preenchido — proibido")
    if re.search(r"<textarea\b[^>]*>\s*\S", text, re.I):
        errs.append(f"{name}: textarea pré-preenchida — proibido")
    if 'name="confirm"' not in text:
        errs.append(f"{name}: falta a caixa de confirmação explícita")
    return errs


def lint_doc(doc: dict, *, now: int, session: str | None) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    decisions = doc.get("decisions") or []
    if not decisions:
        errs.append("decisions: lista vazia")
    for i, d in enumerate(decisions, 1):
        tag = _s(d.get("id")) or f"#{i}"
        title = _s(d.get("title"))
        if not title:
            errs.append(f"{tag}: falta title")
        elif len(title.split()) > 6:
            warns.append(f"{tag}: title com mais de 6 palavras")
        for k in ("context", "ask", "cost_of_delay"):
            if not _s(d.get(k)):
                errs.append(f"{tag}: falta {k}")
            elif "\n" in str(d.get(k)):
                errs.append(f"{tag}: {k} deve ter 1 linha")
        if _s(d.get("urgency")).casefold() not in URG_ALIAS:
            errs.append(f"{tag}: urgency inválida (alta|media|baixa)")
        origin = d.get("origin") if isinstance(d.get("origin"), dict) else {}
        miss = [k for k in ("harness", "repo", "session") if not _s(origin.get(k))]
        if miss:
            errs.append(f"{tag}: origin sem {', '.join(miss)}")
        opts = [o for o in (d.get("options") or []) if isinstance(o, dict) and _s(o.get("label"))]
        labels = [_s(o["label"]).casefold() for o in opts]
        if not 2 <= len(opts) <= 4:
            errs.append(f"{tag}: 2–4 opções (tem {len(opts)})")
        if len(set(labels)) != len(labels):
            errs.append(f"{tag}: rótulos repetidos")
        if d.get("multi") and any("," in x for x in labels):
            errs.append(f"{tag}: vírgula em rótulo de multi-seleção")
        rec = d.get("recommended")
        refs = rec if isinstance(rec, list) else ([] if rec in (None, "", False) else [rec])
        if not d.get("multi") and len(refs) > 1:
            errs.append(f"{tag}: escolha única com mais de uma recomendação")
        card_rev = d.get("reversible")
        for r in refs:
            j = _option_index(r, opts)
            if j is None:
                errs.append(f"{tag}: recommended '{r}' não é uma opção")
                continue
            if not _s(opts[j].get("evidence")):
                warns.append(f"{tag}: recomendação sem ponteiro de evidência → card sem ✅")
            orev = opts[j].get("reversible", card_rev)
            if orev is False and _s(opts[j].get("confidence")).casefold() not in HIGH_CONF:
                errs.append(f"{tag}: recomendada '{_s(opts[j].get('label'))}' é 🚪 SEM VOLTA com confiança "
                            f"'{_s(opts[j].get('confidence')) or '?'}': exija confiança alta ou "
                            "deixe o card sem recomendação")
        if refs and not _s(d.get("rationale")):
            errs.append(f"{tag}: recomendação sem rationale (A ✅ … — porque <rationale>)")
        unknown = [_s(o.get("label")) for o in opts
                   if not isinstance(o.get("reversible", card_rev), bool)]
        if unknown:
            warns.append(f"{tag}: reversible não informado (↩️/🚪) em: {', '.join(unknown)}")
        for o in opts:
            if not _s(o.get("effect")):
                warns.append(f"{tag}: opção '{_s(o.get('label'))}' sem effect (o que acontece se escolhida)")
    if errs:
        return errs, warns
    warns += budget_warnings(doc, session)
    shown, parked, nxt = plan(load_cards(doc))
    if len(shown) > 4:
        errs.append("mais de 4 cards")
    for layout in ("full", "compact"):
        text = render_text(doc, now=now, session=session, layout=layout)
        errs += lint_text(text, f"render-{layout}")
        if layout == "compact" and len(shown) <= 3 and len([l for l in text.splitlines() if l.strip()]) > BODY_MAX:
            errs.append(f"render-compact: mais de {BODY_MAX} linhas (Contrato de Atenção)")
    errs += lint_auq(ask_claude(doc, now=now, session=session), "ask-claude")
    errs += lint_html(ask_omp(doc, now=now, session=session), "ask-omp")
    return errs, warns


def budget_warnings(doc: dict, session: str | None) -> list[str]:
    """Source budgets of the compact card (contrato §1): every field fits its line in 80
    columns. Nothing is truncated: a field over budget wraps and the lint asks to shorten
    it at the source."""
    warns = []
    foot = {"harness": _s(doc.get("harness")), "repo": _s(doc.get("repo")),
            "session": session[-8:] if session else ""}
    for c in load_cards(doc):
        tag = c["id"] or c["title"]
        if cols(_title_line(c, 9)) > COLS:
            warns.append(f"{tag}: title passa do orçamento da L1 ({cols(_title_line(c, 9))} > {COLS} colunas)")
        if c["rec"] and cols(IND + _rec_line(c)) > COLS:
            warns.append(f"{tag}: rótulo + rationale + ponteiro passam do orçamento da L2 "
                         f"({cols(IND + _rec_line(c))} > {COLS} colunas)")
        rest = [o for o in c["options"] if not o["recommended"]] if c["rec"] else c["options"]
        if len(pack([f"{o['letter']} {o['label']}" for o in rest])) > 1:
            warns.append(f"{tag}: rótulos das demais opções passam de 1 linha (L3)")
        if cols(IND + _risk(c)) > COLS:
            warns.append(f"{tag}: cost_of_delay passa do orçamento da L4 ({cols(IND + _risk(c))} > {COLS} colunas)")
        delta = origin_delta(c, foot)
        if delta and cols(IND + delta) > COLS:
            warns.append(f"{tag}: origem passa de 1 linha (L5)")
        if len(compact_lines(c, 9, foot, short=True)) > 3:
            warns.append(f"{tag}: card de 3 linhas não cabe (L3 = demais opções · ⌛ · porta · origem); "
                         "encurte cost_of_delay ou os rótulos")
        for o in c["options"]:
            if cols(o["effect"]) > EFFECT_MAX:
                warns.append(f"{tag} {o['letter']}: effect passa do orçamento ({cols(o['effect'])} > {EFFECT_MAX} colunas)")
    return warns


# ---------------------------------------------------------------- CLI
def _read(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hitl-scorecard", description=__doc__.split("\n")[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--session", help="ROOT harness session id (default: CLAUDE_CODE_SESSION_ID, CODEX_THREAD_ID)")
    common.add_argument("--now", type=int, default=None, help="epoch seconds for the digest code (default: clock)")
    common.add_argument("--harness")
    common.add_argument("--repo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render", parents=[common])
    p.add_argument("decisions")
    p.add_argument("--format", choices=["text", "ansi", "markdown"], default="text")
    p.add_argument("--layout", choices=["full", "compact"], default="full")
    p = sub.add_parser("ask", parents=[common])
    p.add_argument("decisions")
    p.add_argument("--target", choices=["claude", "omp"], required=True)
    p = sub.add_parser("parse", parents=[common])
    p.add_argument("decisions")
    p.add_argument("--source", choices=["text", "claude", "omp"], required=True)
    p.add_argument("--answer", help="answer line (text) or JSON (claude/omp)")
    p.add_argument("--input", help="file with the answer (- = stdin)")
    p.add_argument("--code", help="code of the digest shown (required for text answers)")
    p.add_argument("--closed", action="append", default=[], help="code already closed (repeatable)")
    p.add_argument("--resolved", action="append", default=[], help="n=LETTER already resolved in this digest")
    p = sub.add_parser("aggregate", parents=[common])
    p.add_argument("inputs", nargs="+", help="decision JSON files and/or files with NEEDS-OPERATOR lines (- = stdin)")
    p.add_argument("--origin", default="", help="harness·repo·session for bare NEEDS-OPERATOR lines")
    p = sub.add_parser("lint", parents=[common])
    p.add_argument("decisions", nargs="?")
    p.add_argument("--text")
    p.add_argument("--auq")
    p.add_argument("--html")
    a = ap.parse_args(argv)
    now = a.now if a.now is not None else int(time.time())
    session = root_session(a.session)
    try:
        if a.cmd == "render":
            out = render_text(load_doc(a.decisions), now=now, session=session, layout=a.layout,
                              harness=a.harness, repo=a.repo)
            out = ansi(out) if a.format == "ansi" else f"```text\n{out}```\n" if a.format == "markdown" else out
            sys.stdout.write(out)
        elif a.cmd == "ask":
            doc = load_doc(a.decisions)
            if a.target == "claude":
                sys.stdout.write(json.dumps(ask_claude(doc, now=now, session=session), ensure_ascii=False, indent=2) + "\n")
            else:
                sys.stdout.write(ask_omp(doc, now=now, session=session))
        elif a.cmd == "parse":
            doc = load_doc(a.decisions)
            raw = a.answer if a.answer is not None else _read(a.input or "-")
            if a.source == "text":
                # A text answer refers to the cards the text digest made answerable; the
                # compact fit may have moved some to ⏭, and those are not answerable now.
                _, shown = render_with_cards(doc, now=now, session=session, layout="compact",
                                             harness=a.harness, repo=a.repo)
                resolved = dict((int(k), v.upper()) for k, v in (r.split("=", 1) for r in a.resolved))
                res = parse_text(shown, raw, a.code, a.closed, resolved)
            else:
                shown, _, _ = plan(load_cards(doc))
                data = json.loads(raw)
                res = (parse_claude if a.source == "claude" else parse_omp)(shown, data, a.code)
            sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
            return 0 if res["status"] == "ok" else 1
        elif a.cmd == "aggregate":
            srcs = [(x, _read(x)) for x in a.inputs]
            sys.stdout.write(json.dumps(aggregate(srcs, _origin_from(a.origin)), ensure_ascii=False, indent=2) + "\n")
        elif a.cmd == "lint":
            errs, warns = [], []
            if a.decisions:
                e2, w2 = lint_doc(load_doc(a.decisions), now=now, session=session)
                errs, warns = errs + e2, warns + w2
            if a.text:
                errs += lint_text(_read(a.text), a.text)
            if a.auq:
                errs += lint_auq(json.loads(_read(a.auq)), a.auq)
            if a.html:
                errs += lint_html(_read(a.html), a.html)
            for w in warns:
                print(f"AVISO {w}", file=sys.stderr)
            for e in errs:
                print(f"ERRO {e}", file=sys.stderr)
            print(f"lint: {len(errs)} erro(s), {len(warns)} aviso(s)")
            return 1 if errs else 0
    except (InputError, json.JSONDecodeError, OSError, ValueError) as e:
        print(f"hitl-scorecard: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
