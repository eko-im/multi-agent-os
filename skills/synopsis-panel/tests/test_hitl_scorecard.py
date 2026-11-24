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
import unittest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "bin" / "hitl-scorecard.py"
_spec = importlib.util.spec_from_file_location("hitl_scorecard_under_test", _SCRIPT)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

SESSION = "01a20e56-ecbe-7673-8116-76600e63ce53"
NOW = 1795469400                      # fixed instant (UTC) for deterministic codes
CODE = "K" + dt.datetime.fromtimestamp(NOW, tz=dt.timezone.utc).strftime("%y%m%d-%H%M") + "-" + SESSION[-8:]


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
        "recommended": rec, "because": "é o caminho mais barato",
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

    def test_lint_text_flags_width_and_dash_offer(self):
        errs = sc.lint_text("x" * 81 + f"\nResponda: {CODE} 1:-\n")
        self.assertEqual(len(errs), 2)


if __name__ == "__main__":
    unittest.main()
