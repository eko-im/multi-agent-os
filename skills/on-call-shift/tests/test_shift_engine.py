"""Acceptance scenarios for skills/on-call-shift (stdlib unittest; no network, no model).

Run: python3 -m unittest discover -s skills/on-call-shift/tests -v
Each test name starts with its scenario number from SKILL.md "Acceptance scenarios".
"""
import copy
import json
import os
import sys
import re
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
        pick = se.select_next(state, backlog, "agent-1", 1001, generation=state["generation"])
        self.assertEqual(pick["action"], "adopt")
        self.assertEqual(pick["intent_key"], "fix-login-timeout")
        state, first = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002, generation=state["generation"])
        state, again = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1003, generation=state["generation"])
        self.assertTrue(first)
        self.assertFalse(again)
        self.assertEqual(len(state["adopted"]), 1)
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        self.assertEqual(state["budget"]["spent"], 1)

    def test_02_item_in_flight_by_other_is_not_adopted_only_offered_help(self):
        backlog = demo_backlog()
        state = new_shift()
        pick = se.select_next(state, backlog, "agent-1", 1001, generation=state["generation"])
        skipped = {s["intent_key"]: s for s in pick["skipped"]}
        self.assertEqual(skipped["rotate-report-cron"]["why"], "IN_FLIGHT_BY_OTHER")
        self.assertIn("remove impediment", skipped["rotate-report-cron"]["offer"])
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "rotate-report-cron", backlog, 1002, generation=state["generation"])
        self.assertEqual(err.exception.code, "IN_FLIGHT_BY_OTHER")

    def test_03_human_gate_waits_with_reason_and_deadline(self):
        backlog = demo_backlog()
        state = new_shift()
        pick = se.select_next(state, backlog, "agent-1", 1001, generation=state["generation"])
        skipped = {s["intent_key"]: s for s in pick["skipped"]}
        self.assertEqual(skipped["publish-pricing-page"]["why"], "HUMAN_GATE")
        state["in_flight"].append("publish-pricing-page")
        se.set_gate(state, "agent-1", "publish-pricing-page",
                    {"kind": "approval", "by": "owner-1", "deadline": 5000, "state": "pending"}, 1001, generation=state["generation"])
        result = se.complete_item(state, "agent-1", "publish-pricing-page",
                                  author="agent-1", reviewer="agent-2", now=1002, generation=state["generation"])
        self.assertEqual(result, {"completed": False, "reason": "AWAITING_HUMAN_GATE",
                                  "deadline": 5000})
        self.assertIn("publish-pricing-page", state["in_flight"])

    def test_04_handoff_needs_successor_ack_and_keeps_one_holder_and_cursor(self):
        state = new_shift()
        se.apply_tick(state, "agent-1", "t1", 1001, generation=state["generation"])
        state["in_flight"] = ["fix-login-timeout"]
        se.set_gate(state, "agent-1", "publish-pricing-page", {"kind": "approval", "state": "pending"}, 1001, generation=state["generation"])
        se.propose_handoff(state, "agent-1", "agent-2", 1002, generation=state["generation"])
        # a heartbeat is not an ACK
        self.assertEqual(se.accept_handoff(state, {"kind": "heartbeat", "from": "agent-2"}, 1003),
                         {"relieved": False, "reason": "NOT_A_HANDOFF_ACK"})
        # an ACK that drops in-flight work is refused
        bad = {"kind": "handoff_ack", "generation": 1, "from": "agent-2", "cursor_seq": 1, "in_flight": [],
               "gates": ["publish-pricing-page"]}
        self.assertEqual(se.accept_handoff(state, bad, 1004)["reason"], "ACK_MISMATCH_IN_FLIGHT")
        self.assertEqual(state["holder"], "agent-1")
        good = {"kind": "handoff_ack", "generation": 1, "from": "agent-2", "cursor_seq": 1,
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
        se.propose_handoff(state, "agent-1", "agent-2", 1002, generation=state["generation"])
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
        pick = se.select_next(new_shift(), backlog, "agent-1", 1001, generation=new_shift()["generation"])
        self.assertEqual(pick["action"], "wait")
        self.assertEqual(pick["reason"], "CONNECTORS_NOT_READABLE")
        self.assertEqual(pick["connectors"], ["tracker-c", "tracker-d"])
        empty = se.normalize_backlog([{"connector": "tracker-a", "status": "empty", "items": []}])
        self.assertTrue(empty["queue_empty"])
        self.assertEqual(se.select_next(new_shift(), empty, "agent-1", 1001, generation=new_shift()["generation"])["reason"],
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
        _, first = se.apply_tick(state, "agent-1", "tick-42", 1001, generation=state["generation"])
        _, second = se.apply_tick(state, "agent-1", "tick-42", 1002, generation=state["generation"])
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
        se.open_event(state, "agent-1", "ev-1", 1001, recipient="owner-1", generation=state["generation"])
        self.assertEqual(se.conclude_event(state, "agent-1", "ev-1", None, 1002, generation=state["generation"]),
                         {"concluded": False, "reason": "NO_ACK"})
        self.assertEqual(
            se.conclude_event(state, "agent-1", "ev-1",
                              {"event_id": "ev-1", "from": "x", "kind": "heartbeat"}, 1003, generation=state["generation"]),
            {"concluded": False, "reason": "HEARTBEAT_IS_NOT_ACK"})
        self.assertIn("ev-1", state["pending_events"])
        self.assertTrue(se.conclude_event(state, "agent-1", "ev-1",
                                          {"event_id": "ev-1", "from": "owner-1"},
                                          1004, generation=state["generation"])["concluded"])
        self.assertNotIn("ev-1", state["pending_events"])

    def test_10_restart_restores_lease_cursor_and_work(self):
        backlog = demo_backlog()
        state = new_shift()
        se.apply_tick(state, "agent-1", "t1", 1001, generation=state["generation"])
        se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002, generation=state["generation"])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shift.json")
            se.save(state, path)
            restored = se.load(path)
        self.assertEqual(restored, state)
        self.assertTrue(se.lease_valid(restored, "agent-1", 1003))
        _, replay = se.apply_tick(restored, "agent-1", "t1", 1004, generation=restored["generation"])
        self.assertIsNone(replay)  # replay after restart is still one effect
        _, readopt = se.adopt(restored, "agent-1", "fix-login-timeout", backlog, 1005, generation=restored["generation"])
        self.assertFalse(readopt)

    def test_11_human_veto_is_respected_not_faked(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.set_gate(state, "agent-1", "fix-login-timeout", {"kind": "veto", "by": "owner-1",
                                                 "state": "vetoed"}, 1001, generation=state["generation"])
        result = se.complete_item(state, "agent-1", "fix-login-timeout",
                                  author="agent-1", reviewer="agent-2", now=1001, generation=state["generation"])
        self.assertEqual(result["reason"], "VETOED")
        self.assertIn("fix-login-timeout", state["in_flight"])

    def test_12_reviewer_must_not_be_author(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        result = se.complete_item(state, "agent-1", "fix-login-timeout",
                                  author="agent-1", reviewer="agent-1", now=1001, generation=state["generation"])
        self.assertEqual(result, {"completed": False, "reason": "REVIEWER_IS_AUTHOR"})
        ok = se.complete_item(state, "agent-1", "fix-login-timeout",
                              author="agent-1", reviewer="agent-2", now=1002, generation=state["generation"])
        self.assertTrue(ok["completed"])

    def test_13_wakeup_kind_is_proven_and_degraded_without_transport(self):
        state = new_shift(capabilities={})
        self.assertEqual(state["wakeup"]["mode"], "DEGRADED")
        self.assertEqual(state["wakeup"]["reason"], "NO_BOUND_WAKEUP_TRANSPORT")
        self.assertFalse(state["wakeup"]["always_on_claim"])
        self.assertTrue(state["wakeup"]["recovery"])
        # claiming a wakeup without support is recorded as what the receipt proves
        entry = se.record_signal(state, "agent-1", "wakeup", "ev-1",
                                 {"delivered_to": SUPERVISOR, "woken": SUPERVISOR}, 1001, generation=state["generation"])
        self.assertEqual(entry["signal"], "notification")
        self.assertTrue(entry["downgraded"])
        supported = new_shift(capabilities={"wakeup_transport": "host-push",
                                            "bound_target": SUPERVISOR})
        self.assertEqual(supported["wakeup"]["mode"], "SUPPORTED")
        woke = se.record_signal(supported, "agent-1", "resume", "ev-2",
                                {"delivered_to": SUPERVISOR, "woken": SUPERVISOR}, 1002, generation=supported["generation"])
        self.assertEqual(woke["signal"], "wakeup")  # not consumed yet, so not a resume
        resumed = se.record_signal(supported, "agent-1", "resume", "ev-3",
                                   {"delivered_to": SUPERVISOR, "woken": SUPERVISOR,
                                    "consumed_by": "agent-1", "effects": 1}, 1003, generation=supported["generation"])
        self.assertEqual(resumed["signal"], "resume")
        self.assertFalse(resumed["downgraded"])
        wrong = se.record_signal(supported, "agent-1", "wakeup", "ev-4", {"woken": "supervisor://other"}, 1004, generation=supported["generation"])
        self.assertEqual(wrong["signal"], "tick")


class UserDeliveredValue(unittest.TestCase):
    """UDV: the intended recipient received the result and is satisfied."""

    def delivered(self, recipient="person-1", kind="human", received=True):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.complete_item(state, "agent-1", "fix-login-timeout",
                         author="agent-1", reviewer="agent-2", now=1001, generation=state["generation"])
        result = se.deliver(state, "agent-1", "fix-login-timeout", recipient=recipient,
                            recipient_kind=kind, result_ref="repo/x!13@abc123",
                            receipt={"received_by": recipient if received else None}, now=1002, generation=state["generation"])
        return state, result

    def test_14_technical_done_alone_is_not_udv(self):
        state = new_shift()
        state["in_flight"].append("fix-login-timeout")
        se.complete_item(state, "agent-1", "fix-login-timeout",
                         author="agent-1", reviewer="agent-2", now=1001, generation=state["generation"])
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
                           receipt={"received_by": None}, now=1003, generation=state["generation"])
        self.assertEqual(again, {"sent": False, "reason": "NO_RESEND_SAME_RESULT"})
        self.assertEqual(state["deliveries"]["fix-login-timeout"]["attempts"], 1)
        # the shift may still pick other eligible work; the pending item stays pending
        pick = se.select_next(state, demo_backlog(), "agent-1", 1004, generation=state["generation"])
        self.assertEqual(pick["action"], "adopt")
        self.assertEqual(se.udv_status(state, "fix-login-timeout")["udv_percent"], 0)

    def test_16_dissatisfied_user_reopens_intent_linked_to_original(self):
        state, _ = self.delivered()
        out = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                 {"from": "person-1", "kind": "reject",
                                  "note": "still times out"}, 1003, generation=state["generation"])
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
                           {"from": "person-1", "kind": "accept"}, 1003, generation=state["generation"])
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual(status, {"technical_verified": True, "delivered_to_recipient": True,
                                  "satisfaction": "confirmed", "udv_percent": 100,
                                  "pending": None})

    def test_18_qualified_acceptance_is_not_unequivocal_satisfaction(self):
        state, _ = self.delivered()
        se.record_feedback(state, "agent-1", "fix-login-timeout",
                           {"from": "person-1", "kind": "accept_with_reservation",
                            "note": "ok for now, slow on mobile"}, 1003, generation=state["generation"])
        status = se.udv_status(state, "fix-login-timeout")
        self.assertEqual((status["satisfaction"], status["udv_percent"], status["pending"]),
                         ("unknown", 0, "QUALIFIED_ACCEPTANCE"))

    def test_19_agent_recipient_accepts_only_for_its_own_role(self):
        state, _ = self.delivered(recipient="agent-7", kind="agent")
        out = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                 {"from": "agent-7", "kind": "accept",
                                  "on_behalf_of": "person-1"}, 1003, generation=state["generation"])
        self.assertEqual(out["reason"], "AGENT_CANNOT_ACCEPT_FOR_A_PERSON")
        other = se.record_feedback(state, "agent-1", "fix-login-timeout",
                                   {"from": "agent-9", "kind": "accept"}, 1004, generation=state["generation"])
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
        self.assertEqual(se.assess_effect(state, "agent-1", "op-1", self.blast(), 1001, generation=state["generation"])["decision"],
                         "proceed")
        parked = se.assess_effect(state, "agent-1", "op-2",
                                  self.blast(crosses_authority=True, accounts="org-b"), 1002, generation=state["generation"])
        self.assertEqual(parked, {"decision": "park", "reason": "CROSSES_AUTHORITY"})
        self.assertEqual([p["operation"] for p in state["parked"]], ["op-2"])
        self.assertEqual(state["status"], se.ACTIVE)  # the shift keeps running
        self.assertEqual(se.assess_effect(state, "agent-1", "op-3", self.blast(), 1003, generation=state["generation"])["decision"],
                         "proceed")
        incomplete = se.assess_effect(state, "agent-1", "op-4", {"data": "x"}, 1004, generation=state["generation"])
        self.assertEqual(incomplete["reason"], "INCOMPLETE_BLAST_RADIUS")


class HolderLoss(unittest.TestCase):

    def test_21_holder_dies_with_preauthorized_successor_one_takeover_new_generation(self):
        state = se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x",
                              backlog=None, capacity=2, budget=5, holder="agent-1",
                              supervisor_target=SUPERVISOR, now=1000, lease_secs=LEASE,
                              successor_policy={"pre_authorized": "agent-2"})
        se.apply_tick(state, "agent-1", "t1", 1001, generation=state["generation"])
        state["in_flight"].append("fix-login-timeout")
        se.set_gate(state, "agent-1", "publish-pricing-page", {"kind": "approval", "state": "pending"}, 1001, generation=state["generation"])
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
        se.propose_handoff(state, "agent-1", "agent-2", 1001, generation=state["generation"])
        forged = {"kind": "handoff_ack", "generation": 1, "from": "agent-1", "cursor_seq": 0,
                  "in_flight": [], "gates": []}
        self.assertEqual(se.accept_handoff(state, forged, 1002)["reason"], "ACK_FROM_WRONG_PARTY")
        self.assertEqual(state["holder"], "agent-1")


class SuccessionHardening(unittest.TestCase):
    """Root objection: one authorization, one succession; no replay; no self-succession."""

    def armed_shift(self):
        state = se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x",
                              backlog=None, capacity=2, budget=5, holder="agent-1",
                              supervisor_target=SUPERVISOR, now=1000, lease_secs=LEASE,
                              successor_policy={"pre_authorized": "agent-2"})
        return state

    def test_24_policy_consumed_second_expiry_refused_and_degraded(self):
        state = self.armed_shift()
        dead1 = 1000 + LEASE + 1
        self.assertTrue(se.take_over(state, "agent-2", dead1)["taken_over"])
        self.assertIsNone(state["successor_policy"])
        self.assertEqual(state["continuity"]["mode"], "DEGRADED")
        dead2 = dead1 + LEASE + 1  # agent-2 dies too, nobody re-armed
        out = se.take_over(state, "agent-3", dead2)
        self.assertEqual(out["reason"], "NO_PREAUTHORIZED_SUCCESSOR")
        self.assertEqual(state["holder"], "agent-2")
        self.assertEqual(state["generation"], 2)
        self.assertEqual(state["continuity"]["reason"], "NO_PREAUTHORIZED_SUCCESSOR")

    def test_25_policy_from_older_generation_does_not_apply(self):
        state = self.armed_shift()
        se.propose_handoff(state, "agent-1", "agent-3", 1001, generation=state["generation"])
        se.accept_handoff(state, {"kind": "handoff_ack", "generation": 1, "from": "agent-3", "cursor_seq": 0,
                                  "in_flight": [], "gates": []}, 1002)
        self.assertEqual(state["generation"], 2)
        self.assertEqual(state["continuity"]["mode"], "DEGRADED")
        out = se.take_over(state, "agent-2", 1002 + LEASE + 1)
        self.assertEqual(out["reason"], "NO_PREAUTHORIZED_SUCCESSOR")
        self.assertEqual(state["holder"], "agent-3")

    def test_26_replayed_takeover_and_ack_have_no_second_effect(self):
        state = self.armed_shift()
        dead = 1000 + LEASE + 1
        first = se.take_over(state, "agent-2", dead)
        nonce = first["nonce"]
        snap = se.snapshot(state)
        replay = se.take_over(state, "agent-3", dead + LEASE + 1, nonce=nonce)
        self.assertEqual(replay["reason"], "REPLAY")
        self.assertEqual(state, snap)
        self.assertEqual(se.take_over(state, "agent-2", dead + LEASE + 1,
                                      nonce=nonce)["reason"], "SELF_SUCCESSION")
        self.assertEqual(state, snap)
        # re-arming with a used nonce is refused too
        self.assertEqual(se.arm_successor(state, "owner-1", "agent-3", state["generation"],
                                          dead + 1, nonce=nonce)["reason"], "NONCE_ALREADY_USED")
        # replayed handoff ACK after relief
        other = new_shift()
        se.propose_handoff(other, "agent-1", "agent-2", 1001, generation=other["generation"])
        ack = {"kind": "handoff_ack", "generation": 1, "from": "agent-2", "cursor_seq": 0, "in_flight": [],
               "gates": []}
        self.assertTrue(se.accept_handoff(other, ack, 1002)["relieved"])
        gen = other["generation"]
        with self.assertRaises(se.ShiftError) as err:
            se.accept_handoff(other, ack, 1003)
        self.assertEqual(err.exception.code, "NO_PENDING_HANDOFF")
        self.assertEqual(other["generation"], gen)

    def test_27_holder_cannot_be_its_own_successor(self):
        with self.assertRaises(se.ShiftError) as err:
            se.open_shift(shift_id="s", principal="owner-1", scope="x", backlog=None,
                          capacity=1, budget=1, holder="agent-1", supervisor_target=SUPERVISOR,
                          now=0, lease_secs=LEASE, successor_policy={"pre_authorized": "agent-1"})
        self.assertEqual(err.exception.code, "SELF_SUCCESSION")
        state = new_shift()
        self.assertEqual(se.arm_successor(state, "owner-1", "agent-1", 1, 1001)["reason"],
                         "SELF_SUCCESSION")
        self.assertEqual(se.take_over(state, "agent-1", 1000 + LEASE + 1)["reason"],
                         "SELF_SUCCESSION")

    def test_28_only_valid_authority_in_current_generation_can_arm(self):
        state = new_shift()
        self.assertEqual(se.arm_successor(state, "agent-1", "agent-2", 1, 1001)["reason"],
                         "NOT_AUTHORIZED_TO_ARM")
        self.assertEqual(se.arm_successor(state, "owner-1", "agent-2", 0, 1001)["reason"],
                         "STALE_GENERATION")
        self.assertTrue(se.arm_successor(state, "owner-1", "agent-2", 1, 1001)["armed"])
        self.assertEqual(state["continuity"]["mode"], "SUPPORTED")
        self.assertTrue(se.take_over(state, "agent-2", 1000 + LEASE + 1)["taken_over"])
        # re-armed for the new generation, a second succession works exactly once
        self.assertEqual(se.arm_successor(state, "owner-1", "agent-3", 1, 1700)["reason"],
                         "STALE_GENERATION")
        self.assertTrue(se.arm_successor(state, "owner-1", "agent-3", 2, 1700)["armed"])
        dead2 = state["lease"]["expires_at"] + 1
        self.assertTrue(se.take_over(state, "agent-3", dead2)["taken_over"])
        self.assertEqual(state["generation"], 3)

    def test_29_takeover_without_ack_preserves_all_work_and_fences_stale_owner(self):
        state = self.armed_shift()
        se.apply_tick(state, "agent-1", "t1", 1001, generation=state["generation"])
        se.open_event(state, "agent-1", "ev-1", 1002, recipient="owner-1", generation=state["generation"])
        state["in_flight"].append("fix-login-timeout")
        se.set_gate(state, "agent-1", "publish-pricing-page", {"kind": "approval", "state": "pending"}, 1001, generation=state["generation"])
        se.complete_item(state, "agent-1", "fix-login-timeout", author="agent-1",
                         reviewer="agent-9", now=1003, generation=state["generation"])
        se.deliver(state, "agent-1", "fix-login-timeout", recipient="person-1",
                   recipient_kind="human", result_ref="repo/x!13@abc",
                   receipt={"received_by": None}, now=1004, generation=state["generation"])
        state["in_flight"].append("rotate-report-cron")
        keep = {k: se.snapshot(state)[k] for k in
                ("cursor", "processed_events", "pending_events", "in_flight", "gates",
                 "deliveries", "adopted", "reopened", "parked", "effects")}
        udv_before = se.udv_status(state, "fix-login-timeout")
        old_gen = state["generation"]
        dead = 1000 + LEASE + 1
        self.assertTrue(se.take_over(state, "agent-2", dead)["taken_over"])  # no ACK from owner
        for key, value in keep.items():
            self.assertEqual(state[key], value, key)
        self.assertEqual(se.udv_status(state, "fix-login-timeout"), udv_before)
        self.assertFalse(se.lease_valid(state, "agent-1", dead + 1))
        self.assertFalse(se.lease_valid(state, "agent-2", dead + 1, generation=old_gen))
        self.assertEqual(se.authorize_send(state, "agent-1", SUPERVISOR, dead + 1,
                                           generation=old_gen)["reason"], "STALE_GENERATION")
        with self.assertRaises(se.ShiftError):
            se.open_event(state, "agent-1", "ev-2", dead + 1, recipient="owner-1", generation=state["generation"])
        self.assertTrue(se.lease_valid(state, "agent-2", dead + 1, generation=old_gen + 1))


class ReviewThreadInvariants(unittest.TestCase):
    """Regression guards for the PR #605 review threads (defensive, no abuse demo)."""

    def test_30_adopt_rechecks_gate_owner_budget_capacity_before_mutating(self):
        backlog = demo_backlog()
        cases = [
            ("publish-pricing-page", {}, "HUMAN_GATE"),
            ("rotate-report-cron", {}, "IN_FLIGHT_BY_OTHER"),
            ("fix-login-timeout", {"budget": 0}, "BUDGET_EXHAUSTED"),
        ]
        for key, kw, code in cases:
            state = new_shift(**kw)
            before = se.snapshot(state)
            with self.assertRaises(se.ShiftError) as err:
                se.adopt(state, "agent-1", key, backlog, 1001, generation=1)
            self.assertEqual(err.exception.code, code)
            self.assertEqual(state, before, key)
        state = new_shift(capacity=1)
        state["in_flight"].append("other")
        before = se.snapshot(state)
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1001, generation=1)
        self.assertEqual(err.exception.code, "CAPACITY_FULL")
        self.assertEqual(state, before)
        owned = se.normalize_backlog([{"connector": "c", "status": "ok", "items": [
            {"ref": "R-1", "intent_key": "k", "assignee": "agent-9"}]}])
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(new_shift(), "agent-1", "k", owned, 1001, generation=1)
        self.assertEqual(err.exception.code, "OWNED_BY_OTHER")
        gated = new_shift()
        se.set_gate(gated, "agent-1", "fix-login-timeout",
                    {"kind": "approval", "by": "owner-1", "state": "pending"}, 1001, generation=1)
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(gated, "agent-1", "fix-login-timeout", backlog, 1002, generation=1)
        self.assertEqual(err.exception.code, "HUMAN_GATE")

    def test_31_every_mutator_needs_current_lease_and_generation(self):
        backlog = demo_backlog()
        calls = {
            "renew_lease": lambda s, a, g: se.renew_lease(s, a, 1001, generation=g),
            "apply_tick": lambda s, a, g: se.apply_tick(s, a, "t9", 1001, generation=g),
            "record_signal": lambda s, a, g: se.record_signal(s, a, "tick", "e9", {}, 1001,
                                                              generation=g),
            "open_event": lambda s, a, g: se.open_event(s, a, "ev9", 1001, recipient="owner-1",
                                                        generation=g),
            "select_next": lambda s, a, g: se.select_next(s, backlog, a, 1001, generation=g),
            "adopt": lambda s, a, g: se.adopt(s, a, "fix-login-timeout", backlog, 1001,
                                              generation=g),
            "mark_backlog_exhausted": lambda s, a, g: se.mark_backlog_exhausted(s, a, 1001,
                                                                                generation=g),
            "set_gate": lambda s, a, g: se.set_gate(s, a, "k", {"kind": "veto", "by": "o"},
                                                    1001, generation=g),
            "complete_item": lambda s, a, g: se.complete_item(s, a, "k", author="a",
                                                              reviewer="b", now=1001,
                                                              generation=g),
            "propose_handoff": lambda s, a, g: se.propose_handoff(s, a, "agent-2", 1001,
                                                                  generation=g),
            "deliver": lambda s, a, g: se.deliver(s, a, "k", recipient="p", recipient_kind="human",
                                                  result_ref="r", receipt={}, now=1001,
                                                  generation=g),
            "record_receipt": lambda s, a, g: se.record_receipt(s, a, "k", {}, 1001,
                                                                generation=g),
            "record_feedback": lambda s, a, g: se.record_feedback(s, a, "k", {}, 1001,
                                                                  generation=g),
            "assess_effect": lambda s, a, g: se.assess_effect(s, a, "op", {}, 1001, generation=g),
            "raise_incident": lambda s, a, g: se.raise_incident(s, a, "inc", 1001, generation=g),
            "decide_route": lambda s, a, g: se.decide_route(s, a, "d", {}, 1001, generation=g),
            "start_item": lambda s, a, g: se.start_item(s, a, "fix-login-timeout", backlog, 1001,
                                                        generation=g),
            "record_spend": lambda s, a, g: se.record_spend(s, a, 1.0, 1001, generation=g),
            "arm_heartbeat": lambda s, a, g: se.arm_heartbeat(
                s, a, 1001, generation=g, transport="omp:background-job", job_ref="bg_1",
                fires_at=1100, bound_target=SUPERVISOR),
        }
        for name, call in calls.items():
            for actor, gen, code in (("agent-1", None, "GENERATION_REQUIRED"),
                                     ("agent-1", 0, "STALE_GENERATION"),
                                     ("agent-2", 1, "LEASE_INVALID")):
                state = new_shift()
                before = se.snapshot(state)
                with self.assertRaises(se.ShiftError, msg=name) as err:
                    call(state, actor, gen)
                self.assertEqual(err.exception.code, code, name)
                self.assertEqual(state, before, name)

    def test_32_gate_changes_only_by_its_decider(self):
        state = new_shift()
        se.set_gate(state, "agent-1", "k", {"kind": "veto", "by": "owner-1", "state": "vetoed"},
                    1001, generation=1)
        with self.assertRaises(se.ShiftError) as err:
            se.set_gate(state, "agent-1", "k", {"kind": "veto", "state": "granted",
                                                "decided_by": "agent-1"}, 1002, generation=1)
        self.assertEqual(err.exception.code, "GATE_DECIDER_MISMATCH")
        self.assertEqual(state["gates"]["k"]["state"], "vetoed")
        se.set_gate(state, "agent-1", "k", {"kind": "veto", "state": "granted",
                                            "decided_by": "owner-1"}, 1003, generation=1)
        self.assertEqual(state["gates"]["k"]["by"], "owner-1")

    def test_33_stale_handoff_ack_refused_and_in_flight_preserved(self):
        backlog = demo_backlog()
        state = new_shift()
        se.propose_handoff(state, "agent-1", "agent-2", 1001, generation=1)
        old_ack = {"kind": "handoff_ack", "generation": 1, "from": "agent-2", "cursor_seq": 0,
                   "in_flight": [], "gates": []}
        se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002, generation=1)
        out = se.accept_handoff(state, old_ack, 1003)
        self.assertEqual(out["reason"], "PROPOSAL_STALE_REACK")
        self.assertEqual(state["holder"], "agent-1")
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        new_ack = dict(old_ack, in_flight=["fix-login-timeout"])
        wrong_gen = dict(new_ack, generation=7)
        self.assertEqual(se.accept_handoff(state, wrong_gen, 1004)["reason"],
                         "ACK_MISMATCH_GENERATION")
        self.assertEqual(state["holder"], "agent-1")
        self.assertTrue(se.accept_handoff(state, new_ack, 1004)["relieved"])
        self.assertEqual(state["in_flight"], ["fix-login-timeout"])
        self.assertEqual(state["holder"], "agent-2")

    def _delivered(self, received):
        state = new_shift()
        se.complete_item(state, "agent-1", "k", author="agent-1", reviewer="agent-2", now=1001,
                         generation=1)
        se.deliver(state, "agent-1", "k", recipient="person-1", recipient_kind="human",
                   result_ref="r1", receipt={"received_by": "person-1" if received else None},
                   now=1002, generation=1)
        return state

    def test_34_late_receipt_recorded_without_resending(self):
        state = self._delivered(received=False)
        self.assertEqual(se.record_receipt(state, "agent-1", "k", {"received_by": "person-9"},
                                           1003, generation=1)["reason"], "NOT_THE_RECIPIENT")
        out = se.record_receipt(state, "agent-1", "k", {"received_by": "person-1"}, 1004,
                                generation=1)
        self.assertEqual(out, {"recorded": True, "reason": None, "attempts": 1})
        self.assertEqual(state["deliveries"]["k"]["attempts"], 1)
        se.record_feedback(state, "agent-1", "k", {"from": "person-1", "kind": "accept"}, 1005,
                           generation=1)
        self.assertEqual(se.udv_status(state, "k")["udv_percent"], 100)

    def test_35_changed_result_after_acceptance_resets_udv(self):
        state = self._delivered(received=True)
        se.record_feedback(state, "agent-1", "k", {"from": "person-1", "kind": "accept"}, 1003,
                           generation=1)
        self.assertEqual(se.udv_status(state, "k")["udv_percent"], 100)
        se.deliver(state, "agent-1", "k", recipient="person-2", recipient_kind="human",
                   result_ref="r2", receipt={"received_by": "person-2"}, now=1004, generation=1)
        status = se.udv_status(state, "k")
        self.assertEqual((status["udv_percent"], status["satisfaction"],
                          status["technical_verified"]), (0, "unknown", False))
        self.assertEqual(se.record_feedback(state, "agent-1", "k",
                                            {"from": "person-2", "kind": "accept",
                                             "result_ref": "r1"}, 1005,
                                            generation=1)["reason"], "FEEDBACK_FOR_OTHER_RESULT")

    def test_36_event_ack_must_come_from_its_recipient(self):
        state = new_shift()
        se.open_event(state, "agent-1", "ev-1", 1001, recipient="owner-1", generation=1)
        out = se.conclude_event(state, "agent-1", "ev-1", {"event_id": "ev-1", "from": "agent-7"},
                                1002, generation=1)
        self.assertEqual(out["reason"], "ACK_NOT_FROM_RECIPIENT")
        self.assertIn("ev-1", state["pending_events"])

    def test_37_wakeup_bound_to_other_target_is_degraded(self):
        state = new_shift(capabilities={"wakeup_transport": "host-push",
                                        "bound_target": "supervisor://other"})
        self.assertEqual((state["wakeup"]["mode"], state["wakeup"]["reason"]),
                         ("DEGRADED", "BOUND_TARGET_MISMATCH"))


class DecisionLenses(unittest.TestCase):
    """Lens addendum: behaviour at the decision point, not text."""

    def test_38_incident_preempts_backlog_and_cursor_is_unchanged(self):
        backlog = demo_backlog()
        state = new_shift()
        se.apply_tick(state, "agent-1", "t1", 1001, generation=1)
        se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1002, generation=1)
        cursor = dict(state["cursor"])
        in_flight = list(state["in_flight"])
        se.raise_incident(state, "agent-1", "inc-1", 1003, generation=1)
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1004, generation=1),
                         {"action": "handle_incident", "incident": "inc-1"})
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "other", se.normalize_backlog([
                {"connector": "c", "status": "ok",
                 "items": [{"ref": "R", "intent_key": "other"}]}]), 1005, generation=1)
        self.assertEqual(err.exception.code, "INCIDENT_ACTIVE")
        se.resolve_incident(state, "agent-1", "inc-1", 1006, generation=1)
        self.assertEqual(state["cursor"], cursor)
        self.assertEqual(state["in_flight"], in_flight)
        self.assertNotEqual(se.select_next(state, backlog, "agent-1", 1007,
                                           generation=1)["action"], "handle_incident")

    def test_39_repeated_source_does_not_change_decision(self):
        state = new_shift()
        ev = {"source": "ci/run-7", "digest": "aa11", "supports": "ship"}
        self.assertTrue(se.decide_route(state, "agent-1", "d1", ev, 1001, generation=1)["changed"])
        echo = dict(ev, supports="rollback")  # same source and digest, louder claim
        for t in (1002, 1003, 1004):
            out = se.decide_route(state, "agent-1", "d1", echo, t, generation=1)
            self.assertEqual((out["changed"], out["reason"]), (False, "REPEATED_EVIDENCE"))
        self.assertEqual(state["decisions"]["d1"]["choice"], "ship")
        self.assertEqual(len(state["decisions"]["d1"]["changes"]), 1)

    def test_40_new_evidence_changes_decision_and_records_the_lens(self):
        state = new_shift()
        se.decide_route(state, "agent-1", "d1", {"source": "ci/run-7", "digest": "aa11",
                                                 "supports": "ship"}, 1001, generation=1)
        out = se.decide_route(state, "agent-1", "d1",
                              {"source": "ci/run-8", "digest": "bb22", "supports": "rollback",
                               "lens": "doubting"}, 1002, generation=1)
        self.assertEqual((out["changed"], out["choice"]), (True, "rollback"))
        self.assertEqual(state["decisions"]["d1"]["changes"][-1]["lens"], "doubting")
        same = se.decide_route(state, "agent-1", "d1", {"source": "ci/run-9", "digest": "cc33",
                                                        "supports": "rollback", "lens": "x"},
                               1003, generation=1)
        self.assertEqual(same["reason"], "SAME_CONCLUSION")
        self.assertEqual(len(state["decisions"]["d1"]["changes"]), 2)  # no-op lens not logged

    def test_41_received_without_satisfaction_has_no_udv(self):
        state = new_shift()
        se.complete_item(state, "agent-1", "k", author="agent-1", reviewer="agent-2", now=1001,
                         generation=1)
        se.deliver(state, "agent-1", "k", recipient="person-1", recipient_kind="human",
                   result_ref="r1", receipt={"received_by": "person-1"}, now=1002, generation=1)
        status = se.udv_status(state, "k")
        self.assertEqual((status["technical_verified"], status["delivered_to_recipient"],
                          status["udv_percent"], status["pending"]),
                         (True, True, 0, "SATISFACTION_UNKNOWN"))

    def test_42_no_backlog_never_invents_an_item(self):
        state = new_shift()
        empty = se.normalize_backlog([{"connector": "c", "status": "empty", "items": []}])
        before = se.snapshot(state)
        pick = se.select_next(state, empty, "agent-1", 1001, generation=1)
        self.assertEqual((pick["action"], pick["reason"]), ("wait", "NO_ELIGIBLE_ITEM"))
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "made-up-need", empty, 1002, generation=1)
        self.assertEqual(err.exception.code, "UNKNOWN_ITEM")
        self.assertEqual(state, before)

    def test_43_stop_or_revocation_beats_everything(self):
        backlog = demo_backlog()
        for revoke in (False, True):
            state = se.open_shift(shift_id="s", principal="owner-1", scope="x", backlog=None,
                                  capacity=2, budget=5, holder="agent-1",
                                  supervisor_target=SUPERVISOR, now=1000, lease_secs=LEASE,
                                  successor_policy={"pre_authorized": "agent-2"})
            se.raise_incident(state, "agent-1", "inc-1", 1001, generation=1)
            se.propose_handoff(state, "agent-1", "agent-2", 1002, generation=1)
            se.stop_shift(state, "owner-1", 1003, revoke=revoke)
            for call in (lambda: se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1004,
                                          generation=1),
                         lambda: se.resolve_incident(state, "agent-1", "inc-1", 1004,
                                                     generation=1),
                         lambda: se.decide_route(state, "agent-1", "d", {"source": "s",
                                                 "digest": "d", "supports": "x"}, 1004,
                                                 generation=1),
                         lambda: se.renew_lease(state, "agent-1", 1004, generation=1)):
                with self.assertRaises(se.ShiftError):
                    call()
            self.assertEqual(se.take_over(state, "agent-2", 5000)["reason"], "SHIFT_NOT_ACTIVE")
            self.assertEqual(se.arm_successor(state, "owner-1", "agent-3", 1, 1005)["reason"],
                             "SHIFT_NOT_ACTIVE")
            with self.assertRaises(se.ShiftError):
                se.accept_handoff(state, {"kind": "handoff_ack", "generation": 1,
                                          "from": "agent-2", "cursor_seq": 0, "in_flight": [],
                                          "gates": []}, 1006)
            self.assertEqual(state["holder"], "agent-1")
            self.assertFalse(se.authorize_send(state, "agent-1", SUPERVISOR, 1006)["allowed"])


class FinalWaveThreads(unittest.TestCase):
    """Regression guards for the last review wave on PR #605."""

    def test_44_granted_gate_allows_adoption_pending_still_blocks(self):
        def backlog(gate):
            return se.normalize_backlog([{"connector": "c", "status": "ok", "items": [
                {"ref": "R-1", "intent_key": "k", "gate": gate}]}])
        state = new_shift()
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "k", backlog({"kind": "approval", "by": "owner-1",
                                                     "state": "pending"}), 1001, generation=1)
        self.assertEqual(err.exception.code, "HUMAN_GATE")
        _, ok = se.adopt(state, "agent-1", "k", backlog({"kind": "approval", "by": "owner-1",
                                                         "state": "granted"}), 1002, generation=1)
        self.assertTrue(ok)
        # connector still shows pending, but the decider granted it through set_gate
        state = new_shift()
        pending = backlog({"kind": "approval", "by": "owner-1", "state": "pending"})
        se.set_gate(state, "agent-1", "k", {"kind": "approval", "by": "owner-1",
                                            "state": "pending"}, 1001, generation=1)
        se.set_gate(state, "agent-1", "k", {"kind": "approval", "state": "granted",
                                            "decided_by": "owner-1"}, 1002, generation=1)
        self.assertEqual(se.select_next(state, pending, "agent-1", 1003,
                                        generation=1)["action"], "adopt")
        _, ok = se.adopt(state, "agent-1", "k", pending, 1004, generation=1)
        self.assertTrue(ok)

    def test_45_conflicting_owners_make_item_ineligible_in_any_order(self):
        a = {"connector": "a", "status": "ok",
             "items": [{"ref": "A-1", "intent_key": "k", "in_flight_by": "agent-1"}]}
        b = {"connector": "b", "status": "ok",
             "items": [{"ref": "B-1", "intent_key": "k", "in_flight_by": "agent-9"}]}
        for order in ([a, b], [b, a]):
            backlog = se.normalize_backlog(order)
            self.assertEqual(backlog["items"]["k"]["conflicts"],
                             [{"field": "in_flight_by", "values": ["agent-1", "agent-9"]}])
            state = new_shift()
            before = se.snapshot(state)
            pick = se.select_next(state, backlog, "agent-1", 1001, generation=1)
            self.assertEqual(pick["action"], "wait")
            with self.assertRaises(se.ShiftError) as err:
                se.adopt(state, "agent-1", "k", backlog, 1002, generation=1)
            self.assertIn(err.exception.code, ("OWNERSHIP_CONFLICT", "IN_FLIGHT_BY_OTHER"))
            self.assertEqual(state, before)

    def test_46_replayed_rejection_reopens_once(self):
        state = new_shift(capacity=2)
        se.complete_item(state, "agent-1", "k", author="agent-1", reviewer="agent-2", now=1001,
                         generation=1)
        se.deliver(state, "agent-1", "k", recipient="person-1", recipient_kind="human",
                   result_ref="r1", receipt={"received_by": "person-1"}, now=1002, generation=1)
        reject = {"from": "person-1", "kind": "reject", "note": "still broken"}
        self.assertTrue(se.record_feedback(state, "agent-1", "k", reject, 1003,
                                           generation=1)["recorded"])
        for t in (1004, 1005):
            out = se.record_feedback(state, "agent-1", "k", reject, t, generation=1)
            self.assertEqual(out["reason"], "DUPLICATE_REJECTION")
        self.assertEqual(len(state["reopened"]), 1)
        self.assertEqual(state["in_flight"], ["k#reopen-1"])
    def test_47_every_blocking_gate_survives_the_merge_in_any_order(self):
        issue = {"connector": "issues", "status": "ok", "items": [
            {"ref": "I-1", "intent_key": "k",
             "gate": {"kind": "approval", "by": "owner-1", "state": "granted"}}]}
        review = {"connector": "reviews", "status": "ok", "items": [
            {"ref": "P-1", "intent_key": "k",
             "gate": {"kind": "veto", "by": "owner-2", "state": "pending"}}]}
        for order in ([issue, review], [review, issue]):
            backlog = se.normalize_backlog(order)
            self.assertEqual(len(backlog["items"]["k"]["gates"]), 2)
            state = new_shift()
            before = se.snapshot(state)
            self.assertEqual(se.select_next(state, backlog, "agent-1", 1001,
                                            generation=1)["action"], "wait")
            with self.assertRaises(se.ShiftError) as err:
                se.adopt(state, "agent-1", "k", backlog, 1002, generation=1)
            self.assertEqual(err.exception.code, "HUMAN_GATE")
            self.assertEqual(state, before)
        # one decider's own record does not clear another decider's open gate
        state = new_shift()
        backlog = se.normalize_backlog([issue, review])
        se.set_gate(state, "agent-1", "k", {"kind": "approval", "by": "owner-1",
                                            "state": "granted", "decided_by": "owner-1"},
                    1001, generation=1)
        with self.assertRaises(se.ShiftError):
            se.adopt(state, "agent-1", "k", backlog, 1002, generation=1)

    def test_48_delivery_dedupes_against_every_result_already_sent(self):
        state = new_shift()
        common = {"recipient": "person-1", "recipient_kind": "human",
                  "receipt": {"received_by": "person-1"}, "generation": 1}
        self.assertTrue(se.deliver(state, "agent-1", "k", result_ref="r1", now=1001,
                                   **common)["sent"])
        self.assertTrue(se.deliver(state, "agent-1", "k", result_ref="r2", now=1002,
                                   **common)["sent"])
        se.record_feedback(state, "agent-1", "k", {"from": "person-1", "kind": "accept"},
                           1003, generation=1)
        current = se.snapshot(state)["deliveries"]["k"]
        replay = se.deliver(state, "agent-1", "k", result_ref="r1", now=1004, **common)
        self.assertEqual(replay, {"sent": False, "reason": "NO_RESEND_SAME_RESULT"})
        self.assertEqual(state["deliveries"]["k"], current)  # current evidence untouched
        self.assertEqual(state["deliveries"]["k"]["attempts"], 2)


class JudgeFindings(unittest.TestCase):
    """Regression guards for the judge's findings on 302976ec (A1, A4, A5)."""

    def pending_connector(self):
        return se.normalize_backlog([{"connector": "c", "status": "ok", "items": [
            {"ref": "R-1", "intent_key": "k",
             "gate": {"kind": "approval", "by": "owner-1", "state": "pending"}}]}])

    def test_61_holder_never_grants_a_human_gate(self):
        backlog = self.pending_connector()
        state = new_shift()
        for gate, code in (
                ({"kind": "approval", "by": "owner-1", "state": "granted"},
                 "GATE_DECIDER_MISMATCH"),
                ({"kind": "approval", "by": "agent-1", "state": "granted",
                  "decided_by": "agent-1"}, "SELF_GRANT_REFUSED"),
                ({"kind": "approval", "by": "owner-1", "state": "granted",
                  "decided_by": "agent-1"}, "GATE_DECIDER_MISMATCH")):
            before = se.snapshot(state)
            with self.assertRaises(se.ShiftError) as err:
                se.set_gate(state, "agent-1", "k", gate, 1001, generation=1)
            self.assertEqual(err.exception.code, code)
            self.assertEqual(state, before)
        # a recorded grant from a DIFFERENT decider never clears the connector's pending gate
        se.set_gate(state, "agent-1", "k", {"kind": "approval", "by": "owner-9",
                                            "state": "granted", "decided_by": "owner-9"},
                    1002, generation=1)
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "k", backlog, 1003, generation=1)
        self.assertEqual(err.exception.code, "HUMAN_GATE")

    def test_62_linked_issue_and_pr_with_different_keys_are_one_item(self):
        backlog = se.normalize_backlog([
            {"connector": "issues", "status": "ok",
             "items": [{"ref": "repo/x#12", "intent_key": "fix-timeout", "links": ["repo/x!13"]}]},
            {"connector": "reviews", "status": "ok",
             "items": [{"ref": "repo/x!13", "intent_key": "pr-13-timeout"}]}])
        self.assertEqual(list(backlog["items"]), ["fix-timeout"])
        self.assertEqual(sorted(backlog["items"]["fix-timeout"]["refs"]),
                         ["repo/x!13", "repo/x#12"])
        state = new_shift()
        _, first = se.adopt(state, "agent-1", "fix-timeout", backlog, 1001, generation=1)
        _, again = se.adopt(state, "agent-1", "pr-13-timeout", backlog, 1002, generation=1)
        self.assertEqual((first, again, len(state["adopted"])), (True, False, 1))

    def test_63_same_digest_under_another_source_name_is_an_echo(self):
        state = new_shift()
        se.decide_route(state, "agent-1", "d", {"source": "ci/run-7", "digest": "aa11",
                                                "supports": "ship"}, 1001, generation=1)
        out = se.decide_route(state, "agent-1", "d", {"source": "mirror/run-7", "digest": "aa11",
                                                      "supports": "rollback"}, 1002, generation=1)
        self.assertEqual((out["changed"], out["reason"]), (False, "REPEATED_EVIDENCE"))
        self.assertEqual(state["decisions"]["d"]["choice"], "ship")


class ConflictResolver(unittest.TestCase):

    def test_64_technical_conflict_settled_by_verified_evidence_not_majority(self):
        state = new_shift()
        out = se.resolve_conflict(
            state, "agent-1", "cf-1",
            facts=["tracker A says done", "tracker B says open"],
            authorities={"repo": "team-x"},
            alternatives=[{"id": "done"}, {"id": "open"}],
            evidence=[{"supports": "done", "source": "a", "digest": "d1", "verified": False},
                      {"supports": "done", "source": "b", "digest": "d2", "verified": False},
                      {"supports": "done", "source": "c", "digest": "d3", "verified": False},
                      {"supports": "open", "source": "ci", "digest": "d9", "verified": True},
                      {"supports": "done", "source": "late", "digest": "d4", "verified": False}],
            reversible=True, review_criterion="re-check when CI on main changes",
            now=1001, generation=1)
        self.assertEqual((out["status"], out["decision"]), ("RESOLVED", "open"))
        record = state["conflict_log"]["cf-1"]
        for field in ("facts", "authorities", "alternatives", "reversible", "decision",
                      "review_criterion"):
            self.assertIn(field, record)
        self.assertEqual(record["evidence"], ["d9"])
        split = se.resolve_conflict(
            state, "agent-1", "cf-2", facts=[], authorities={"repo": "team-x"},
            alternatives=[{"id": "a"}, {"id": "b"}],
            evidence=[{"supports": "a", "digest": "x1", "verified": True},
                      {"supports": "b", "digest": "x2", "verified": True}],
            reversible=True, review_criterion="new evidence", now=1002, generation=1)
        self.assertEqual((split["status"], split["decision"]), ("OPEN", None))

    def test_65_authority_conflict_parks_only_that_effect(self):
        backlog = demo_backlog()
        state = new_shift()
        out = se.resolve_conflict(
            state, "agent-1", "cf-3", facts=["two owners claim the release"],
            authorities={"tracker-a": "owner-1", "tracker-b": "owner-2"},
            alternatives=[{"id": "ship"}, {"id": "hold"}],
            evidence=[{"supports": "ship", "digest": "v1", "verified": True}],
            reversible=False, review_criterion="owners agree", now=1001, generation=1)
        self.assertEqual((out["status"], out["reason"]), ("PARKED", "AUTHORITY_CONFLICT"))
        self.assertEqual([p["operation"] for p in state["parked"]], ["cf-3"])
        human = se.resolve_conflict(
            state, "agent-1", "cf-4", facts=[], authorities={"org": "owner-1"},
            alternatives=[{"id": "grant", "needs_human_authorization": True}, {"id": "deny"}],
            evidence=[{"supports": "grant", "digest": "v2", "verified": True}],
            reversible=False, review_criterion="owner decides", now=1002, generation=1)
        self.assertEqual(human["reason"], "HUMAN_AUTHORIZATION_NOT_ARBITRATED")
        self.assertIsNone(human["decision"])
        # the rest of the turn continues
        self.assertEqual(state["status"], se.ACTIVE)
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1003,
                                        generation=1)["action"], "adopt")


class ContractEdges(unittest.TestCase):

    def test_backlog_given_blocks_adoption_until_exhausted(self):
        backlog = demo_backlog()
        state = new_shift(backlog="list://owner-1/tonight")
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1001, generation=state["generation"])
        self.assertEqual(err.exception.code, "BACKLOG_GIVEN")
        se.mark_backlog_exhausted(state, "agent-1", 1002, generation=state["generation"])
        _, adopted = se.adopt(state, "agent-1", "fix-login-timeout", backlog, 1003, generation=state["generation"])
        self.assertTrue(adopted)

    def test_budget_and_capacity_stop_new_work(self):
        backlog = demo_backlog()
        state = new_shift(budget=0)
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1001, generation=state["generation"])["reason"],
                         "BUDGET_EXHAUSTED")
        state = new_shift(capacity=1)
        state["in_flight"].append("other")
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1001, generation=state["generation"])["reason"],
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
        optional = {"backlog_exhausted"}
        self.assertEqual(sorted(set(schema["properties"]) - optional), sorted(state))
        armed = se.open_shift(shift_id="s", principal="p", scope="x", backlog=None, capacity=1,
                              budget=1, holder="a", supervisor_target="t", now=0, lease_secs=1,
                              successor_policy={"pre_authorized": "b"})
        self.assertEqual(sorted(schema["properties"]["successor_policy"]["required"]),
                         sorted(armed["successor_policy"]))
        self.assertEqual(sorted(schema["properties"]["continuity"]["required"]),
                         sorted(armed["continuity"]))
        self.assertEqual(sorted(schema["properties"]["wakeup"]["required"]),
                         sorted(set(state["wakeup"]) - {"transport", "bound_target"}))
        # regenerating the example from the engine must give the committed file
        regen = new_shift(now=1000)
        regen["scope"] = example["scope"]
        se.apply_tick(regen, "agent-1", "tick-1", 1001, generation=regen["generation"])
        self.assertEqual(json.loads(json.dumps(regen)), example)
        self.assertEqual(schema["properties"]["schema"]["const"], se.SCHEMA)
        self.assertEqual(example["mantras"], list(se.DEFAULT_MANTRAS))

    def test_open_shift_refuses_missing_fields(self):
        with self.assertRaises(se.ShiftError) as err:
            se.open_shift(shift_id="s", principal="", scope="x", backlog=None, capacity=1,
                          budget=1, holder="a", supervisor_target="t", now=0, lease_secs=1)
        self.assertEqual(err.exception.code, "MISSING_FIELD")


OMP_SESSION = "omp:session-1"
DEADLINE = 1000 + 4 * LEASE


def given_backlog():
    """The principal's explicit list, normalized like any connector (night 2026-11-25 shape)."""
    return se.normalize_backlog([{"connector": "operator-backlog", "kind": "operator",
                                  "status": "ok", "items": [
        {"ref": "org/a#41", "intent_key": "a-41",
         "gate": {"kind": "approval", "by": "owner-1", "state": "pending"}},
        {"ref": "org/b#517", "intent_key": "b-517", "gut": 9},
        {"ref": "org/b#516", "intent_key": "b-516", "gut": 7},
        {"ref": "org/c#423", "intent_key": "c-423", "in_flight_by": "agent-other"},
        {"ref": "org/d#8", "intent_key": "d-8", "gut": 3}]}])


def night_shift(**over):
    """Intake of the night that delivered 0 items: given list, USD + deadline, OMP host."""
    args = dict(shift_id="night-1", principal="owner-1",
                scope=["org/a", "org/b", "org/c", "org/d"], backlog="file://opening.md#2",
                capacity=2, budget={"currency": "USD", "amount": 50, "freeze_at": 40,
                                    "deadline": DEADLINE},
                holder="agent-1", supervisor_target=OMP_SESSION, now=1000, lease_secs=LEASE,
                capabilities={"heartbeat_transport": "omp:background-job"})
    args.update(over)
    return se.open_shift(**args)


def arm(state, now, fires_at, job_ref="bg_1", bound_target=OMP_SESSION):
    return se.arm_heartbeat(state, "agent-1", now, generation=state["generation"],
                            transport="omp:background-job", job_ref=job_ref,
                            fires_at=fires_at, bound_target=bound_target)


class WorkLoop(unittest.TestCase):
    """Postmortem night-20261125: the shift opened, then nothing was worked until morning."""

    def test_92_given_backlog_items_start_in_flight_with_the_adopt_checks(self):  # H3
        backlog = given_backlog()
        state = night_shift()
        se.record_spend(state, "agent-1", 149.15, 1000, generation=1)
        pick = se.select_next(state, backlog, "agent-1", 1001, generation=1)
        self.assertEqual((pick["action"], pick["intent_key"]), ("start", "b-517"))
        self.assertEqual({s["intent_key"]: s["why"] for s in pick["skipped"]},
                         {"a-41": "HUMAN_GATE", "c-423": "IN_FLIGHT_BY_OTHER"})
        state, started = se.start_item(state, "agent-1", "b-517", backlog, 1002, generation=1)
        state, again = se.start_item(state, "agent-1", "b-517", backlog, 1003, generation=1)
        self.assertEqual((started, again), (True, False))  # a replay adds nothing
        self.assertEqual(state["in_flight"], ["b-517"])
        self.assertEqual(state["adopted"]["b-517"]["via"], "backlog")
        for key, code in (("a-41", "HUMAN_GATE"), ("c-423", "IN_FLIGHT_BY_OTHER"),
                          ("made-up", "UNKNOWN_ITEM")):
            before = se.snapshot(state)
            with self.assertRaises(se.ShiftError) as err:
                se.start_item(state, "agent-1", key, backlog, 1004, generation=1)
            self.assertEqual(err.exception.code, code)
            self.assertEqual(state, before)
        se.start_item(state, "agent-1", "b-516", backlog, 1005, generation=1)
        with self.assertRaises(se.ShiftError) as err:
            se.start_item(state, "agent-1", "d-8", backlog, 1006, generation=1)
        self.assertEqual(err.exception.code, "CAPACITY_FULL")
        with self.assertRaises(se.ShiftError) as err:  # adoption stays for "no list given"
            se.adopt(state, "agent-1", "d-8", backlog, 1006, generation=1)
        self.assertEqual(err.exception.code, "BACKLOG_GIVEN")
        with self.assertRaises(se.ShiftError) as err:
            se.start_item(new_shift(), "agent-1", "fix-login-timeout", demo_backlog(), 1001,
                          generation=1)
        self.assertEqual(err.exception.code, "NO_BACKLOG_GIVEN")

    def test_93_money_budget_is_a_measured_delta_and_freezes_at_the_threshold(self):  # H4
        backlog = given_backlog()
        state = night_shift()
        self.assertEqual(se.select_next(state, backlog, "agent-1", 1001, generation=1)["reason"],
                         "SPEND_NOT_MEASURED")  # fail closed until a baseline exists
        with self.assertRaises(se.ShiftError) as err:
            se.start_item(state, "agent-1", "b-517", backlog, 1001, generation=1)
        self.assertEqual(err.exception.code, "SPEND_NOT_MEASURED")
        out = se.record_spend(state, "agent-1", 149.15, 1002, generation=1)
        self.assertEqual((out["recorded"], out["spent"]), (True, 0))
        self.assertEqual(state["budget"]["money"]["baseline"], 149.15)
        se.start_item(state, "agent-1", "b-517", backlog, 1003, generation=1)
        self.assertEqual(state["budget"]["spent"], 1)  # the adoption count is still kept
        self.assertAlmostEqual(se.record_spend(state, "agent-1", 160.32, 1004,
                                               generation=1)["spent"], 11.17)
        self.assertTrue(state["admission"]["open"])
        out = se.record_spend(state, "agent-1", 189.15, 1005, generation=1)  # +40 = threshold
        self.assertEqual(out["cutoff"], "SPEND_CAP_REACHED")
        self.assertEqual(state["admission"], {"open": False, "reason": "SPEND_CAP_REACHED"})
        with self.assertRaises(se.ShiftError) as err:
            se.start_item(state, "agent-1", "b-516", backlog, 1006, generation=1)
        self.assertEqual(err.exception.code, "ADMISSION_FROZEN")
        self.assertEqual(se.close_at_cutoff(state, "agent-1", 1007, generation=1)["reason"],
                         "SPEND_CAP_REACHED")
        # a meter that goes backwards is another source: fail closed, never a refund
        other = night_shift()
        se.record_spend(other, "agent-1", 149.15, 1001, generation=1)
        out = se.record_spend(other, "agent-1", 12.0, 1002, generation=1)
        self.assertEqual((out["recorded"], out["reason"]),
                         (False, "SPEND_MEASUREMENT_INCONSISTENT"))
        self.assertEqual(other["admission"]["reason"], "SPEND_MEASUREMENT_INCONSISTENT")
        # a measurement older than one lease is stale: no new work on it
        stale = night_shift()
        se.record_spend(stale, "agent-1", 149.15, 1001, generation=1)
        se.renew_lease(stale, "agent-1", 1500, generation=1)
        self.assertEqual(se.select_next(stale, backlog, "agent-1", 1602, generation=1)["reason"],
                         "SPEND_MEASUREMENT_STALE")
        with self.assertRaises(se.ShiftError) as err:
            se.record_spend(new_shift(), "agent-1", 1.0, 1001, generation=1)
        self.assertEqual(err.exception.code, "NO_MONEY_BUDGET")

    def test_94_deadline_stops_new_work_and_the_holder_closes_at_cutoff(self):  # H4 + H5
        backlog = given_backlog()
        state = night_shift(lease_secs=4 * LEASE)  # the lease reaches the deadline
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        se.start_item(state, "agent-1", "b-517", backlog, 1002, generation=1)
        before = se.snapshot(state)
        with self.assertRaises(se.ShiftError) as err:
            se.close_at_cutoff(state, "agent-1", 1003, generation=1)
        self.assertEqual(err.exception.code, "NOT_AT_CUTOFF")  # an early end is the principal's
        self.assertEqual(state, before)
        se.renew_lease(state, "agent-1", DEADLINE - 100, generation=1)
        se.record_spend(state, "agent-1", 150.0, DEADLINE - 50, generation=1)
        self.assertEqual(se.select_next(state, backlog, "agent-1", DEADLINE,
                                        generation=1)["reason"], "DEADLINE_REACHED")
        with self.assertRaises(se.ShiftError) as err:
            se.start_item(state, "agent-1", "b-516", backlog, DEADLINE, generation=1)
        self.assertEqual(err.exception.code, "DEADLINE_REACHED")
        se.apply_tick(state, "agent-1", "bg_9", DEADLINE + 1, generation=1)
        self.assertEqual(state["admission"], {"open": False, "reason": "DEADLINE_REACHED"})
        for actor, gen, code in (("agent-1", None, "GENERATION_REQUIRED"),
                                 ("agent-1", 0, "STALE_GENERATION"),
                                 ("agent-2", 1, "NOT_THE_HOLDER")):
            with self.assertRaises(se.ShiftError) as err:
                se.close_at_cutoff(state, actor, DEADLINE + 5, generation=gen)
            self.assertEqual(err.exception.code, code)
        out = se.close_at_cutoff(state, "agent-1", DEADLINE + 5, generation=1)
        self.assertEqual(out, {"closed": True, "reason": "DEADLINE_REACHED",
                               "in_flight_left": ["b-517"]})
        self.assertEqual(state["status"], se.STOPPED)
        self.assertEqual(state["stop"], {"kind": "cutoff", "by": "agent-1",
                                         "reason": "DEADLINE_REACHED", "at": DEADLINE + 5,
                                         "in_flight_left": ["b-517"]})
        self.assertFalse(se.lease_valid(state, "agent-1", DEADLINE + 5))
        with self.assertRaises(se.ShiftError) as err:
            se.close_at_cutoff(state, "agent-1", DEADLINE + 6, generation=1)
        self.assertEqual(err.exception.code, "SHIFT_NOT_ACTIVE")
        # the lease lapsed overnight: at the deadline its last holder still closes, only it
        lapsed = night_shift()
        self.assertFalse(se.lease_valid(lapsed, "agent-1", DEADLINE))
        self.assertTrue(se.close_at_cutoff(lapsed, "agent-1", DEADLINE, generation=1)["closed"])
        # a principal stop or revocation stays distinct from a cutoff
        for revoke, kind in ((False, "principal_stop"), (True, "principal_revoke")):
            ended = night_shift()
            se.stop_shift(ended, "owner-1", 1001, revoke=revoke)
            self.assertEqual((ended["stop"]["kind"], ended["stop"]["by"]), (kind, "owner-1"))

    def test_95_a_new_tick_renews_the_lease_a_replay_does_not(self):  # H2
        state = new_shift()
        se.apply_tick(state, "agent-1", "hb-1", 1500, generation=1)
        self.assertEqual(state["lease"]["expires_at"], 1500 + LEASE)
        se.apply_tick(state, "agent-1", "hb-1", 1700, generation=1)  # replay: no effect
        self.assertEqual(state["lease"]["expires_at"], 1500 + LEASE)
        with self.assertRaises(se.ShiftError) as err:  # an expired lease is never revived
            se.apply_tick(state, "agent-1", "hb-2", 1500 + LEASE, generation=1)
        self.assertEqual(err.exception.code, "LEASE_INVALID")

    def test_96_yield_gate_dispatch_first_then_heartbeat_then_idle(self):  # H1 + H2
        backlog = given_backlog()
        state = night_shift()
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        gate = se.may_yield(state, "agent-1", 1001, generation=1, eligible=True)
        self.assertEqual((gate["yield"], gate["next"]), (False, "dispatch"))
        se.start_item(state, "agent-1", "b-517", backlog, 1002, generation=1)
        se.start_item(state, "agent-1", "b-516", backlog, 1003, generation=1)
        gate = se.may_yield(state, "agent-1", 1004, generation=1, eligible=False)
        self.assertEqual((gate["yield"], gate["reason"], gate["next"], gate["fire_by"]),
                         (False, "NO_WAKEUP_ARMED", "arm_heartbeat", 1004 + LEASE / 2))
        for fires_at, code in ((1004, "HEARTBEAT_NOT_IN_FUTURE"),
                               (1004 + LEASE / 2 + 1, "HEARTBEAT_AFTER_HALF_LEASE")):
            before = se.snapshot(state)
            with self.assertRaises(se.ShiftError) as err:
                arm(state, 1004, fires_at)
            self.assertEqual(err.exception.code, code)
            self.assertEqual(state, before)
        arm(state, 1004, 1300)
        self.assertEqual(state["wakeup"]["mode"], "SUPPORTED")  # bound to the exact supervisor
        gate = se.may_yield(state, "agent-1", 1005, generation=1, eligible=False)
        self.assertEqual((gate["yield"], gate["reason"], gate["until"]),
                         (True, "HEARTBEAT_ARMED", 1300))
        self.assertEqual(se.may_yield(state, "agent-1", 1005, generation=1,
                                      eligible=True)["next"], "dispatch")  # work beats idling
        # the heartbeat fires: its tick consumes it, renews the lease and re-measures spend
        se.apply_tick(state, "agent-1", "bg_1", 1300, generation=1, spend_total=151.0)
        self.assertIsNone(state["heartbeat"]["job_ref"])
        self.assertEqual(state["lease"]["expires_at"], 1300 + LEASE)
        self.assertAlmostEqual(state["budget"]["money"]["spent"], 1.85)
        self.assertEqual(se.may_yield(state, "agent-1", 1301, generation=1,
                                      eligible=False)["next"], "arm_heartbeat")
        # an unmeasured money budget is measured before any yield, so no wake can stall on it
        self.assertEqual(se.may_yield(night_shift(), "agent-1", 1001, generation=1,
                                      eligible=False)["next"], "record_spend")
        # near the deadline the next wake is due no later than the deadline itself
        soon = night_shift(budget={"currency": "USD", "amount": 50, "deadline": 1200,
                                   "baseline": 149.15})
        self.assertEqual(se.may_yield(soon, "agent-1", 1001, generation=1,
                                      eligible=False)["fire_by"], 1200)
        self.assertEqual(se.may_yield(soon, "agent-1", 1200, generation=1,
                                      eligible=True)["next"], "close_at_cutoff")
        se.close_at_cutoff(soon, "agent-1", 1200, generation=1)
        self.assertEqual(se.may_yield(soon, "agent-1", 1201, generation=1,
                                      eligible=True)["reason"], "SHIFT_ENDED")
        # bound elsewhere: the holder still wakes, the supervisor wakeup stays DEGRADED
        elsewhere = night_shift()
        se.record_spend(elsewhere, "agent-1", 149.15, 1001, generation=1)
        arm(elsewhere, 1001, 1100, bound_target="omp:other-session")
        self.assertEqual(elsewhere["wakeup"]["reason"], "BOUND_TARGET_MISMATCH")
        self.assertTrue(se.may_yield(elsewhere, "agent-1", 1002, generation=1,
                                     eligible=False)["yield"])
        # a heartbeat never downgrades a wakeup the host already bound to the supervisor
        bound = night_shift(capabilities={"wakeup_transport": "pager",
                                          "bound_target": OMP_SESSION,
                                          "heartbeat_transport": "omp:background-job"})
        arm(bound, 1001, 1100, bound_target="omp:other-session")
        self.assertEqual((bound["wakeup"]["mode"], bound["wakeup"]["transport"]),
                         ("SUPPORTED", "pager"))
        # a host with no self-wakeup may yield, but says so and runs postflight
        bare = night_shift(capabilities=None)
        se.record_spend(bare, "agent-1", 149.15, 1001, generation=1)
        self.assertEqual(se.may_yield(bare, "agent-1", 1001, generation=1, eligible=False),
                         {"yield": True, "reason": "NO_HOST_WAKEUP", "next": "postflight",
                          "fire_by": 1001 + LEASE / 2})
        self.assertEqual(se.may_yield(state, "agent-1", 1301, generation=0,
                                      eligible=True)["reason"], "FENCED")

    def test_97_one_call_intake_takes_the_principal_s_shapes(self):  # H6
        state = night_shift()
        self.assertEqual(state["scope"], ["org/a", "org/b", "org/c", "org/d"])
        self.assertEqual(state["budget"], {
            "limit": None, "spent": 0, "deadline": DEADLINE,
            "money": {"currency": "USD", "limit": 50.0, "freeze_at": 40.0, "baseline": None,
                      "spent": 0.0, "measured_at": None, "source": None,
                      "inconsistent_at": None, "read_failed_at": None}})
        self.assertEqual(new_shift()["budget"],
                         {"limit": 5, "spent": 0, "money": None, "deadline": None})
        for bad, code in ((dict(backlog=[]), "BAD_BACKLOG"), (dict(backlog=""), "BAD_BACKLOG"),
                          (dict(scope=[]), "MISSING_FIELD"),
                          (dict(scope=["org/a", ""]), "MISSING_FIELD"),
                          (dict(budget={}), "MISSING_FIELD"),
                          (dict(budget={"currency": "USD"}), "MISSING_FIELD"),
                          (dict(budget={"amount": 50}), "MISSING_FIELD"),
                          (dict(budget={"currency": "USD", "amount": 50, "freeze_at": 60}),
                           "BAD_BUDGET")):
            with self.assertRaises(se.ShiftError, msg=str(bad)) as err:
                night_shift(**bad)
            self.assertEqual(err.exception.code, code, str(bad))
        measured = night_shift(budget={"currency": "USD", "amount": 50, "baseline": 149.15,
                                       "deadline": DEADLINE})
        self.assertEqual(measured["budget"]["money"]["measured_at"], 1000)  # taken at open
        self.assertEqual(se.select_next(measured, given_backlog(), "agent-1", 1001,
                                        generation=1)["action"], "start")

    def test_98_load_migrates_a_v0_2_0_state_file(self):
        legacy = new_shift()
        for key in ("heartbeat", "stop"):
            legacy.pop(key, None)
        legacy["budget"] = {"limit": 5, "spent": 0}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(legacy, handle)
            state = se.load(path)
        self.assertEqual(sorted(state), sorted(new_shift()))
        self.assertEqual(state["budget"], {"limit": 5, "spent": 0, "money": None,
                                           "deadline": None})
        self.assertIsNone(state["stop"])
        self.assertIsNone(state["heartbeat"]["job_ref"])

    def test_99_incident_replay_the_loop_works_the_night_and_closes_at_cutoff(self):
        """Same intake as night-20261125 (0 items, lease lapsed after 1 h, shift left ACTIVE)."""
        backlog = given_backlog()
        deadline = 11 * 3600
        state = night_shift(now=0, lease_secs=3600, budget={
            "currency": "USD", "amount": 50, "freeze_at": 40, "deadline": deadline})
        se.record_spend(state, "agent-1", 149.15, 1, generation=1)
        now, total, worked, wakes = 2, 149.15, [], 0
        for _ in range(500):
            pick = se.select_next(state, backlog, "agent-1", now, generation=1)
            if pick["action"] == "start":
                se.start_item(state, "agent-1", pick["intent_key"], backlog, now, generation=1)
                worked.append(pick["intent_key"])
                continue
            gate = se.may_yield(state, "agent-1", now, generation=1, eligible=False)
            if gate["next"] == "close_at_cutoff":
                se.close_at_cutoff(state, "agent-1", now, generation=1)
                break
            if gate["next"] == "arm_heartbeat":
                wakes += 1
                arm(state, now, gate["fire_by"], job_ref=f"bg_{wakes}")
                continue
            self.assertEqual(gate["reason"], "HEARTBEAT_ARMED")
            now, total = gate["until"], total + 0.5  # the host wakes the holder; a wake costs
            se.apply_tick(state, "agent-1", f"bg_{wakes}", now, generation=1, spend_total=total)
            for key in list(state["in_flight"]):  # workers finished; a distinct judge reviewed
                se.complete_item(state, "agent-1", key, author="worker", reviewer="judge",
                                 now=now, generation=1)
        else:
            self.fail("the loop never reached the cutoff")
        self.assertEqual(sorted(worked), ["b-516", "b-517", "d-8"])
        self.assertEqual((state["status"], state["stop"]["kind"], state["stop"]["reason"]),
                         (se.STOPPED, "cutoff", "DEADLINE_REACHED"))
        self.assertEqual(wakes, 22)  # one heartbeat per half lease until the deadline
        self.assertLess(state["budget"]["money"]["spent"], 40)


class WorkLoopReviewFindings(unittest.TestCase):
    """PR #618 bot findings (amazon-q, codex, graphify), each fixed and pinned here."""

    def test_103_bad_numbers_and_readings_fail_closed_with_a_contract_error(self):
        for budget in ("five", {"adoptions": "x"}, {"currency": "USD", "amount": "lots"},
                       {"currency": "USD", "amount": float("nan")},
                       {"deadline": float("inf")}):
            with self.assertRaises(se.ShiftError, msg=str(budget)):
                night_shift(budget=budget)
        same = night_shift(budget={"currency": "USD", "amount": 50, "freeze_at": None,
                                   "deadline": DEADLINE})
        self.assertEqual(same["budget"]["money"]["freeze_at"], 50.0)  # None = the amount
        for bad in (float("nan"), float("inf"), -1.0, "n/a"):
            state = night_shift()
            se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
            out = se.record_spend(state, "agent-1", bad, 1002, generation=1)
            self.assertEqual((out["recorded"], out["reason"]),
                             (False, "SPEND_MEASUREMENT_INCONSISTENT"), str(bad))
            self.assertEqual(state["admission"]["reason"], "SPEND_MEASUREMENT_INCONSISTENT")
            self.assertEqual(state["budget"]["money"]["spent"], 0.0)
        legacy = new_shift()
        legacy["schema"] = "other/state@9"
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(legacy, handle)
            with self.assertRaises(se.ShiftError) as err:
                se.load(path)
        self.assertEqual(err.exception.code, "SCHEMA_MISMATCH")

    def test_104_relief_and_takeover_drop_the_previous_holder_s_heartbeat(self):
        state = night_shift()
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        arm(state, 1001, 1200)
        se.propose_handoff(state, "agent-1", "agent-2", 1002, generation=1)
        se.accept_handoff(state, {"kind": "handoff_ack", "from": "agent-2", "generation": 1,
                                  "cursor_seq": 0, "in_flight": [], "gates": []}, 1003)
        self.assertEqual(state["heartbeat"]["job_ref"], None)
        self.assertEqual(state["heartbeat"]["transport"], "omp:background-job")
        self.assertEqual(se.may_yield(state, "agent-2", 1004, generation=2,
                                      eligible=False)["next"], "record_spend")  # its own ledger
        se.record_spend(state, "agent-2", 2.0, 1004, generation=2)
        self.assertEqual(se.may_yield(state, "agent-2", 1004, generation=2,
                                      eligible=False)["next"], "arm_heartbeat")
        lost = night_shift(successor_policy={"pre_authorized": "agent-2"})
        se.record_spend(lost, "agent-1", 149.15, 1001, generation=1)
        arm(lost, 1001, 1200)
        self.assertTrue(se.take_over(lost, "agent-2", 1001 + LEASE + 1)["taken_over"])
        self.assertIsNone(lost["heartbeat"]["job_ref"])

    def test_105_team_admission_respects_frozen_admission_and_unmeasured_spend(self):
        def admit(state):
            return se.admit_member(state, "agent-1", "m1", role="executor",
                                   scope=state["scope"], risk="low", cost=0, now=1002,
                                   generation=1)
        self.assertEqual(admit(night_shift())["reason"], "SPEND_NOT_MEASURED")
        frozen = night_shift()
        se.record_spend(frozen, "agent-1", 149.15, 1001, generation=1)
        frozen["admission"] = {"open": False, "reason": "PREFLIGHT_INCONSISTENT"}
        self.assertEqual(admit(frozen)["reason"], "ADMISSION_FROZEN")
        ok = night_shift()
        se.record_spend(ok, "agent-1", 149.15, 1001, generation=1)
        self.assertTrue(admit(ok)["admitted"])

    def test_117_an_unreadable_ledger_blocks_new_work_until_a_good_reading_never_sticky(self):
        # codex @8bca8951: a None reading must stop new work at once; verdict r2: a failed
        # read is not a contradiction, so it never sticks and never stalls the shift
        state = night_shift()
        money = state["budget"]["money"]
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        se.apply_tick(state, "agent-1", "t1", 1100, generation=1)  # this wake did not measure
        self.assertEqual((state["admission"]["open"], money["measured_at"]), (True, 1001))
        se.apply_tick(state, "agent-1", "t2", 1200, generation=1, spend_total=None)
        self.assertEqual((money["read_failed_at"], money["inconsistent_at"],
                          state["cursor"]["last_event_id"]), (1200, None, "t2"))  # applied whole
        self.assertEqual(se.select_next(state, given_backlog(), "agent-1", 1201,
                                        generation=1)["reason"], "SPEND_NOT_READ")
        gate = se.may_yield(state, "agent-1", 1201, generation=1, eligible=True)
        self.assertEqual((gate["next"], gate["reason"]), ("arm_heartbeat", "SPEND_NOT_READ"))
        se.apply_tick(state, "agent-1", "t3", 1300, generation=1, spend_total=150.0)
        self.assertEqual((money["read_failed_at"], money["spent"]), (None, 0.85))
        self.assertEqual(se.select_next(state, given_backlog(), "agent-1", 1301,
                                        generation=1)["action"], "start")
        plain = night_shift(budget=5)  # no money cap: any reading is refused, like record_spend
        with self.assertRaises(se.ShiftError) as err:
            se.apply_tick(plain, "agent-1", "t1", 1001, generation=1, spend_total=None)
        self.assertEqual(err.exception.code, "NO_MONEY_BUDGET")
        self.assertIsNotNone(se.apply_tick(plain, "agent-1", "t1", 1001, generation=1)[1])


class VerdictFindings(unittest.TestCase):
    """Independent verdict on PR #618 @ced0d710 (findings P1-1 .. P3-8), each pinned here."""

    def test_108_an_unmeasurable_meter_is_a_degraded_exit_never_a_spin(self):  # P1-1
        state = night_shift()
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        se.apply_tick(state, "agent-1", "t1", 1500, generation=1)  # lease renewed, no reading
        arm(state, 1650, 1900)
        # stale meter, nothing eligible, heartbeat armed: yield, the wake re-measures
        self.assertEqual(se.may_yield(state, "agent-1", 1700, generation=1,
                                      eligible=False)["reason"], "HEARTBEAT_ARMED")
        self.assertEqual(se.may_yield(state, "agent-1", 1700, generation=1,
                                      eligible=True)["next"], "record_spend")
        out = se.record_spend(state, "agent-1", 100.0, 1701, generation=1)  # goes down
        self.assertEqual(out["reason"], "SPEND_MEASUREMENT_INCONSISTENT")
        gate = se.may_yield(state, "agent-1", 1702, generation=1, eligible=True)
        self.assertEqual((gate["yield"], gate["reason"], gate["next"], gate["until"]),
                         (True, "SPEND_UNMEASURABLE", "report_degraded", 1900))  # no dispatch
        gate = se.may_yield(state, "agent-1", 1702 + LEASE // 2, generation=1, eligible=False)
        self.assertEqual((gate["yield"], gate["reason"], gate["next"]),
                         (False, "SPEND_UNMEASURABLE", "arm_heartbeat"))  # tick-only, no spin
        self.assertEqual(se.record_spend(state, "agent-1", 200.0, 1703, generation=1)["reason"],
                         "SPEND_UNMEASURABLE")  # sticky until the principal re-baselines
        self.assertEqual(se.select_next(state, given_backlog(), "agent-1", 1704,
                                        generation=1)["reason"], "ADMISSION_FROZEN")

    def test_109_principal_rebaseline_and_a_new_holder_keep_the_spend_counted(self):  # P1-1
        state = night_shift()
        se.record_spend(state, "agent-1", 100.0, 1001, generation=1)
        se.record_spend(state, "agent-1", 110.0, 1002, generation=1)  # spent 10
        se.record_spend(state, "agent-1", 5.0, 1003, generation=1)  # meter reset: unmeasurable
        for by, gen, reason in (("agent-1", 1, "NOT_AUTHORIZED_TO_REBASELINE"),
                                ("owner-1", 0, "STALE_GENERATION")):
            self.assertEqual(se.rebaseline_spend(state, by, 5.0, 1004, generation=gen)["reason"],
                             reason)
        self.assertEqual(se.rebaseline_spend(state, "owner-1", float("nan"), 1004,
                                             generation=1)["reason"],
                         "SPEND_MEASUREMENT_INCONSISTENT")
        out = se.rebaseline_spend(state, "owner-1", 5.0, 1004, generation=1)
        self.assertEqual((out["rebaselined"], out["spent"]), (True, 10.0))  # never a refund
        self.assertEqual(state["admission"], {"open": True, "reason": None})
        self.assertEqual(se.record_spend(state, "agent-1", 20.0, 1005, generation=1)["spent"],
                         25.0)
        se.propose_handoff(state, "agent-1", "agent-2", 1006, generation=1)
        se.accept_handoff(state, {"kind": "handoff_ack", "from": "agent-2", "generation": 1,
                                  "cursor_seq": 0, "in_flight": [], "gates": []}, 1007)
        self.assertEqual(se.select_next(state, given_backlog(), "agent-2", 1008,
                                        generation=2)["reason"], "SPEND_NOT_MEASURED")
        self.assertEqual(se.record_spend(state, "agent-2", 3.0, 1008, generation=2)["spent"],
                         25.0)  # its own ledger: re-baselined, spend kept
        self.assertEqual(se.record_spend(state, "agent-2", 8.0, 1009, generation=2)["spent"],
                         30.0)
        lost = night_shift(successor_policy={"pre_authorized": "agent-2"})
        se.record_spend(lost, "agent-1", 100.0, 1001, generation=1)
        se.record_spend(lost, "agent-1", 104.0, 1002, generation=1)
        self.assertTrue(se.take_over(lost, "agent-2", 1000 + LEASE + 3)["taken_over"])
        self.assertEqual(se.record_spend(lost, "agent-2", 1.0, 1000 + LEASE + 4,
                                         generation=2)["spent"], 4.0)
        self.assertEqual(se.record_spend(lost, "agent-2", 2.5, 1000 + LEASE + 5,
                                         generation=2)["spent"], 5.5)

    def test_110_the_skill_tells_an_omp_holder_to_declare_its_wakeup(self):  # P1-2
        with open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        inputs = text.split("## Inputs", 1)[1].split("## Work loop", 1)[0]
        loop = text.split("## Work loop", 1)[1].split("### Host adapters", 1)[0]
        self.assertIn("| `capabilities` |", inputs)
        self.assertIn('capabilities={"heartbeat_transport": "omp:background-job"}', loop)
        self.assertIn("never postflight", loop)
        bare = night_shift(capabilities=None)  # an OMP holder that forgot to declare it
        se.record_spend(bare, "agent-1", 149.15, 1001, generation=1)
        gate = se.may_yield(bare, "agent-1", 1001, generation=1, eligible=False)
        self.assertEqual((gate["reason"], gate["fire_by"]), ("NO_HOST_WAKEUP", 1001 + LEASE / 2))
        arm(bare, 1001, gate["fire_by"])
        self.assertEqual(se.may_yield(bare, "agent-1", 1002, generation=1,
                                      eligible=False)["reason"], "HEARTBEAT_ARMED")

    def test_111_a_heartbeat_never_fires_after_the_deadline(self):  # P2-3
        state = night_shift(budget={"currency": "USD", "amount": 50, "baseline": 149.15,
                                    "deadline": 1100})
        before = se.snapshot(state)
        with self.assertRaises(se.ShiftError) as err:
            arm(state, 1001, 1200)
        self.assertEqual(err.exception.code, "HEARTBEAT_AFTER_DEADLINE")
        self.assertEqual(state, before)
        arm(state, 1001, 1100)  # the deadline itself is the last wake
        self.assertEqual(se.may_yield(state, "agent-1", 1002, generation=1,
                                      eligible=False)["until"], 1100)
        state["heartbeat"]["fires_at"] = 1250  # armed past the deadline (pre-fix state)
        self.assertFalse(se.heartbeat_armed(state, 1002))
        gate = se.may_yield(state, "agent-1", 1002, generation=1, eligible=False)
        self.assertEqual((gate["next"], gate["fire_by"]), ("arm_heartbeat", 1100))

    def test_115_overflow_and_bad_currency_fail_closed_and_a_tick_is_never_half_applied(self):
        # P3-7
        for budget in (float("inf"), {"adoptions": float("inf")},
                       {"currency": "USD", "amount": 10 ** 400}, {"deadline": 10 ** 400},
                       {"currency": 1, "amount": 50}, {"currency": " ", "amount": 50}):
            with self.assertRaises(se.ShiftError, msg=str(budget)[:60]):
                night_shift(budget=budget)
        state = night_shift()
        se.record_spend(state, "agent-1", 149.15, 1001, generation=1)
        arm(state, 1001, 1300)
        se.apply_tick(state, "agent-1", "bg_1", 1300, generation=1, spend_total=10 ** 400)
        self.assertEqual((state["cursor"]["last_event_id"], state["heartbeat"]["job_ref"],
                          state["lease"]["expires_at"]), ("bg_1", None, 1300 + LEASE))
        self.assertEqual((state["budget"]["money"]["inconsistent_at"],
                          state["admission"]["reason"]),
                         (1300, "SPEND_MEASUREMENT_INCONSISTENT"))
        self.assertEqual(se.apply_tick(state, "agent-1", "bg_1", 1301, generation=1,
                                       spend_total=152.0), (state, None))  # replay: no effect

    def test_116_the_deadline_is_epoch_seconds_utc_and_the_scenario_ranges_are_current(self):
        # P3-8
        with self.assertRaises(se.ShiftError) as err:
            night_shift(budget={"deadline": 1795694400 * 1000})  # milliseconds
        self.assertEqual(err.exception.code, "BAD_BUDGET")
        state = night_shift(budget={"deadline": 1795694400})
        self.assertEqual(state["log"][0]["deadline_utc"], "2026-11-26T12:00:00Z")
        with open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("epoch seconds, UTC", text)
        numbers = set()
        for name in ("test_shift_engine.py", "test_continuity.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                numbers |= {int(n) for n in re.findall(r"def test_(\d+)_", handle.read())}
        top = max(numbers)
        self.assertIn(f"`test_92`–`test_{top}`", text)
        self.assertIn(f"Scenarios 92–{top}", text)
        listed = {int(line.split(".", 1)[0]) for line in text.splitlines()
                  if re.match(r"^\d+\. ", line)}
        self.assertLessEqual(set(range(92, top + 1)), listed)


OMIT = object()  # a tick-only wake: apply_tick without spend_total


class VerdictRound2(unittest.TestCase):
    """Independent verdict r2 on PR #618 @cb839548: a meter failure never stalls the shift."""

    def night(self, reading, rebaseline_at=None):
        """test_99's incident night. `reading(wake, total)` is what the host passes at each
        wake: the true running total, None (the ledger could not be read), a contradicting
        number, or OMIT. Returns the state, the (wake, item) starts, the gate reasons, the
        wakes and, when the flagged meter ended the chain, the (wake, now) where it did."""
        backlog = given_backlog()
        deadline = 11 * 3600
        state = night_shift(now=0, lease_secs=3600, budget={
            "currency": "USD", "amount": 50, "freeze_at": 40, "deadline": deadline})
        se.record_spend(state, "agent-1", 149.15, 1, generation=1)
        now, total, wakes, rebased, started, reasons = 2, 149.15, 0, False, [], set()
        halted = None
        for _ in range(500):
            pick = se.select_next(state, backlog, "agent-1", now, generation=1)
            if pick["action"] == "start":
                se.start_item(state, "agent-1", pick["intent_key"], backlog, now, generation=1)
                started.append((wakes, pick["intent_key"]))
                continue
            gate = se.may_yield(state, "agent-1", now, generation=1, eligible=False)
            reasons.add(gate["reason"])
            if gate["next"] == "close_at_cutoff":
                se.close_at_cutoff(state, "agent-1", now, generation=1)
                break
            if gate["next"] == "arm_heartbeat":
                arm(state, now, gate["fire_by"], job_ref=f"bg_{wakes + 1}")
                continue
            self.assertTrue(gate["yield"])
            if gate["reason"] == "METER_FLAGGED_TOO_LONG":
                # nothing re-armed: the lease lapses and the next wake is the principal's,
                # here an overdue one after the deadline, which closes with no lease
                halted, now = (wakes, now), deadline + 60
                self.assertFalse(se.lease_valid(state, "agent-1", now))
                self.assertEqual(se.may_yield(state, "agent-1", now, generation=1,
                                              eligible=False)["next"], "close_at_cutoff")
                se.close_at_cutoff(state, "agent-1", now, generation=1)
                break
            now, total, wakes = gate["until"], total + 0.5, wakes + 1  # a wake costs
            self.assertTrue(se.lease_valid(state, "agent-1", now), now)  # never lapses
            if rebaseline_at is not None and now >= rebaseline_at and not rebased:
                # on the principal's explicit order (the holder never supplies its name)
                self.assertTrue(se.rebaseline_spend(state, "owner-1", total, now,
                                                    generation=1)["rebaselined"])
                rebased = True
            value = reading(wakes, total)
            extra = {} if value is OMIT else {"spend_total": value}
            se.apply_tick(state, "agent-1", f"bg_{wakes}", now, generation=1, **extra)
            for key in list(state["in_flight"]):
                se.complete_item(state, "agent-1", key, author="worker", reviewer="judge",
                                 now=now, generation=1)
        else:
            self.fail("the loop never reached the cutoff")
        self.assertEqual((state["status"], state["stop"]["kind"], state["stop"]["reason"]),
                         (se.STOPPED, "cutoff", "DEADLINE_REACHED"))
        return state, started, reasons, wakes, halted

    def test_118_one_unreadable_read_does_not_halt_the_shift(self):
        state, started, reasons, wakes, halted = self.night(
            lambda wake, total: None if wake == 1 else total)
        self.assertEqual(started, [(0, "b-517"), (0, "b-516"), (2, "d-8")])  # none at wake 1
        self.assertIn("SPEND_NOT_READ", reasons)
        self.assertIsNone(state["budget"]["money"]["inconsistent_at"])
        self.assertEqual((wakes, halted), (22, None))  # one wake per half lease, as test_99

    def test_119_a_contradiction_keeps_a_tick_only_chain_for_two_leases_then_stops(self):
        state, started, reasons, wakes, halted = self.night(
            lambda wake, total: 100.0 if wake == 1 else OMIT)  # wake 1: the total went down
        self.assertEqual(started, [(0, "b-517"), (0, "b-516")])  # nothing after it
        self.assertLessEqual({"SPEND_UNMEASURABLE", "METER_FLAGGED_TOO_LONG"}, reasons)
        self.assertEqual(state["budget"]["money"]["inconsistent_at"], 1802)
        self.assertEqual((wakes, halted), (5, (5, 1802 + 2 * 3600)))  # bounded, not 22
        self.assertEqual(state["stop"]["at"], 11 * 3600 + 60)  # the overdue wake closed it

    def test_120_a_rebaseline_inside_the_window_resumes_the_work(self):
        state, started, _, wakes, halted = self.night(
            lambda wake, total: 100.0 if wake == 1 else (total if wake >= 4 else OMIT),
            rebaseline_at=2 * 3600)  # wake 4, before the two-lease bound
        self.assertEqual(started, [(0, "b-517"), (0, "b-516"), (4, "d-8")])
        self.assertIsNone(state["budget"]["money"]["inconsistent_at"])
        self.assertEqual((wakes, halted), (22, None))
        self.assertEqual(state["log"][-1]["event"], "closed_at_cutoff")

    def test_122_the_holder_s_limits_are_written_down(self):  # verdict r2 findings 3 and 4
        with open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8") as handle:
            text = handle.read()
        loop = text.split("## Work loop", 1)[1].split("### Host adapters", 1)[0]
        self.assertIn("never supplies the principal's name", loop)
        self.assertIn("final `record_spend` before `propose_handoff`", loop)
        self.assertIn("trusts the list it is handed", text)
        self.assertIn("Caller-trusted", se.start_item.__doc__)


class VerdictRound3(unittest.TestCase):
    """Independent verdict r3 on PR #618 @5bf239b6: bounded unmetered wakes, whole counts."""

    def test_123_a_money_cap_needs_a_deadline(self):  # N1
        with self.assertRaises(se.ShiftError) as err:
            night_shift(budget={"currency": "USD", "amount": 50, "freeze_at": 40})
        self.assertEqual(err.exception.code, "MISSING_FIELD")
        self.assertIn("budget.deadline", str(err.exception))
        for budget in ({"adoptions": 3}, {"deadline": DEADLINE}, 3):
            self.assertIsNone(night_shift(budget=budget)["budget"]["money"])

    def test_124_a_ledger_that_stays_unreadable_ends_the_chain_after_two_leases(self):  # N1
        state, started, reasons, wakes, halted = VerdictRound2.night(
            self, lambda wake, total: None)
        self.assertEqual(started, [(0, "b-517"), (0, "b-516")])
        self.assertLessEqual({"SPEND_NOT_READ", "METER_FLAGGED_TOO_LONG"}, reasons)
        self.assertEqual(state["budget"]["money"]["read_failed_at"], 1802)  # the first failure
        self.assertEqual((wakes, halted), (5, (5, 1802 + 2 * 3600)))
        flagged = night_shift()
        se.record_spend(flagged, "agent-1", 149.15, 1001, generation=1)
        se.record_spend(flagged, "agent-1", None, 1002, generation=1)  # the first failure
        for n, (at, fires) in enumerate(((1100, 1300), (1300, 1600), (1600, 1900),
                                         (1900, 2150)), 1):
            arm(flagged, at, fires, job_ref=f"bg_{n}")
            self.assertEqual(se.may_yield(flagged, "agent-1", at, generation=1,
                                          eligible=True)["reason"], "HEARTBEAT_ARMED")
            se.apply_tick(flagged, "agent-1", f"bg_{n}", fires, generation=1, spend_total=None)
        self.assertEqual(flagged["budget"]["money"]["read_failed_at"], 1002)  # never moves on
        arm(flagged, 2150, 2400, job_ref="bg_5")
        gate = se.may_yield(flagged, "agent-1", 1002 + 2 * LEASE, generation=1, eligible=False)
        self.assertEqual((gate["yield"], gate["reason"], gate["next"], gate["flag"]),
                         (True, "METER_FLAGGED_TOO_LONG", "report_degraded", "SPEND_NOT_READ"))
        self.assertNotIn("fire_by", gate)  # bounded even with a heartbeat still armed

    def test_125_a_count_is_a_whole_number_never_truncated(self):  # N2 (graphify, line 101)
        for budget in ({"adoptions": 1.9}, {"adoptions": 2.5}, {"adoptions": True},
                       {"adoptions": "2.7"}, 1.9, True, "2.7", -1):
            with self.assertRaises(se.ShiftError, msg=repr(budget)) as err:
                night_shift(budget=budget)
            self.assertEqual(err.exception.code, "BAD_BUDGET", repr(budget))
        for budget, limit in (({"adoptions": 3}, 3), ({"adoptions": 3.0}, 3),
                              ({"adoptions": "4"}, 4), (5, 5), (0, 0)):
            got = night_shift(budget=budget)["budget"]["limit"]
            self.assertEqual((got, type(got)), (limit, int), repr(budget))


def v1_state(*events, budget=None):
    """A state@1 (v0.2.0) file whose money cap and deadline live only in the log."""
    legacy = new_shift()
    for key in ("heartbeat", "stop"):
        legacy.pop(key, None)
    legacy["schema"] = "on-call-shift/state@1"
    legacy["budget"] = budget or {"limit": 5, "spent": 0}
    legacy["log"].extend(events)
    return legacy


def armed(until, at=1100, **over):
    event = {"at": at, "event": "usd_ledger_armed", "until": until, "cap_delta_usd": 50,
             "baseline_usd": 149.15, "freeze_at_delta_usd": 40, "source": "ledger"}
    event.update(over)
    return event


class Issue619(unittest.TestCase):
    """eko-im/multi-agent-os#619: legacy deadline not migrated; a non-numeric `now`."""

    def test_126_a_v1_deadline_in_the_log_is_promoted_never_guessed(self):
        state = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00")))
        self.assertEqual(state["budget"]["deadline"], 1795694400)  # 12:00Z, epoch seconds
        money = state["budget"]["money"]
        self.assertEqual({k: money[k] for k in ("currency", "limit", "baseline", "freeze_at",
                                                "spent", "inconsistent_at", "read_failed_at")},
                         {"currency": "USD", "limit": 50, "baseline": 149.15, "freeze_at": 40,
                          "spent": 0, "inconsistent_at": None, "read_failed_at": None})
        self.assertEqual(state["log"][-1]["event"], "legacy_budget_promoted")
        self.assertEqual(state["log"][-1]["deadline_utc"], "2026-11-26T12:00:00Z")
        self.assertEqual(se.migrate(copy.deepcopy(state)), state)  # idempotent
        no_freeze = se.migrate(v1_state(armed("2026-11-26T09:00:00Z",
                                              freeze_at_delta_usd=None)))
        self.assertEqual(no_freeze["budget"]["money"]["freeze_at"], 50)
        # several events: only the most recent one counts
        latest = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00", at=1100),
                                     armed("2026-11-26T07:00:00+00:00", at=1200,
                                           cap_delta_usd=20, freeze_at_delta_usd=15,
                                           baseline_usd=10)))
        self.assertEqual(latest["budget"]["deadline"], 1795676400)
        self.assertEqual((latest["budget"]["money"]["limit"],
                          latest["budget"]["money"]["baseline"]), (20, 10))
        # malformed, naive or incomplete: nothing promoted, the skip is logged and named
        for event, why in ((armed("26/11/2026 09:00"), "until"),
                           (armed("2026-11-26T09:00:00"), "until"),  # naive: zone unknown
                           (armed(None), "until"),
                           (armed("1900-01-01T00:00:00+00:00"), "deadline"),  # #622
                           (armed("2026-11-26T09:00:00-03:00", cap_delta_usd=None),
                            "cap_delta_usd"),
                           (armed("2026-11-26T09:00:00-03:00", baseline_usd="x"),
                            "baseline_usd")):
            skipped = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00", at=1), event))
            self.assertEqual((skipped["budget"]["deadline"], skipped["budget"]["money"]),
                             (None, None), repr(event))
            entry = skipped["log"][-1]
            self.assertEqual((entry["event"], entry["source_event"]),
                             ("legacy_budget_not_promoted", "usd_ledger_armed"))
            self.assertIn(why, entry["reason"])
        # an explicit budget field is never overwritten; only the missing one is promoted
        explicit = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00"),
                                       budget={"limit": 5, "spent": 0, "deadline": 5000}))
        self.assertEqual(explicit["budget"]["deadline"], 5000)
        self.assertEqual(explicit["budget"]["money"]["limit"], 50)
        self.assertEqual((explicit["log"][-1]["promoted"], explicit["log"][-1]["kept"]),
                         (["money"], ["deadline"]))
        capped = {"currency": "EUR", "limit": 9, "freeze_at": 9, "baseline": 1, "spent": 0.0,
                  "measured_at": 1, "source": None}
        kept = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00"),
                                   budget={"limit": 5, "spent": 0, "money": dict(capped)}))
        self.assertEqual(kept["budget"]["deadline"], 1795694400)
        self.assertEqual(kept["budget"]["money"]["currency"], "EUR")
        both = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00"), budget={
            "limit": 5, "spent": 0, "deadline": 5000, "money": dict(capped)}))
        self.assertEqual(both["budget"]["deadline"], 5000)
        self.assertNotIn("legacy_budget", both["log"][-1]["event"])
        # a non-numeric `at` is not a measurement: the meter waits for a reading
        odd_at = se.migrate(v1_state(armed("2026-11-26T09:00:00-03:00", at="yesterday")))
        self.assertIsNone(odd_at["budget"]["money"]["measured_at"])
        self.assertEqual(se._spend_block(odd_at, 2000), "SPEND_NOT_MEASURED")
        plain = se.migrate(v1_state())  # no event: nothing to promote, nothing logged
        self.assertEqual(plain["log"], new_shift()["log"])

    def test_126b_the_incident_s_own_v1_file_closes_at_its_cutoff(self):
        state = se.load(os.path.join(HERE, "fixtures", "night-20261125-state-v1.json"))
        self.assertEqual(state["budget"]["deadline"], 1795694400)
        with self.assertRaises(se.ShiftError) as err:  # never before the cutoff
            se.close_at_cutoff(state, state["holder"], 1795694399, generation=1)
        self.assertEqual(err.exception.code, "NOT_AT_CUTOFF")
        out = se.close_at_cutoff(state, state["holder"], 1795695090, generation=1)
        self.assertEqual(out["reason"], "DEADLINE_REACHED")
        self.assertEqual((state["status"], state["stop"]["kind"]), (se.STOPPED, "cutoff"))

    def test_127_a_bad_now_is_refused_before_any_change(self):
        import continuity as co
        import watchdog as wdg
        import inspect
        for module in (se, co, wdg):
            for name, fn in inspect.getmembers(module, inspect.isfunction):
                if (not name.startswith("_") and fn.__module__ == module.__name__
                        and "now" in inspect.signature(fn).parameters):
                    self.assertTrue(getattr(fn, "checks_now", False), f"{module.__name__}.{name}")
        backlog = given_backlog()
        calls = (
            lambda s, now: se.apply_tick(s, "agent-1", "t-1", now, generation=1),
            lambda s, now: se.close_at_cutoff(s, "agent-1", now, generation=1),
            lambda s, now: se.stop_shift(s, "owner-1", now),
            lambda s, now: se.record_spend(s, "agent-1", 150.0, now, generation=1),
            lambda s, now: se.start_item(s, "agent-1", "b-517", backlog, now, generation=1),
            lambda s, now: se.select_next(s, backlog, "agent-1", now, generation=1),
            lambda s, now: se.may_yield(s, "agent-1", now, generation=1, eligible=False),
            lambda s, now: se.renew_lease(s, "agent-1", now, generation=1),
            lambda s, now: co.postflight(s, "agent-1", now, generation=1),
            lambda s, now: se.rebaseline_spend(s, "owner-1", 150.0, now, generation=1),
        )
        for bad in ("2026-11-26T09:00:00-03:00", True, float("nan"), float("inf"),
                    float("-inf"), None, 10 ** 400):
            with self.assertRaises(se.ShiftError, msg=repr(bad)) as err:
                night_shift(now=bad)
            self.assertEqual(err.exception.code, "BAD_NOW", repr(bad))
            for call in calls:
                state = night_shift()
                se.record_spend(state, "agent-1", 149.15, 1000, generation=1)
                before = se.snapshot(state)
                with self.assertRaises(se.ShiftError, msg=repr(bad)) as err:
                    call(state, bad)
                self.assertEqual(err.exception.code, "BAD_NOW", repr(bad))
                self.assertEqual(state, before, repr(bad))
            wd = wdg.new_watchdog(watchdog_id="w", scope="x", target_holder="agent-1",
                                  generation=1, ack_timeout_secs=5, misses_to_confirm=2, now=1)
            with self.assertRaises(se.ShiftError) as err:
                wdg.observe(wd, now=bad)
            self.assertEqual(err.exception.code, "BAD_NOW")
        state = night_shift(now=1000.5)  # a float or an int epoch is fine
        self.assertEqual(se.cutoff_reason(state, DEADLINE), "DEADLINE_REACHED")


if __name__ == "__main__":
    unittest.main()
