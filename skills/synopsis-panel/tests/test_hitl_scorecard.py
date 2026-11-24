"""Deterministic tests for bin/hitl-scorecard.py (hitl-digest spec §8 scorecard + panel).

Runs under `python3 -m unittest` and under pytest. Stdlib only.
"""
import copy
import datetime as dt
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "bin" / "hitl-scorecard.py"
_spec = importlib.util.spec_from_file_location("hitl_scorecard_under_test", _SCRIPT)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

SESSION = "01a20e56-ecbe-7673-8116-76600e63ce53"
NOW = 1795469400                      # fixed instant (UTC) for deterministic codes
CODE = "K" + dt.datetime.fromtimestamp(NOW, tz=dt.timezone.utc).strftime("%y%m%d-%H%M") + "-" + SESSION[-8:]
FUSE = _SCRIPT.parent / "synopsis-fuse.py"


def decision(i, urgency="baixa", owner=False, rec="Manter", evidence="spec.md:1", multi=False, n_opts=2):
    labels = ["Manter", "Mudar", "Adiar", "Arquivar", "Dividir"][:n_opts]
    return {
        "id": f"D{i}", "title": f"Decisão número {i}",
        "origin": {"harness": "OMP", "repo": "org/repo", "session": SESSION},
        "context": f"contexto da decisão {i}", "ask": f"Qual caminho para o item {i}",
        "urgency": urgency, "owner_only": owner, "reversible": True,
        "cost_of_delay": "o item fica parado", "time_to_decide": "2 min", "multi": multi,
        "options": [{"label": l, "effect": f"efeito {l}", "confidence": "média",
                     "evidence": evidence if l in (rec if isinstance(rec, list) else [rec]) else ""}
                    for l in labels],
        "recommended": rec, "rationale": "é o mais barato",
    }


def doc(*ds):
    return {"decisions": list(ds), "harness": "OMP", "repo": "org/repo"}


def cards(d):
    shown, _, _ = sc.plan([sc.normalize(x) for x in d["decisions"]])
    return shown


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.doc = doc(decision(1, "alta", True), decision(2, "media", True), decision(3))

    def test_code_is_utc_plus_root_s8(self):
        out = sc.render_text(self.doc, now=NOW, session=SESSION)
        self.assertIn(f"HITL DIGEST · {CODE} (", out.splitlines()[0])

    def test_compact_fits_attention_contract(self):
        out = sc.render_text(self.doc, now=NOW, session=SESSION, layout="compact")
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 15)
        self.assertTrue(all(sc.cols(l) <= 80 for l in lines))

    def test_full_lines_fit_80_columns_and_carry_bluf(self):
        out = sc.render_text(self.doc, now=NOW, session=SESSION, layout="full")
        self.assertTrue(all(sc.cols(l) <= 80 for l in out.splitlines()))
        for needle in ("origem: OMP · org/repo", "contexto:", "decisão:", "✅ recomendo A porque",
                       "↩️ REVERSÍVEL", "⌛ sem resposta:", "⏱ 2 min"):
            self.assertIn(needle, out)
        self.assertTrue(out.rstrip().endswith("sessão: " + SESSION[-8:]))

    def test_hint_requires_letter_on_urgent_and_owner_only(self):
        out = sc.render_text(self.doc, now=NOW, session=SESSION)
        self.assertIn(f"Responda: {CODE} 1:A 2:A 3:A", out)
        self.assertIn("(1 e 2 exigem letra · omitido = pendente · - = aceitar A nos demais)", out)

    def test_recommendation_without_pointer_has_no_check_mark(self):
        d = doc(decision(1, evidence=""))
        out = sc.render_text(d, now=NOW, session=SESSION)
        self.assertIn(sc.NO_REC, out)
        self.assertNotIn("✅", out)
        self.assertIn("(1 exige letra · omitido = pendente)", out)

    def test_no_root_session_means_no_numbered_digest(self):
        out = sc.render_text(self.doc, now=NOW, session=None)
        self.assertNotIn("Responda:", out)
        self.assertIn("sem código", out)
        self.assertIn("• · ⏫ ALTA", out)

    def test_ansi_respects_no_color(self):
        out = sc.render_text(self.doc, now=NOW, session=SESSION)
        old = os.environ.pop("NO_COLOR", None)
        try:
            colored = sc.ansi(out)
            self.assertIn("\x1b[", colored)
            self.assertIn("ALTA", re.sub(r"\x1b\[[0-9;]*m", "", colored))
            os.environ["NO_COLOR"] = "1"
            self.assertEqual(sc.ansi(out), out)
        finally:
            os.environ.pop("NO_COLOR", None)
            if old is not None:
                os.environ["NO_COLOR"] = old

    def test_compact_is_five_lines_bluf_and_never_cut(self):
        out = sc.render_text(doc(decision(1, "alta", True)), now=NOW, session=SESSION, layout="compact")
        lines = out.splitlines()
        self.assertNotIn("…", out)
        card = lines[4:-1]
        self.assertEqual(len(card), 4)                    # origin = footer ⇒ no L5
        self.assertTrue(card[1].startswith("    A ✅ Manter — porque é o mais barato (média · spec.md:1)"))
        self.assertEqual(card[2], "    B Mudar")
        self.assertEqual(card[3], "    ⌛ o item fica parado · ↩️ REVERSÍVEL")

    def test_compact_origin_shown_only_when_it_differs_from_footer(self):
        d = doc(decision(1), decision(2))
        d["decisions"][1]["origin"] = {"harness": "Codex", "repo": "org/outro", "session": "x" * 8 + "99990000"}
        out = sc.render_text(d, now=NOW, session=SESSION, layout="compact")
        self.assertIn("Codex · org/outro · 99990000", out)
        self.assertEqual(out.count("org/repo"), 1)        # only the footer

    def test_compact_degrades_lowest_priority_card_first(self):
        d = doc(decision(1, "alta", True), decision(2, "media", True), decision(3))
        for x in d["decisions"]:
            x["origin"] = dict(x["origin"], repo=f"org/r{x['id']}")       # 5-line cards
        out = sc.render_text(d, now=NOW, session=SESSION, layout="compact")
        body = out.splitlines()
        self.assertLessEqual(len(body), 15)
        self.assertNotIn("…", out)
        starts = [i for i, l in enumerate(body) if re.match(r"\d · ", l)] + [len(body) - 1]
        sizes = [b - a for a, b in zip(starts, starts[1:])]
        self.assertEqual(sorted(sizes, reverse=True), sizes)          # 3rd card shrinks first
        for r in ("org/rD1", "org/rD2", "org/rD3"):
            self.assertIn(r, out)                                       # origin never dropped


class CodeTimezoneTest(unittest.TestCase):
    """spec §2: one code generator (synopsis-fuse `_digest_code`), in UTC. The same instant
    gives the same code in both surfaces whatever the host zone; local time only in `( )`."""

    def _env(self, tz):
        env = {k: v for k, v in os.environ.items() if k not in (
            "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "PI_SESSION_ID", "PI_SESSION_FILE",
            "MAOS_SELF_SESSION_ID", "CLAUDE_SESSION_ID")}
        env["TZ"] = tz
        return env

    def test_same_instant_same_code_in_both_surfaces_outside_utc(self):
        self.assertIs(sc.fuse._digest_code, sc.fuse._digest_code)
        self.assertFalse(hasattr(sc, "digest_code"))      # no duplicate generator
        now = 1793060820                                    # 2026-10-27 00:27 UTC = 21:27 -03 the day before
        with tempfile_dir() as tmp:
            dj = pathlib.Path(tmp, "d.json")
            dj.write_text(json.dumps(doc(decision(1))), encoding="utf-8")
            hj = pathlib.Path(tmp, "h.json")
            hj.write_text(json.dumps([{"id": "H-0001", "sev": "🟡 NORMAL", "tipo": "negocio",
                                       "decidir": "x", "session_id": SESSION}]), encoding="utf-8")
            codes, heads = [], []
            for tz in ("America/Sao_Paulo", "UTC"):
                card = subprocess.run([sys.executable, str(_SCRIPT), "ask", str(dj), "--target", "claude",
                                       "--session", SESSION, "--now", str(now)],
                                      capture_output=True, text=True, env=self._env(tz), check=True)
                auq = subprocess.run([sys.executable, str(FUSE), "--hitl-only", "--compass-json", "-",
                                      "--hitl-json", str(hj), "--scope", "all", "--format", "ask-user-question",
                                      "--session-id", SESSION, "--now", str(now)], input="{}",
                                     capture_output=True, text=True, env=self._env(tz), check=True)
                a, b = json.loads(card.stdout), json.loads(auq.stdout)
                codes += [a["code"], b["code"]]
                heads.append(b["preamble"][0])
        self.assertEqual(set(codes), {"K261027-0027-" + SESSION[-8:]})
        self.assertIn("(21:27 -03)", heads[0])
        self.assertIn("(00:27 +00)", heads[1])


class tempfile_dir:
    def __enter__(self):
        import tempfile
        self._d = tempfile.TemporaryDirectory()
        return self._d.name

    def __exit__(self, *exc):
        self._d.cleanup()



class PlanTest(unittest.TestCase):
    def test_fourth_card_only_for_urgent_and_never_more_than_four(self):
        d = doc(*[decision(i, "alta", True) for i in range(1, 6)], decision(6))
        shown, parked, nxt = sc.plan([sc.normalize(x) for x in d["decisions"]])
        self.assertEqual(len(shown), 4)
        self.assertEqual([c["id"] for c in parked], ["D6"])   # only the non-urgent item parks
        self.assertEqual([c["urgency"] for c in nxt], ["alta"])  # ⏫/👤 overflow goes to ⏭, never ⏸

    def test_three_cards_then_at_most_three_parked(self):
        d = doc(*[decision(i) for i in range(1, 9)])
        shown, parked, nxt = sc.plan([sc.normalize(x) for x in d["decisions"]])
        self.assertEqual((len(shown), len(parked), len(nxt)), (3, 3, 2))

    def test_order_owner_urgent_first_then_unblocks(self):
        a, b, c = decision(1), decision(2, "alta", True), decision(3)
        c["unblocks"] = 5
        shown = cards(doc(a, b, c))
        self.assertEqual([x["id"] for x in shown], ["D2", "D3", "D1"])


class AskTest(unittest.TestCase):
    def test_claude_payload_respects_tool_limits(self):
        d = doc(*[decision(i, "alta", True, n_opts=4) for i in range(1, 6)])
        qs = sc.ask_claude(d, now=NOW, session=SESSION)["ask_user_question"]["questions"]
        self.assertTrue(1 <= len(qs) <= 4)
        for q in qs:
            self.assertTrue(2 <= len(q["options"]) <= 4)
            self.assertLessEqual(len(q["header"]), 12)
            self.assertIsInstance(q["multiSelect"], bool)
        self.assertEqual(sc.lint_auq({"questions": qs}), [])

    def test_recommended_first_with_label_and_never_preselected(self):
        d = doc(decision(1, rec="Mudar"))
        q = sc.ask_claude(d, now=NOW, session=SESSION)["ask_user_question"]["questions"][0]
        self.assertEqual(q["options"][0]["label"], "Mudar (recomendado)")
        self.assertNotIn("default", json.dumps(q))

    def test_lint_auq_rejects_out_of_bounds(self):
        bad = {"questions": [{"question": "x?", "header": "header longo demais",
                              "options": [{"label": "só"}], "multiSelect": "no"}]}
        errs = sc.lint_auq(bad)
        self.assertEqual(len(errs), 3)

    def test_single_real_option_is_refused_never_padded(self):
        d = doc(decision(1, n_opts=1))
        for fn in (lambda: sc.render_text(d, now=NOW, session=SESSION),
                   lambda: sc.ask_claude(d, now=NOW, session=SESSION),
                   lambda: sc.ask_omp(d, now=NOW, session=SESSION)):
            with self.assertRaises(sc.InputError):
                fn()
        errs, _ = sc.lint_doc(d, now=NOW, session=SESSION)
        self.assertTrue(any("2–4 opções (tem 1)" in e for e in errs))
        res = sc.aggregate([("s.log", "NEEDS-OPERATOR: Mergear o PR ; rec=mergear ; confidence=alta ; "
                                      "cost-of-not-deciding=PR parado ; origin=OMP·org/a·aaaaaaaa1111")],
                           {"harness": "", "repo": "", "session": ""})
        self.assertEqual(res["decisions"], [])
        self.assertEqual(len(res["rejected"]), 1)
        self.assertNotIn("Manter pendente", json.dumps(res, ensure_ascii=False))

    def test_omp_form_has_no_preselect_and_a_confirmation_gate(self):
        d = doc(decision(1, "alta", True), decision(2, multi=True, rec=["Manter", "Mudar"], n_opts=3))
        form = sc.ask_omp(d, now=NOW, session=SESSION)
        self.assertNotRegex(form, r"\b(checked|selected)\b")
        self.assertIn('type="checkbox" name="d2"', form)
        self.assertIn('type="radio" name="d1"', form)
        self.assertIn('name="confirm"', form)
        self.assertEqual(sc.lint_html(form), [])
        self.assertEqual(len(sc.lint_html(form.replace('value="A">', 'value="A" checked>'))), 1)


class ParseTextTest(unittest.TestCase):
    def setUp(self):
        self.cards = cards(doc(decision(1, "alta", True), decision(2), decision(3, evidence="")))

    def st(self, res):
        return [i["status"] for i in res["items"]]

    def test_valid_answer_and_fechado_line(self):
        res = sc.parse_text(self.cards, f"{CODE} 1:B 2:- 3:a", CODE)
        self.assertEqual(self.st(res), ["decided"] * 3)
        self.assertEqual(res["fechado"], f"{CODE} fechado: 1=B 2=A 3=A")

    def test_dash_refused_on_owner_only_and_no_recommendation(self):
        res = sc.parse_text(self.cards, f"{CODE} 1:- 2:- 3:-", CODE)
        self.assertEqual(self.st(res), ["pending", "decided", "pending"])

    def test_whole_answer_rejections(self):
        self.assertEqual(sc.parse_text(self.cards, "1:A", CODE)["status"], "rejected")
        other = CODE[:-8] + "deadbeef"
        self.assertEqual(sc.parse_text(self.cards, f"{other} 1:A", CODE)["status"], "rejected")
        self.assertEqual(sc.parse_text(self.cards, f"{CODE} 1:A", CODE, closed=[CODE])["status"], "rejected")
        self.assertEqual(sc.parse_text(self.cards, f"{CODE} 1:A", None)["status"], "rejected")

    def test_item_level_rejections(self):
        res = sc.parse_text(self.cards, f"{CODE} 1:A 1:B 2:Z 7:A", CODE)
        self.assertEqual(self.st(res), ["pending", "pending", "pending"])
        self.assertEqual(res["rejected_tokens"][0]["n"], 7)

    def test_free_text_decides_nothing_and_case_is_ignored(self):
        self.assertEqual(self.st(sc.parse_text(self.cards, f"{CODE} sim", CODE)), ["pending"] * 3)
        res = sc.parse_text(self.cards, f"{CODE.lower()}.1:b", CODE)
        self.assertEqual(self.st(res), ["decided", "pending", "pending"])

    def test_already_resolved_is_not_reexecuted(self):
        res = sc.parse_text(self.cards, f"{CODE} 1:A", CODE, resolved={1: "B"})
        self.assertEqual(res["items"][0]["status"], "rejected")
        self.assertIn("já resolvido: B", res["items"][0]["note"])


class ParsePanelTest(unittest.TestCase):
    def setUp(self):
        self.doc = doc(decision(1, "alta", True), decision(2, multi=True, rec=["Manter", "Mudar"], n_opts=3))
        self.cards = cards(self.doc)
        self.qs = sc.ask_claude(self.doc, now=NOW, session=SESSION)["ask_user_question"]["questions"]

    def test_claude_answers_map_to_letters(self):
        res = sc.parse_claude(self.cards, {"answers": {
            self.qs[0]["question"]: self.qs[0]["options"][1]["label"],
            self.qs[1]["question"]: ", ".join(o["label"] for o in self.qs[1]["options"][:2])}}, CODE)
        self.assertEqual([(i["status"], i["letters"]) for i in res["items"]],
                         [("decided", ["B"]), ("decided", ["A", "B"])])

    def test_claude_idle_auto_resolve_is_expired_not_consent(self):
        res = sc.parse_claude(self.cards, {"answers": {self.qs[0]["question"]: self.qs[0]["options"][0]["label"]},
                                           "afkTimeoutMs": 120000}, CODE)
        self.assertEqual({i["status"] for i in res["items"]}, {"expired"})

    def test_claude_unanswered_and_other_text_stay_pending(self):
        res = sc.parse_claude(self.cards, {"answers": {self.qs[1]["question"]: "outra coisa"},
                                           "annotations": {self.qs[0]["question"]: {"unanswered": "skipped"}}}, CODE)
        self.assertEqual([i["status"] for i in res["items"]], ["pending", "pending"])

    def test_omp_requires_explicit_confirmation(self):
        vals = {"d1": "A", "d2": ["A", "C"]}
        self.assertEqual({i["status"] for i in sc.parse_omp(self.cards, vals, CODE)["items"]}, {"pending"})
        res = sc.parse_omp(self.cards, dict(vals, confirm="sim"), CODE)
        self.assertEqual([i["letters"] for i in res["items"]], [["A"], ["A", "C"]])

    def test_omp_timeout_is_expired(self):
        res = sc.parse_omp(self.cards, {"values": {"d1": "A", "confirm": "sim"}, "timedOut": True}, CODE)
        self.assertEqual({i["status"] for i in res["items"]}, {"expired"})


class AggregateLintTest(unittest.TestCase):
    def test_needs_operator_lines_dedupe_and_order(self):
        a = "NEEDS-OPERATOR: Ratificar a regra X ; rec=ratificar ; alt=pedir ajustes ; confidence=alta ; cost-of-not-deciding=PR parado ; urgency=alta ; owner=sim ; origin=Claude Code·org/a·aaaaaaaa1111"
        b = "NEEDS-OPERATOR: Arquivar o plano Y ; rec=arquivar ; alt=manter ; confidence=média ; cost-of-not-deciding=fila ; origin=Codex·org/b·bbbbbbbb2222"
        res = sc.aggregate([("s1.log", a + "\n" + b), ("s2.log", a.replace("aaaaaaaa1111", "cccccccc3333"))],
                           {"harness": "", "repo": "", "session": ""})
        self.assertEqual(res["deduped"], 1)
        self.assertEqual(res["queue"]["cards"][0], "Ratificar a regra X")
        self.assertEqual(len(res["decisions"][0]["origins"]), 2)
        out = sc.render_text(res, now=NOW, session=SESSION)
        self.assertIn("(+1 sessões)", out)
        self.assertNotIn("✅", out)                       # bare lines carry no evidence pointer

    def test_same_ask_in_two_repos_is_two_cards(self):
        line = ("NEEDS-OPERATOR: Mergear o PR ; rec=mergear ; alt=esperar ; confidence=alta ; "
                "cost-of-not-deciding=PR parado ; origin=OMP·{repo}·{s}")
        res = sc.aggregate([("s1.log", line.format(repo="org/a", s="aaaaaaaa1111")),
                            ("s2.log", line.format(repo="org/b", s="bbbbbbbb2222"))],
                           {"harness": "", "repo": "", "session": ""})
        self.assertEqual(res["deduped"], 0)
        self.assertEqual(len(res["queue"]["cards"]), 2)
        self.assertEqual({d["origin"]["repo"] for d in res["decisions"]}, {"org/a", "org/b"})

    def test_lint_clean_and_dirty(self):
        good = doc(decision(1, "alta", True), decision(2))
        self.assertEqual(sc.lint_doc(good, now=NOW, session=SESSION)[0], [])
        bad = copy.deepcopy(good)
        bad["decisions"][0]["options"] = bad["decisions"][0]["options"][:1]
        bad["decisions"][1]["origin"] = {}
        bad["decisions"][1]["recommended"] = "Inexistente"
        errs, _ = sc.lint_doc(bad, now=NOW, session=SESSION)
        self.assertTrue(any("2–4 opções" in e for e in errs))
        self.assertTrue(any("origin sem" in e for e in errs))
        self.assertTrue(any("não é uma opção" in e for e in errs))
        _, warns = sc.lint_doc(doc(decision(1, evidence="")), now=NOW, session=SESSION)
        self.assertTrue(any("sem ponteiro" in w for w in warns))
        no_why = copy.deepcopy(good)
        no_why["decisions"][0].pop("rationale")
        errs, _ = sc.lint_doc(no_why, now=NOW, session=SESSION)
        self.assertTrue(any("sem rationale" in e for e in errs))
        long = doc(decision(1))
        long["decisions"][0]["cost_of_delay"] = "x " * 45
        _, warns = sc.lint_doc(long, now=NOW, session=SESSION)
        self.assertTrue(any("cost_of_delay passa do orçamento" in w for w in warns))

    def test_lint_text_flags_width_and_dash_offer(self):
        errs = sc.lint_text("x" * 81 + f"\nResponda: {CODE} 1:-\n")
        self.assertEqual(len(errs), 2)


if __name__ == "__main__":
    unittest.main()
