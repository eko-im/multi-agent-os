"""Acceptance scenarios for skills/on-call-shift (stdlib unittest; no network, no model).

Run: python3 -m unittest discover -s skills/on-call-shift/tests -v
Each test name starts with its scenario number from SKILL.md "Acceptance scenarios".
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bin"))

import shift_engine as se  # noqa: E402

LEASE = 600
SUPERVISOR = "supervisor://shift-desk-1"


def new_shift(now=1000, mantras=None, capabilities=None, backlog=None, budget=5, capacity=2):
    return se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x + team B",
                         backlog=backlog, capacity=capacity, budget=budget, holder="agent-1",
                         supervisor_target=SUPERVISOR, now=now, lease_secs=LEASE,
                         mantras=mantras, capabilities=capabilities)


def demo_backlog():
    with open(os.path.join(HERE, "fixtures", "backlog-demo.json"), encoding="utf-8") as handle:
        return se.normalize_backlog(json.load(handle)["connectors"])


class Scenarios(unittest.TestCase):

    def test_01_same_intent_in_many_trackers_is_one_item_and_one_adoption(self):
        backlog = demo_backlog()
        self.assertEqual([c["connector"] for c in backlog["connectors"]],
                         ["jira-like", "linear-like", "forge-issues", "forge-pull-requests",
                          "tracker-c"])
        item = backlog["items"]["fix-login-timeout"]
        self.assertEqual(sorted(item["refs"]),
                         ["TRK-A-1", "TRK-B-7", "repo/x!13", "repo/x#12"])
        self.assertEqual(item["raci"]["driver"], "agent-1")
        self.assertEqual(item["raci"]["responsible"], "agent-1")
        self.assertEqual(item["raci"]["consulted"], "unknown")  # never invented
        state = new_shift()
        pick = se.select_next(state, backlog, "agent-1", 1001)
        self.assertEqual(pick["action"], "adopt")
        self.assertEqual(pick["intent_key"], "fix-login-timeout")
        state, first = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002)
        state, again = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1003)
        self.assertTrue(first)
        self.assertFalse(again)
        self.assertEqual(len(state["adopted"]), 1)
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        self.assertEqual(state["budget"]["spent"], 1)

    def test_02_item_in_flight_by_other_is_not_adopted_only_offered_help(self):
        backlog = demo_backlog()
        state = new_shift()
        pick = se.select_next(state, backlog, "agent-1", 1001)
        skipped = {s["intent_key"]: s for s in pick["skipped"]}
        self.assertEqual(skipped["rotate-report-cron"]["why"], "IN_FLIGHT_BY_OTHER")
        self.assertIn("remove impediment", skipped["rotate-report-cron"]["offer"])
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "rotate-report-cron", backlog, 1002)
        self.assertEqual(err.exception.code, "IN_FLIGHT_BY_OTHER")

    def test_03_human_gate_waits_with_reason_and_deadline(self):
        backlog = demo_backlog()
        state = new_shift()
        pick = se.select_next(state, backlog, "agent-1", 1001)
        skipped = {s["intent_key"]: s for s in pick["skipped"]}
        self.assertEqual(skipped["publish-pricing-page"]["why"], "HUMAN_GATE")
        state["in_flight"].append("publish-pricing-page")
        se.set_gate(state, "publish-pricing-page",
                    {"kind": "approval", "by": "owner-1", "deadline": 5000, "state": "pending"})
        result = se.complete_item(state, "agent-1", "publish-pricing-page",
                                  author="agent-1", reviewer="agent-2", now=1002)
        self.assertEqual(result, {"completed": False, "reason": "AWAITING_HUMAN_GATE",
                                  "deadline": 5000})
        self.assertIn("publish-pricing-page", state["in_flight"])

    def test_04_handoff_needs_successor_ack_and_keeps_one_holder_and_cursor(self):
        state = new_shift()
        se.apply_tick(state, "t1", 1001)
        state["in_flight"] = ["fix-login-timeout"]
        se.set_gate(state, "publish-pricing-page", {"kind": "approval", "state": "pending"})
        se.propose_handoff(state, "agent-1", "agent-2", 1002)
        # a heartbeat is not an ACK
        self.assertEqual(se.accept_handoff(state, {"kind": "heartbeat", "from": "agent-2"}, 1003),
                         {"relieved": False, "reason": "NOT_A_HANDOFF_ACK"})
        # an ACK that drops in-flight work is refused
        bad = {"kind": "handoff_ack", "from": "agent-2", "cursor_seq": 1, "in_flight": [],
               "gates": ["publish-pricing-page"]}
        self.assertEqual(se.accept_handoff(state, bad, 1004)["reason"], "ACK_MISMATCH_IN_FLIGHT")
        self.assertEqual(state["holder"], "agent-1")
        good = {"kind": "handoff_ack", "from": "agent-2", "cursor_seq": 1,
                "in_flight": ["fix-login-timeout"], "gates": ["publish-pricing-page"]}
        self.assertEqual(se.accept_handoff(state, good, 1005), {"relieved": True, "reason": None})
        self.assertEqual(state["holder"], "agent-2")
        self.assertEqual(state["lease"]["holder"], "agent-2")
        self.assertEqual(state["cursor"]["seq"], 1)
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        self.assertFalse(se.lease_valid(state, "agent-1", 1006))
        self.assertTrue(se.lease_valid(state, "agent-2", 1006))

    def test_04b_silence_is_not_relief(self):
        state = new_shift()
        se.propose_handoff(state, "agent-1", "agent-2", 1002)
        self.assertTrue(se.handoff_timed_out(state, 1002 + 300, deadline_secs=300))
        self.assertEqual(state["holder"], "agent-1")
        self.assertEqual(state["status"], se.ACTIVE)

    def test_05_unavailable_connector_is_not_an_empty_queue(self):
        backlog = se.normalize_backlog([
            {"connector": "tracker-a", "status": "empty", "items": []},
            {"connector": "tracker-c", "status": "unavailable", "items": []},
            {"connector": "tracker-d", "status": "denied", "items": []},
        ])
        self.assertFalse(backlog["queue_empty"])
        pick = se.select_next(new_shift(), backlog, "agent-1", 1001)
        self.assertEqual(pick["action"], "wait")
        self.assertEqual(pick["reason"], "CONNECTORS_NOT_READABLE")
        self.assertEqual(pick["connectors"], ["tracker-c", "tracker-d"])
        empty = se.normalize_backlog([{"connector": "tracker-a", "status": "empty", "items": []}])
        self.assertTrue(empty["queue_empty"])
        self.assertEqual(se.select_next(new_shift(), empty, "agent-1", 1001)["reason"],
                         "NO_ELIGIBLE_ITEM")

    def test_06_no_mantra_gets_defaults_explicit_is_kept_verbatim(self):
        state = new_shift(mantras=None)
        self.assertEqual(state["mantras"], list(se.DEFAULT_MANTRAS))
        self.assertEqual(state["mantras_source"], "default")
        own = ["Ship small, Ship often."]
        state = new_shift(mantras=own)
        self.assertEqual(state["mantras"], own)
        self.assertEqual(state["mantras_source"], "explicit")
        self.assertEqual(new_shift(mantras=["  "])["mantras_source"], "default")

    def test_07_duplicate_tick_has_one_effect(self):
        state = new_shift()
        _, first = se.apply_tick(state, "tick-42", 1001)
        _, second = se.apply_tick(state, "tick-42", 1002)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(state["effects"]), 1)
        self.assertEqual(state["cursor"]["seq"], 1)
        self.assertEqual(first["notification"], "NOT_SENT_BY_TIMER")

    def test_08_wrong_target_or_expired_lease_is_not_sent(self):
        state = new_shift(now=1000)
        self.assertEqual(se.authorize_send(state, "agent-1", "supervisor://other", 1001),
                         {"allowed": False, "reason": "WRONG_TARGET"})
        self.assertEqual(se.authorize_send(state, "agent-1", SUPERVISOR, 1000 + LEASE),
                         {"allowed": False, "reason": "LEASE_INVALID"})
        self.assertEqual(se.authorize_send(state, "agent-2", SUPERVISOR, 1001)["reason"],
                         "LEASE_INVALID")
        self.assertTrue(se.authorize_send(state, "agent-1", SUPERVISOR, 1001)["allowed"])

    def test_09_event_without_ack_is_not_concluded(self):
        state = new_shift()
        se.open_event(state, "agent-1", "ev-1", 1001)
        self.assertEqual(se.conclude_event(state, "agent-1", "ev-1", None, 1002),
                         {"concluded": False, "reason": "NO_ACK"})
        self.assertEqual(
            se.conclude_event(state, "agent-1", "ev-1",
                              {"event_id": "ev-1", "from": "x", "kind": "heartbeat"}, 1003),
            {"concluded": False, "reason": "HEARTBEAT_IS_NOT_ACK"})
        self.assertIn("ev-1", state["pending_events"])
        self.assertTrue(se.conclude_event(state, "agent-1", "ev-1",
                                          {"event_id": "ev-1", "from": "owner-1"},
                                          1004)["concluded"])
        self.assertNotIn("ev-1", state["pending_events"])

    def test_10_restart_restores_lease_cursor_and_work(self):
        backlog = demo_backlog()
        state = new_shift()
        se.apply_tick(state, "t1", 1001)
        se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shift.json")
            se.save(state, path)
            restored = se.load(path)
        self.assertEqual(restored, state)
        self.assertTrue(se.lease_valid(restored, "agent-1", 1003))
        _, replay = se.apply_tick(restored, "t1", 1004)
        self.assertIsNone(replay)  # replay after restart is still one effect
        _, readopt = se.adopt(restored, "agent-1", "fix-login-timeout", backlog, 1005)
        self.assertFalse(readopt)

    def test_11_human_veto_is_respected_not_faked(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.set_gate(state, "fix-login-timeout", {"kind": "veto", "by": "owner-1",
                                                 "state": "vetoed"})
        result = se.complete_item(state, "agent-1", "fix-login-timeout",
                                  author="agent-1", reviewer="agent-2", now=1001)
        self.assertEqual(result["reason"], "VETOED")
        self.assertIn("fix-login-timeout", state["in_flight"])

    def test_12_reviewer_must_not_be_author(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        result = se.complete_item(state, "agent-1", "fix-login-timeout",
                                  author="agent-1", reviewer="agent-1", now=1001)
        self.assertEqual(result, {"completed": False, "reason": "REVIEWER_IS_AUTHOR"})
        ok = se.complete_item(state, "agent-1", "fix-login-timeout",
                              author="agent-1", reviewer="agent-2", now=1002)
        self.assertTrue(ok["completed"])

    def test_13_wakeup_kind_is_proven_and_degraded_without_transport(self):
        state = new_shift(capabilities={})
        self.assertEqual(state["wakeup"]["mode"], "DEGRADED")
        self.assertEqual(state["wakeup"]["reason"], "NO_BOUND_WAKEUP_TRANSPORT")
        self.assertFalse(state["wakeup"]["always_on_claim"])
        self.assertTrue(state["wakeup"]["recovery"])
        # claiming a wakeup without support is recorded as what the receipt proves
        entry = se.record_signal(state, "wakeup", "ev-1",
                                 {"delivered_to": SUPERVISOR, "woken": SUPERVISOR}, 1001)
        self.assertEqual(entry["signal"], "notification")
        self.assertTrue(entry["downgraded"])
        supported = new_shift(capabilities={"wakeup_transport": "host-push",
                                            "bound_target": SUPERVISOR})
        self.assertEqual(supported["wakeup"]["mode"], "SUPPORTED")
        woke = se.record_signal(supported, "resume", "ev-2",
                                {"delivered_to": SUPERVISOR, "woken": SUPERVISOR}, 1002)
        self.assertEqual(woke["signal"], "wakeup")  # not consumed yet, so not a resume
        resumed = se.record_signal(supported, "resume", "ev-3",
                                   {"delivered_to": SUPERVISOR, "woken": SUPERVISOR,
                                    "consumed_by": "agent-1", "effects": 1}, 1003)
        self.assertEqual(resumed["signal"], "resume")
        self.assertFalse(resumed["downgraded"])
        wrong = se.record_signal(supported, "wakeup", "ev-4", {"woken": "supervisor://other"}, 1004)
        self.assertEqual(wrong["signal"], "tick")


class UserDeliveredValue(unittest.TestCase):
    """UDV: the intended recipient received the result and is satisfied."""

    def delivered(self, recipient="person-1", kind="human", received=True):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.complete_item(state, "agent-1", "fix-login-timeout",
                         author="agent-1", reviewer="agent-2", now=1001)
        result = se.deliver(state, "agent-1", "fix-login-timeout", recipient=recipient,
                            recipient_kind=kind, result_ref="repo/x!13@abc123",
                            receipt={"received_by": recipient if received else None}, now=1002)
        return state, result

    def test_14_technical_done_alone_is_not_udv(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.complete_item(state, "agent-1", "fix-login-timeout",
                         author="agent-1", reviewer="agent-2", now=1001)
        status = se.udv_status(state, "fix-login-timeout")
        self.assertTrue(status["technical_verified"])
        self.assertEqual(status["udv_percent"], 0)
        self.assertEqual(status["pending"], "AWAITING_RECIPIENT")

    def test_15_absent_user_stays_pending_not_100_and_no_resend(self):
        state, result = self.delivered(received=False)
        self.assertEqual(result["reason"], "RECIPIENT_ABSENT_PENDING")
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual((status["udv_percent"], status["satisfaction"], status["pending"]),
                         (0, "unknown", "AWAITING_RECIPIENT"))
        again = se.deliver(state, "agent-1", "fix-login-timeout", recipient="person-1",
                           recipient_kind="human", result_ref="repo/x!13@abc123",
                           receipt={"received_by": None}, now=1003)
        self.assertEqual(again, {"sent": False, "reason": "NO_RESEND_SAME_RESULT"})
        self.assertEqual(state["deliveries"]["fix-login-timeout"]["attempts"], 1)
        # the shift may still pick other eligible work; the pending item stays pending
        pick = se.select_next(state, demo_backlog(), "agent-1", 1004)
        self.assertEqual(pick["action"], "adopt")
        self.assertEqual(se.udv_status(state, "fix-login-timeout")["udv_percent"], 0)

    def test_16_dissatisfied_user_reopens_intent_linked_to_original(self):
        state, _ = self.delivered()
        out = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                 {"from": "person-1", "kind": "reject",
                                  "note": "still times out"}, 1003)
        self.assertTrue(out["recorded"])
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual((status["satisfaction"], status["udv_percent"], status["pending"]),
                         ("refused", 0, "REJECTED_REOPENED"))
        reopened = state["deliveries"]["fix-login-timeout"]["reopened_as"]
        self.assertEqual(state["reopened"][reopened]["reopens"], "fix-login-timeout")
        self.assertEqual(state["reopened"][reopened]["result_ref"], "repo/x!13@abc123")
        self.assertIn(reopened, state["in_flight"])

    def test_17_valid_acceptance_is_udv_100(self):
        state, _ = self.delivered()
        se.record_feedback(state, "agent-1", "fix-login-timeout",
                           {"from": "person-1", "kind": "accept"}, 1003)
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual(status, {"technical_verified": True, "delivered_to_recipient": True,
                                  "satisfaction": "confirmed", "udv_percent": 100,
                                  "pending": None})

    def test_18_qualified_acceptance_is_not_unequivocal_satisfaction(self):
        state, _ = self.delivered()
        se.record_feedback(state, "agent-1", "fix-login-timeout",
                           {"from": "person-1", "kind": "accept_with_reservation",
                            "note": "ok for now, slow on mobile"}, 1003)
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual((status["satisfaction"], status["udv_percent"], status["pending"]),
                         ("unknown", 0, "QUALIFIED_ACCEPTANCE"))

    def test_19_agent_recipient_accepts_only_for_its_own_role(self):
        state, _ = self.delivered(recipient="agent-7", kind="agent")
        out = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                 {"from": "agent-7", "kind": "accept",
                                  "on_behalf_of": "person-1"}, 1003)
        self.assertEqual(out["reason"], "AGENT_CANNOT_ACCEPT_FOR_A_PERSON")
        other = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                   {"from": "agent-9", "kind": "accept"}, 1004)
        self.assertEqual(other["reason"], "NOT_THE_RECIPIENT")
        self.assertEqual(se.udv_status(state, "fix-login-timeout")["udv_percent"], 0)


class BlastRadius(unittest.TestCase):

    def blast(self, **overrides):
        base = {"data": "one branch", "people": "none", "projects": "repo/x",
                "accounts": "agent-1", "dependencies": "none", "reversible": True,
                "worst_case": "revert one commit", "detection": "CI", "recovery_owner": "agent-1",
                "crosses_authority": False, "in_scope": True}
        base.update(overrides)
        return base

    def test_20_local_reversible_proceeds_authority_crossing_parks_only_that_op(self):
        state = new_shift()
        self.assertEqual(se.assess_effect(state, "agent-1", "op-1", self.blast(), 1001)["decision"],
                         "proceed")
        parked = se.assess_effect(state, "agent-1", "op-2",
                                  self.blast(crosses_authority=True, accounts="org-b"), 1002)
        self.assertEqual(parked, {"decision": "park", "reason": "CROSSES_AUTHORITY"})
        self.assertEqual([p["operation"] for p in state["parked"]], ["op-2"])
        self.assertEqual(state["status"], se.ACTIVE)  # the shift keeps running
        self.assertEqual(se.assess_effect(state, "agent-1", "op-3", self.blast(), 1003)["decision"],
                         "proceed")
        incomplete = se.assess_effect(state, "agent-1", "op-4", {"data": "x"}, 1004)
        self.assertEqual(incomplete["reason"], "INCOMPLETE_BLAST_RADIUS")


class HolderLoss(unittest.TestCase):

    def test_21_holder_dies_with_preauthorized_successor_one_takeover_new_generation(self):
        state = se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x",
                              backlog=None, capacity=2, budget=5, holder="agent-1",
                              supervisor_target=SUPERVISOR, now=1000, lease_secs=LEASE,
                              successor_policy={"pre_authorized": "agent-2"})
        se.apply_tick(state, "t1", 1001)
        state["in_flight"].append("fix-login-timeout")
        se.set_gate(state, "publish-pricing-page", {"kind": "approval", "state": "pending"})
        old_gen = state["generation"]
        self.assertEqual(se.take_over(state, "agent-2", 1100)["reason"],
                         "HOLDER_LEASE_STILL_VALID")
        dead = 1000 + LEASE + 1
        self.assertEqual(se.take_over(state, "agent-3", dead)["reason"],
                         "NOT_THE_PREAUTHORIZED_SUCCESSOR")
        first = se.take_over(state, "agent-2", dead)
        self.assertTrue(first["taken_over"])
        self.assertEqual(state["generation"], old_gen + 1)
        second = se.take_over(state, "agent-2", dead + 1)
        self.assertEqual(second["reason"], "HOLDER_LEASE_STILL_VALID")  # exactly one takeover
        self.assertEqual(len([e for e in state["log"] if e["event"] == "taken_over"]), 1)
        self.assertEqual(state["cursor"]["seq"], 1)
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        self.assertIn("publish-pricing-page", state["gates"])
        # the old holder comes back: refused by holder and by generation
        self.assertFalse(se.lease_valid(state, "agent-1", dead + 2))
        self.assertEqual(se.authorize_send(state, "agent-1", SUPERVISOR, dead + 2,
                                           generation=old_gen)["reason"], "STALE_GENERATION")
        self.assertTrue(se.authorize_send(state, "agent-2", SUPERVISOR, dead + 2,
                                          generation=state["generation"])["allowed"])

    def test_22_holder_dies_without_successor_is_degraded(self):
        state = new_shift(now=1000)
        self.assertEqual(state["continuity"]["mode"], "DEGRADED")
        out = se.take_over(state, "agent-2", 1000 + LEASE + 1)
        self.assertEqual(out, {"taken_over": False, "reason": "NO_PREAUTHORIZED_SUCCESSOR"})
        self.assertEqual(state["holder"], "agent-1")
        self.assertEqual(state["continuity"],
                         {"mode": "DEGRADED", "reason": "NO_PREAUTHORIZED_SUCCESSOR",
                          "uninterrupted_claim": False})
        self.assertFalse(se.lease_valid(state, "agent-1", 1000 + LEASE + 1))

    def test_23_relief_cannot_be_decided_alone_by_predecessor(self):
        state = new_shift()
        se.propose_handoff(state, "agent-1", "agent-2", 1001)
        forged = {"kind": "handoff_ack", "from": "agent-1", "cursor_seq": 0,
                  "in_flight": [], "gates": []}
        self.assertEqual(se.accept_handoff(state, forged, 1002)["reason"], "ACK_FROM_WRONG_PARTY")
        self.assertEqual(state["holder"], "agent-1")


class ContractEdges(unittest.TestCase):

    def test_backlog_given_blocks_adoption_until_exhausted(self):
        backlog = demo_backlog()
        state = new_shift(backlog="list://owner-1/tonight")
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1001)
        self.assertEqual(err.exception.code, "BACKLOG_GIVEN")
        se.mark_backlog_exhausted(state, "agent-1", 1002)
        _, adopted = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1003)
        self.assertTrue(adopted)

    def test_budget_and_capacity_stop_new_work(self):
        backlog = demo_backlog()
        state = new_shift(budget=0)
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1001)["reason"],
                         "BUDGET_EXHAUSTED")
        state = new_shift(capacity=1)
        state["in_flight"].append("other")
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1001)["reason"],
                         "CAPACITY_FULL")

    def test_only_principal_can_stop_or_revoke(self):
        state = new_shift()
        with self.assertRaises(se.ShiftError):
            se.stop_shift(state, "agent-1", 1001)
        se.stop_shift(state, "owner-1", 1002, revoke=True)
        self.assertEqual(state["status"], se.REVOKED)
        self.assertFalse(se.lease_valid(state, "agent-1", 1002))

    def test_templates_match_engine(self):
        templates = os.path.join(HERE, "..", "templates")
        with open(os.path.join(templates, "shift-state.schema.json"), encoding="utf-8") as h:
            schema = json.load(h)
        with open(os.path.join(templates, "shift-state.example.json"), encoding="utf-8") as h:
            example = json.load(h)
        state = new_shift()
        self.assertEqual(sorted(schema["required"]), sorted(state))
        self.assertEqual(sorted(example), sorted(state))
        self.assertEqual(schema["properties"]["schema"]["const"], se.SCHEMA)
        self.assertEqual(example["mantras"], list(se.DEFAULT_MANTRAS))

    def test_open_shift_refuses_missing_fields(self):
        with self.assertRaises(se.ShiftError) as err:
            se.open_shift(shift_id="s", principal="", scope="x", backlog=None, capacity=1,
                          budget=1, holder="a", supervisor_target="t", now=0, lease_secs=1)
        self.assertEqual(err.exception.code, "MISSING_FIELD")


if __name__ == "__main__":
    unittest.main()
