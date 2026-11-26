"""Continuity and watchdog scenarios (stdlib unittest; no network, no model, no timer).

Processes: only a disposable `sleep` child created by the test itself is ever signalled.
Run: python3 -m unittest discover -s skills/on-call-shift/tests -v
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bin"))

import continuity as co  # noqa: E402
import shift_engine as se  # noqa: E402
import watchdog as wdg  # noqa: E402

LEASE = 600
SUP = "supervisor://shift-desk-1"


def shift(successor=None):
    return se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x", backlog=None,
                         capacity=3, budget=5, holder="agent-1", supervisor_target=SUP,
                         now=1000, lease_secs=LEASE,
                         successor_policy={"pre_authorized": successor} if successor else None)


def backlog():
    return se.normalize_backlog([{"connector": "c", "status": "ok", "items": [
        {"ref": "R-1", "intent_key": "k1"}, {"ref": "R-2", "intent_key": "k2"}]}])


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def failing_writer(path, data):
    raise OSError("disk full (simulated)")


def watchdog(now=1000):
    return wdg.new_watchdog(watchdog_id="wd-1", scope="shift-1", target_holder="agent-1",
                            generation=1, ack_timeout_secs=30, misses_to_confirm=2, now=now)


def spawn_disposable():
    token = f"oncall-disposable-{uuid.uuid4().hex}"
    proc = subprocess.Popen([sys.executable, "-c", "import time,sys; time.sleep(120)", token],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    ident = None
    for _ in range(20):  # the process table may be unreadable on this host: then None
        ident = wdg.identify(proc.pid)
        if ident is None or token in ident["command"]:
            break
        time.sleep(0.05)
    return {"pid": proc.pid, "start": ident["start"] if ident else None, "token": token,
            "disposable": True, "_popen": proc}


class Continuity(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "shift.json")
        self.procs = []

    def tearDown(self):
        for proc in self.procs:  # only our own disposable children
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        self.tmp.cleanup()

    def test_49_preflight_greets_the_watchdog_and_backup_is_ok_on_ack(self):
        state, wd = shift(), watchdog()
        self.assertTrue(wdg.greet(wd, holder="agent-1", generation=1, nonce="n-1",
                                  now=1001)["greeted"])
        ack = wdg.ack(wd, nonce="n-1", holder="agent-1", generation=1, now=1005)
        pre = co.preflight(state, "agent-1", 1006, generation=1, watchdog=wd, watchdog_ack=ack)
        self.assertEqual((pre["findings"]["watchdog"], pre["backup"]), ("OK", "OK"))
        self.assertEqual(wdg.greet(wd, holder="agent-1", generation=1, nonce="n-1",
                                   now=1007)["reason"], "NONCE_REUSED")
        self.assertEqual(wdg.greet(wd, holder="agent-9", generation=1, nonce="n-2",
                                   now=1007)["reason"], "WRONG_TARGET_OR_GENERATION")

    def test_50_backup_absent_or_late_is_degraded(self):
        state = shift()
        absent = co.preflight(state, "agent-1", 1001, generation=1, watchdog=None)
        self.assertEqual((absent["findings"]["watchdog"], absent["backup"]),
                         ("ABSENT", "DEGRADED"))
        wd = watchdog()
        wdg.greet(wd, holder="agent-1", generation=1, nonce="n-1", now=1001)
        late = wdg.ack(wd, nonce="n-1", holder="agent-1", generation=1, now=1001 + 31)
        self.assertEqual(late["verdict"], "LATE")
        pre = co.preflight(state, "agent-1", 1040, generation=1, watchdog=wd, watchdog_ack=late)
        self.assertEqual(pre["backup"], "DEGRADED")
        wdg.greet(wd, holder="agent-1", generation=1, nonce="n-2", now=1041)
        self.assertEqual(wdg.ack(wd, nonce="n-x", holder="agent-1", generation=1,
                                 now=1042)["verdict"], "REJECTED")
        silent = co.preflight(state, "agent-1", 1043, generation=1, watchdog=wd,
                              watchdog_ack=None)
        self.assertEqual((silent["findings"]["watchdog"], silent["backup"]),
                         ("NO_ACK", "DEGRADED"))

    def test_51_persistence_failure_rolls_back_and_freezes_admission(self):
        state = shift()
        before = se.snapshot(state)
        _, saved = co.transition(state, self.path, se.adopt, "agent-1", "k1", backlog(), 1001,
                                 generation=1, writer=failing_writer)
        self.assertFalse(saved["saved"])
        self.assertEqual(saved["reason"], "PERSISTENCE_FAILED")
        self.assertNotIn("sha256", saved)
        self.assertEqual(state["adopted"], before["adopted"])  # unsaved effect not kept
        self.assertEqual(state["admission"], {"open": False, "reason": "PERSISTENCE_FAILED"})
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(state, "agent-1", "k1", backlog(), 1002, generation=1)
        self.assertEqual(err.exception.code, "ADMISSION_FROZEN")
        self.assertFalse(os.path.exists(self.path))

    def test_52_recovery_after_failure_and_after_a_torn_write(self):
        state = shift()
        co.transition(state, self.path, se.adopt, "agent-1", "k1", backlog(), 1001,
                      generation=1, writer=failing_writer)
        self.assertEqual(co.reopen_admission(state, self.path, "agent-1", 1002, generation=1,
                                             writer=failing_writer)["reason"],
                         "PERSISTENCE_FAILED")
        self.assertTrue(co.reopen_admission(state, self.path, "agent-1", 1003,
                                            generation=1)["reopened"])
        _, saved = co.transition(state, self.path, se.adopt, "agent-1", "k1", backlog(), 1004,
                                 generation=1)
        self.assertTrue(saved["saved"])
        good = se.snapshot(state)
        co.transition(state, self.path, se.apply_tick, "agent-1", "t1", 1005, generation=1)
        with open(self.path, "w") as handle:  # simulate a torn current file
            handle.write('{"schema": "on-call-shift/state@1", "trunc')
        restored, which = co.load_checked(self.path)
        self.assertEqual(which, "previous")
        self.assertEqual(restored, json.loads(json.dumps(good)))
        self.assertTrue(se.lease_valid(restored, "agent-1", 1006))

    def test_52b_save_is_only_saved_when_it_reads_back(self):
        state = shift()
        out = co.autosave(state, self.path, writer=failing_writer)
        self.assertEqual((out["saved"], state["admission"]["reason"]),
                         (False, "PERSISTENCE_FAILED"))

        def corrupting_writer(path, data):  # write succeeds, bytes differ
            with open(path, "wb") as handle:
                handle.write(data[:-2] if not path.endswith(".sha256") else data)

        state = shift()
        out = co.autosave(state, self.path, writer=corrupting_writer)
        self.assertFalse(out["saved"])
        self.assertFalse(state["admission"]["open"])
        # a valid JSON whose hash does not match the sidecar is not trusted
        state = shift()
        co.autosave(state, self.path)
        se.apply_tick(state, "agent-1", "t1", 1001, generation=1)
        co.autosave(state, self.path)
        other = shift()
        other["scope"] = "tampered"
        with open(self.path, "w") as handle:
            json.dump(other, handle)
        restored, which = co.load_checked(self.path)
        self.assertEqual(which, "previous")
        self.assertNotEqual(restored["scope"], "tampered")

    def test_53_child_checkpoint_keeps_pointer_and_hash_in_parent(self):
        parent, child = shift(), shift()
        child_path = os.path.join(self.tmp.name, "child-a.json")
        saved = co.checkpoint_child(parent, "child-a", child, child_path)
        self.assertEqual(parent["children"]["child-a"],
                         {"ref": "child-a.json", "sha256": saved["sha256"], "received": True,
                          "pending": None})
        self.assertNotIn("log", parent["children"]["child-a"])
        bad = co.checkpoint_child(parent, "child-b", child,
                                  os.path.join(self.tmp.name, "child-b.json"),
                                  writer=failing_writer)
        self.assertFalse(bad["saved"])
        self.assertEqual(parent["children"]["child-b"]["received"], False)
        self.assertEqual(parent["admission"]["reason"], "CHILD_PERSISTENCE_FAILED")


    def test_54_fencing_quarantines_the_holder_and_kills_no_third_party(self):
        bystander = spawn_disposable()
        self.procs.append(bystander["_popen"])
        state, wd = shift(successor="agent-2"), watchdog()
        wdg.greet(wd, holder="agent-1", generation=1, nonce="n-1", now=1001)
        self.assertEqual(wdg.observe(wd, now=1040)["verdict"], "SUSPECT")
        self.assertEqual(wdg.fence(wd, state, now=1040)["reason"], "NOT_CONFIRMED")
        wdg.greet(wd, holder="agent-1", generation=1, nonce="n-2", now=1041)
        self.assertEqual(wdg.observe(wd, now=1080)["verdict"], "SUSPECT")  # no evidence yet
        self.assertEqual(wdg.observe(wd, now=1081, independent_evidence=True)["verdict"],
                         "CONFIRMED")
        self.assertTrue(wdg.fence(wd, state, now=1082)["fenced"])
        self.assertIsNone(bystander["_popen"].poll())  # third party untouched
        self.assertFalse(se.lease_valid(state, "agent-1", 1082))
        self.assertTrue(se.take_over(state, "agent-2", 1083)["taken_over"])
        self.assertEqual(state["holder"], "agent-2")
        self.assertEqual(se.take_over(state, "agent-3", 1084)["reason"],
                         "HOLDER_LEASE_STILL_VALID")
        self.assertEqual(wdg.fence(wd, state, now=1085)["reason"], "TARGET_CHANGED")

    def test_55_reused_pid_is_not_killed_and_the_real_disposable_one_is(self):
        target = spawn_disposable()
        self.procs.append(target["_popen"])
        swapped = dict(target, pid=target["pid"] + 1)  # record now points at another pid
        self.assertEqual(wdg.terminate_disposable(swapped)["reason"], "PID_REUSED_OR_CHANGED")
        self.assertEqual(wdg.terminate_disposable(dict(target, _popen=None))["reason"],
                         "NOT_OWN_CHILD")
        self.assertEqual(wdg.terminate_disposable(dict(target, disposable=False))["reason"],
                         "NOT_DISPOSABLE")
        if target["start"] is not None:  # only where the host exposes the process table
            stale = dict(target, start="Thu Jan  1 00:00:00 1970")
            self.assertEqual(wdg.terminate_disposable(stale)["reason"], "PID_REUSED_OR_CHANGED")
        # an exited, reaped child: its pid may already belong to someone else -> no signal
        gone = spawn_disposable()
        gone["_popen"].terminate()
        gone["_popen"].wait(timeout=5)
        self.assertEqual(wdg.terminate_disposable(gone)["reason"], "ALREADY_GONE")
        self.assertIsNone(target["_popen"].poll())  # still alive after every refusal
        done = wdg.terminate_disposable(target)
        self.assertTrue(done["terminated"])
        self.assertIsNotNone(target["_popen"].poll())

    def test_56_handoff_is_derived_and_delegated_to_a_successor_with_ack(self):
        state = shift()
        se.adopt(state, "agent-1", "k1", backlog(), 1001, generation=1)
        path = os.path.join(self.tmp.name, "HANDOFF.md")
        first = co.write_handoff(state, path, now=1002, stale_after_secs=300)
        again = co.render_handoff(state, now=1002, stale_after_secs=300)
        self.assertEqual(read(path), again)  # same snapshot -> same text
        self.assertIn(f"snapshot_sha256: {co.snapshot_sha(state)}", again)
        self.assertIn("data: fresh", again)
        self.assertIn("data: STALE", co.render_handoff(state, now=5000, stale_after_secs=300))
        se.apply_tick(state, "agent-1", "t1", 1003, generation=1)
        co.write_handoff(state, path, now=1003, stale_after_secs=300)
        self.assertEqual(read(path + ".prev"), again)  # previous revision recoverable
        self.assertTrue(first["written"])
        waiting = co.postflight(state, "agent-1", 1004, generation=1, successor="agent-2")
        self.assertEqual(waiting["relief"], "AWAITING_SUCCESSOR_ACK")
        fields = dict(line[2:].split(": ", 1) for line in
                      co.render_handoff(state, now=1004, stale_after_secs=300).splitlines()
                      if line.startswith("- "))
        ack = {"kind": "handoff_ack", "from": "agent-2",
               "generation": int(fields["generation"]),
               "cursor_seq": int(fields["cursor_seq"]),
               "in_flight": [] if fields["in_flight"] == "none" else fields["in_flight"].split(", "),
               "gates": [] if fields["gates"] == "none" else fields["gates"].split(", ")}
        done = co.postflight(state, "agent-1", 1005, generation=1, successor="agent-2", ack=ack)
        self.assertEqual(done["relief"], "RELIEVED")
        self.assertEqual(state["holder"], "agent-2")
        self.assertEqual(state["in_flight"], ["k1"])
        self.assertFalse(se.lease_valid(state, "agent-1", 1006))

    def test_57_postflight_without_successor_ends_without_relief(self):
        state = shift()
        out = co.postflight(state, "agent-1", 1001, generation=1)
        self.assertEqual(out["relief"], "NO_SUCCESSOR_TURN_ENDS_WITHOUT_RELIEF")
        self.assertEqual(state["holder"], "agent-1")
        self.assertFalse(state["admission"]["open"])

    def test_58_preflight_grades_action_on_observable_signals(self):
        state = shift()
        saved = co.autosave(state, self.path)["sha256"]
        ok = co.preflight(state, "agent-1", 1001, generation=1, saved_sha=saved, watchdog=None)
        self.assertEqual((ok["action"], ok["findings"]["saved_sha"]), ("observe", "match"))
        self.assertEqual(ok["findings"]["memory_pressure"], "unknown")
        back = co.preflight(state, "agent-1", 999, generation=1, watchdog=None)
        self.assertEqual((back["action"], back["findings"]["clock"]), ("freeze", "BACKWARDS"))
        state = shift()
        se.apply_tick(state, "agent-1", "t1", 1002, generation=1)
        diverged = co.preflight(state, "agent-1", 1003, generation=1, saved_sha=saved)
        self.assertEqual(diverged["action"], "freeze")
        self.assertEqual(state["admission"]["reason"], "PREFLIGHT_INCONSISTENT")
        stuck = shift()
        first = co.preflight(stuck, "agent-1", 1004, generation=1)
        again = co.preflight(stuck, "agent-1", 1005, generation=1,
                             last_preflight=first["findings"])
        self.assertEqual(again["action"], "reduce")
        self.assertEqual(co.preflight(stuck, "agent-9", 1006, generation=1)["action"],
                         "observe_only")

    def test_59_diagnosis_is_readable_and_carries_no_private_data(self):
        state = shift()
        se.complete_item(state, "agent-1", "k1", author="agent-1", reviewer="agent-2",
                         now=1001, generation=1)
        se.deliver(state, "agent-1", "k1", recipient="person-secret-name",
                   recipient_kind="human", result_ref="repo/x!13@abc",
                   receipt={"received_by": "person-secret-name"}, now=1002, generation=1)
        se.record_feedback(state, "agent-1", "k1", {"from": "person-secret-name",
                                                    "kind": "reject", "note": "private note"},
                           1003, generation=1)
        text = json.dumps(co.diagnose(state, now=1004))
        for private in ("person-secret-name", "private note", "repo/x!13@abc"):
            self.assertNotIn(private, text)
        diag = co.diagnose(state, now=1004)
        self.assertEqual(diag["udv_pending_reasons"], ["REJECTED_REOPENED"])
        self.assertEqual(diag["counts"]["deliveries"], 1)

    def test_60_one_watchdog_per_scope(self):
        registry = {}
        self.assertTrue(wdg.register(registry, "shift-1", "wd-1")["registered"])
        self.assertTrue(wdg.register(registry, "shift-1", "wd-1")["registered"])  # idempotent
        self.assertEqual(wdg.register(registry, "shift-1", "wd-2")["reason"],
                         "WATCHDOG_ALREADY_REGISTERED")


class ChildRecovery(unittest.TestCase):
    """W5-P1: the parent recovers after a child's persistence failed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.parent_path = os.path.join(self.d, "parent.json")

    def tearDown(self):
        self.tmp.cleanup()

    def child(self, shift_id="child-shift", holder="agent-c"):
        return se.open_shift(shift_id=shift_id, principal="owner-1", scope="repo/x",
                             backlog=None, capacity=2, budget=5, holder=holder,
                             supervisor_target=SUP, now=1000, lease_secs=LEASE)

    def failed(self, child_id="child-a", child=None):
        parent, child = shift(), child or self.child()
        se.adopt(parent, "agent-1", "k1", backlog(), 1001, generation=1)
        se.apply_tick(parent, "agent-1", "t1", 1002, generation=1)
        path = os.path.join(self.d, f"{child_id}.json")
        co.checkpoint_child(parent, child_id, child, path, writer=failing_writer)
        return parent, child, path

    def fresh_checkpoint(self, child, path):
        return co.autosave(child, path)["sha256"]

    def recover(self, parent, child_id, path, sha, **kw):
        args = dict(child_path=path, claimed_sha=sha, cause="CHILD_PERSISTENCE_FAILED",
                    now=1003, generation=1, parent_path=self.parent_path)
        args.update(kw)
        return co.recover_child(parent, "agent-1", child_id, **args)

    def test_73_child_failure_freezes_admission_and_records_cause(self):
        parent, child, _ = self.failed()
        self.assertEqual(parent["admission"], {"open": False,
                                               "reason": "CHILD_PERSISTENCE_FAILED"})
        pending = parent["children"]["child-a"]["pending"]
        self.assertEqual({k: v for k, v in pending.items() if k != "failed_at"},
                         {"cause": "CHILD_PERSISTENCE_FAILED", "shift_id": "child-shift",
                          "holder": "agent-c", "generation": 1})
        self.assertEqual((pending["failed_at"]["generation"], pending["failed_at"]["cursor_seq"],
                          pending["failed_at"]["sha256"]),
                         (1, 0, co.snapshot_sha(child)))
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(parent, "agent-1", "k2", backlog(), 1003, generation=1)
        self.assertEqual(err.exception.code, "ADMISSION_FROZEN")
        # a second failure keeps the ORIGINAL cause record, not the newer attempt's
        co.checkpoint_child(parent, "child-a", dict(child, generation=4),
                            os.path.join(self.d, "child-a.json"), writer=failing_writer)
        self.assertEqual(parent["children"]["child-a"]["pending"]["generation"], 1)

    def test_74_valid_new_checkpoint_resolves_persists_and_reopens_once(self):
        parent, child, path = self.failed()
        sha = self.fresh_checkpoint(child, path)
        out = self.recover(parent, "child-a", path, sha)
        self.assertEqual((out["recovered"], out["reopened"]), (True, True))
        self.assertEqual(parent["children"]["child-a"],
                         {"ref": "child-a.json", "sha256": sha, "received": True,
                          "pending": None})
        self.assertTrue(parent["admission"]["open"])
        on_disk, which = co.load_checked(self.parent_path)
        self.assertEqual((which, on_disk), ("current", json.loads(json.dumps(parent))))
        again = self.recover(parent, "child-a", path, sha)  # repeated confirmation
        self.assertEqual(again["reason"], "NO_PENDING_FAILURE")
        # only the resolved pending is removed; another pending child keeps admission frozen
        parent, child, path = self.failed()
        other = self.child(shift_id="child-shift-b", holder="agent-d")
        co.checkpoint_child(parent, "child-b", other, os.path.join(self.d, "child-b.json"),
                            writer=failing_writer)
        out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
        self.assertEqual((out["recovered"], out["reopened"], out["still_pending"]),
                         (True, False, ["child-b"]))
        self.assertIsNotNone(parent["children"]["child-b"]["pending"])
        self.assertFalse(parent["admission"]["open"])

    def test_75_bad_checkpoints_are_rejected_and_change_nothing(self):
        parent, child, path = self.failed()
        sha = self.fresh_checkpoint(child, path)
        before = se.snapshot(parent)
        self.assertEqual(self.recover(parent, "child-a", path, "0" * 64)["reason"],
                         "HASH_MISMATCH")
        other_path = os.path.join(self.d, "other.json")
        other_sha = co.autosave(self.child(shift_id="other-shift"), other_path)["sha256"]
        self.assertEqual(self.recover(parent, "child-a", other_path, other_sha)["reason"],
                         "WRONG_CHILD")
        impostor = os.path.join(self.d, "impostor.json")
        imp_sha = co.autosave(self.child(holder="agent-z"), impostor)["sha256"]
        self.assertEqual(self.recover(parent, "child-a", impostor, imp_sha)["reason"],
                         "WRONG_CHILD")
        self.assertEqual(self.recover(parent, "child-a", path, sha,
                                      cause="SOMETHING_ELSE")["reason"], "CAUSE_MISMATCH")
        self.assertEqual(self.recover(parent, "child-z", path, sha)["reason"],
                         "NO_PENDING_FAILURE")
        self.assertEqual(parent, before)
        # an older version than the one that failed
        parent, child, path = self.failed(child=dict(self.child(), generation=3))
        old_sha = co.autosave(dict(child, generation=2), path)["sha256"]
        self.assertEqual(self.recover(parent, "child-a", path, old_sha)["reason"],
                         "STALE_CHECKPOINT")
        # wrong caller identity or generation of the parent holder
        with self.assertRaises(se.ShiftError):
            co.recover_child(parent, "agent-9", "child-a", child_path=path, claimed_sha=old_sha,
                             cause="CHILD_PERSISTENCE_FAILED", now=1003, generation=1,
                             parent_path=self.parent_path)
        with self.assertRaises(se.ShiftError):
            self.recover(parent, "child-a", path, old_sha, generation=2)

    def test_76_parent_save_failure_keeps_the_safe_frozen_state(self):
        parent, child, path = self.failed()
        sha = self.fresh_checkpoint(child, path)
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, sha, writer=failing_writer)
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "PARENT_PERSISTENCE_FAILED"))
        self.assertEqual(parent, before)
        self.assertFalse(parent["admission"]["open"])
        self.assertTrue(self.recover(parent, "child-a", path, sha)["recovered"])

    def test_77_no_privilege_widening_and_human_gates_stay_frozen(self):
        parent, child, path = self.failed()
        se.set_gate(parent, "agent-1", "k2", {"kind": "approval", "by": "owner-1",
                                              "state": "pending"}, 1002, generation=1)
        lease, budget = dict(parent["lease"]), dict(parent["budget"])
        self.assertTrue(self.recover(parent, "child-a", path,
                                     self.fresh_checkpoint(child, path))["recovered"])
        self.assertEqual(parent["gates"]["k2"]["state"], "pending")
        with self.assertRaises(se.ShiftError) as err:
            se.adopt(parent, "agent-1", "k2", backlog(), 1004, generation=1)
        self.assertEqual(err.exception.code, "HUMAN_GATE")
        self.assertEqual((parent["lease"], parent["budget"], parent["holder"],
                          parent["generation"]), (lease, budget, "agent-1", 1))
        # a freeze with another cause is never lifted by a child recovery
        parent, child, path = self.failed()
        parent["admission"] = {"open": False, "reason": "PREFLIGHT_INCONSISTENT"}
        out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
        self.assertEqual((out["recovered"], out["reopened"]), (True, False))
        self.assertEqual(parent["admission"]["reason"], "PREFLIGHT_INCONSISTENT")

    def test_78_restart_preserves_cursor_and_in_flight_through_recovery(self):
        parent, child, path = self.failed()
        cursor, in_flight = dict(parent["cursor"]), list(parent["in_flight"])
        co.autosave(parent, self.parent_path)
        restored, _ = co.load_checked(self.parent_path)  # restart
        self.assertEqual(restored["children"]["child-a"]["pending"]["cause"],
                         "CHILD_PERSISTENCE_FAILED")
        self.assertFalse(restored["admission"]["open"])
        self.assertTrue(self.recover(restored, "child-a", path,
                                     self.fresh_checkpoint(child, path))["recovered"])
        again, _ = co.load_checked(self.parent_path)  # second restart after recovery
        for state in (restored, again):
            self.assertEqual((state["cursor"], state["in_flight"]), (cursor, in_flight))
        self.assertTrue(again["admission"]["open"])

    def test_79_child_failure_never_lifts_an_earlier_parent_freeze(self):
        for reason in ("POSTFLIGHT", "PREFLIGHT_INCONSISTENT", "PERSISTENCE_FAILED"):
            parent, child = shift(), self.child()
            parent["admission"] = {"open": False, "reason": reason}
            path = os.path.join(self.d, f"child-{reason}.json")
            co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
            self.assertEqual(parent["admission"]["reason"], reason)  # earlier reason kept
            self.assertIsNotNone(parent["children"]["child-a"]["pending"])
            out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
            self.assertEqual((out["recovered"], out["reopened"]), (True, False))
            self.assertEqual(parent["admission"], {"open": False, "reason": reason})
        # and the parent's own recovery does not reopen while a child is still pending
        parent, child = shift(), self.child()
        parent["admission"] = {"open": False, "reason": "PERSISTENCE_FAILED"}
        path = os.path.join(self.d, "child-x.json")
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        out = co.reopen_admission(parent, self.parent_path, "agent-1", 1003, generation=1)
        self.assertEqual((out["reopened"], out["reason"]), (False, "CHILD_FAILURE_PENDING"))
        self.assertFalse(parent["admission"]["open"])

    def test_80_checkpoint_older_than_the_failed_save_is_refused_same_generation(self):
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        old_sha = co.checkpoint_child(parent, "child-a", child, path)["sha256"]  # cursor 0, ok
        se.apply_tick(child, "agent-c", "t1", 1001, generation=1)  # cursor 1
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        self.assertEqual(parent["children"]["child-a"]["pending"]["failed_at"]["cursor_seq"], 1)
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, old_sha)  # the file still holds cursor 0
        self.assertEqual(out["reason"], "STALE_CHECKPOINT")
        self.assertEqual(parent, before)
        out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
        self.assertEqual((out["recovered"], out["reopened"]), (True, True))
        # a second failure at a newer cursor raises the floor: the cursor-1 file is now old
        parent, child = shift(), self.child()
        se.apply_tick(child, "agent-c", "t1", 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        mid_sha = co.autosave(child, path)["sha256"]  # child file at cursor 1
        se.apply_tick(child, "agent-c", "t2", 1002, generation=1)
        co.checkpoint_child(parent, "child-a", child, path + ".x", writer=failing_writer)
        self.assertEqual(parent["children"]["child-a"]["pending"]["failed_at"]["cursor_seq"], 2)
        self.assertEqual(self.recover(parent, "child-a", path, mid_sha)["reason"],
                         "STALE_CHECKPOINT")

    def test_81_a_later_good_save_does_not_clear_pending_without_recovery(self):
        parent, child, path = self.failed()
        co.checkpoint_child(parent, "child-a", child, path)  # good save, no recover_child
        self.assertIsNotNone(parent["children"]["child-a"]["pending"])
        self.assertEqual(parent["admission"], {"open": False,
                                               "reason": "CHILD_PERSISTENCE_FAILED"})
        out = self.recover(parent, "child-a", path, parent["children"]["child-a"]["sha256"])
        self.assertEqual((out["recovered"], out["reopened"]), (True, True))


    def test_82_same_generation_and_cursor_checkpoint_missing_in_flight_work_is_refused(self):
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        old_sha = co.checkpoint_child(parent, "child-a", child, path)["sha256"]  # no work yet
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)  # no tick: same cursor
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        failed = parent["children"]["child-a"]["pending"]["failed_at"]
        with open(path, "rb") as handle:
            old = json.loads(handle.read())
        self.assertEqual((old["generation"], old["cursor"]["seq"], old["in_flight"]),
                         (failed["generation"], failed["cursor_seq"], []))
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, old_sha)
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "STALE_CHECKPOINT_SAVE_SEQ"))
        self.assertEqual(parent, before)
        self.assertFalse(parent["admission"]["open"])

    def test_83_valid_recovery_after_restart_reopens_once_and_keeps_the_item(self):
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        co.checkpoint_child(parent, "child-a", child, path)
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        co.autosave(parent, self.parent_path)
        restored, _ = co.load_checked(self.parent_path)  # parent restart
        child_back = json.loads(json.dumps(child))  # child restarts from its own memory
        good = co.autosave(child_back, path)["sha256"]  # newer save, item in flight
        out = co.recover_child(restored, "agent-1", "child-a", child_path=path,
                               claimed_sha=good, cause="CHILD_PERSISTENCE_FAILED", now=1003,
                               generation=1, parent_path=self.parent_path)
        self.assertEqual((out["recovered"], out["reopened"]), (True, True))
        with open(path, "rb") as handle:
            self.assertEqual(json.loads(handle.read())["in_flight"], ["k1"])
        again = co.recover_child(restored, "agent-1", "child-a", child_path=path,
                                 claimed_sha=good, cause="CHILD_PERSISTENCE_FAILED", now=1004,
                                 generation=1, parent_path=self.parent_path)
        self.assertEqual(again["reason"], "NO_PENDING_FAILURE")  # exactly one reopening
        on_disk, _ = co.load_checked(self.parent_path)
        self.assertTrue(on_disk["admission"]["open"])

    def test_84_save_counter_never_goes_back_and_equal_count_is_not_newer(self):
        state = shift()
        co.autosave(state, self.parent_path)
        seq = state["save_seq"]
        co.transition(state, self.parent_path, se.apply_tick, "agent-1", "t1", 1001,
                      generation=1, writer=failing_writer)  # failed save rolls back the state
        self.assertGreater(state["save_seq"], seq)  # ...but never the counter
        # the failed save wrote the child file but not its sidecar: same count, not newer
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        co.checkpoint_child(parent, "child-a", child, path)

        def sidecar_fails(target, data):
            if target.endswith(".sha256"):
                raise OSError("sidecar write failed (simulated)")
            co._atomic_write(target, data)

        co.checkpoint_child(parent, "child-a", child, path, writer=sidecar_fails)
        with open(path, "rb") as handle:
            data = handle.read()
        self.assertEqual(json.loads(data)["save_seq"],
                         parent["children"]["child-a"]["pending"]["failed_at"]["save_seq"])
        out = self.recover(parent, "child-a", path, hashlib.sha256(data).hexdigest())
        self.assertEqual(out["reason"], "STALE_CHECKPOINT_SAVE_SEQ")
        out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
        self.assertTrue(out["recovered"])

    def test_85_counter_rolled_back_by_a_child_reload_must_not_make_an_old_file_recover(self):
        # R2 (parecer 05): the counter lives in the child's own file. The child fails to save
        # an adopted item, crashes, reloads the previous revision (lower counter) and saves
        # again; after enough saves the counter passes the failure floor. The correct
        # behaviour is that the counter never goes back, so a checkpoint without the lost
        # item is not accepted as the recovery of that failure.
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        co.checkpoint_child(parent, "child-a", child, path)  # file: no item, save_seq 1
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)  # no tick: same cursor
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)  # seq 2 fails
        floor = parent["children"]["child-a"]["pending"]["failed_at"]["save_seq"]
        reloaded, _ = co.load_checked(path)  # the child restarts from the old revision
        self.assertEqual(reloaded["in_flight"], [])
        self.assertLessEqual(reloaded["save_seq"], floor)
        sha = None
        for _ in range(floor + 1):  # saves until the rolled-back counter passes the floor
            sha = co.autosave(reloaded, path)["sha256"]
        self.assertGreater(reloaded["save_seq"], floor)  # the symptom: the counter regressed
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, sha)
        self.assertFalse(out["recovered"], "checkpoint lacking the failed in-flight item "
                         "was accepted after a counter rollback")
        self.assertEqual(out["reason"], "STALE_CHECKPOINT_IN_FLIGHT")
        self.assertEqual(parent, before)
        self.assertFalse(parent["admission"]["open"])
        self.assertIsNotNone(parent["children"]["child-a"]["pending"])

    def test_86_checkpoint_without_save_seq_is_refused(self):
        # Q1c (parecer 05): a legacy checkpoint (no save_seq) that is otherwise acceptable by
        # generation and cursor must still be refused. Discriminates "accept when absent".
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        floor = parent["children"]["child-a"]["pending"]["failed_at"]
        legacy = json.loads(json.dumps(child))
        del legacy["save_seq"]
        data = json.dumps(legacy, indent=2, sort_keys=True).encode("utf-8")
        co._atomic_write(path, data)  # same generation and cursor, newest content, no counter
        self.assertEqual((legacy["generation"], legacy["cursor"]["seq"]),
                         (floor["generation"], floor["cursor_seq"]))
        self.assertNotIn("save_seq", json.loads(read(path)))
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, hashlib.sha256(data).hexdigest())
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "STALE_CHECKPOINT_SAVE_SEQ"))
        self.assertEqual(parent, before)
        self.assertFalse(parent["admission"]["open"])

    def test_87_two_failures_at_the_same_cursor_keep_the_floor_on_the_latest_one(self):
        # Q1g (parecer 05): failure A, a good save, then failure B at the SAME cursor. The
        # floor must move to B, so the good save made between A and B (without B's item)
        # is refused. Discriminates a floor that stays on the first failure.
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)  # failure A
        first = dict(parent["children"]["child-a"]["pending"]["failed_at"])
        child["admission"] = {"open": True, "reason": None}  # the child itself reopens, then
        between = co.autosave(child, path)["sha256"]  # good save: holds k1, not k2
        se.adopt(child, "agent-c", "k2", backlog(), 1002, generation=1)  # still no tick
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)  # failure B
        second = parent["children"]["child-a"]["pending"]["failed_at"]
        self.assertEqual(first["cursor_seq"], second["cursor_seq"])  # same cursor
        self.assertGreater(second["save_seq"], first["save_seq"])
        self.assertEqual(json.loads(read(path))["in_flight"], ["k1"])
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, between)
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "STALE_CHECKPOINT_SAVE_SEQ"))
        self.assertEqual(parent, before)
        out = self.recover(parent, "child-a", path, self.fresh_checkpoint(child, path))
        self.assertEqual((out["recovered"], out["reopened"]), (True, True))

    def test_88_child_that_legitimately_completed_the_failed_item_is_not_refused(self):
        # R2 counterpart: the in-flight item that failed to save was then really finished
        # (in_flight shrinks, cursor advances) and saved. The checkpoint omits k1 for a good
        # reason, so recovery must accept it: no false STALE.
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        floor = parent["children"]["child-a"]["pending"]["failed_at"]
        child["admission"] = {"open": True, "reason": None}  # the child reopens itself
        se.complete_item(child, "agent-c", "k1", author="agent-c", reviewer="agent-2",
                         now=1002, generation=1)
        se.apply_tick(child, "agent-c", "t-done", 1003, generation=1)
        sha = self.fresh_checkpoint(child, path)
        doc = json.loads(read(path))
        self.assertEqual(doc["in_flight"], [])  # k1 is gone from the checkpoint...
        self.assertGreater(doc["cursor"]["seq"], floor["cursor_seq"])  # ...and the cursor moved
        out = self.recover(parent, "child-a", path, sha)
        self.assertEqual((out["recovered"], out["reason"]), (True, None))
        self.assertIsNone(parent["children"]["child-a"]["pending"])

    def test_89_second_failed_save_after_a_reload_keeps_the_lost_item_in_the_floor(self):
        # Review 06 (A1): good save with no item, adopt k1, failed save (floor holds k1), the
        # child reloads the old revision (counter back to a tie), a NEW failed save replaces
        # the floor, then a good save. The floor must keep k1 (union of failures), so the
        # checkpoint that lacks k1 is refused with STALE_CHECKPOINT_IN_FLIGHT.
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        co.checkpoint_child(parent, "child-a", child, path)  # good save, no item, save_seq 1
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)  # seq 2
        reloaded, _ = co.load_checked(path)  # the child restarts from the old revision
        self.assertEqual(reloaded["in_flight"], [])
        co.checkpoint_child(parent, "child-a", reloaded, path, writer=failing_writer)  # tie
        floor = parent["children"]["child-a"]["pending"]["failed_at"]
        self.assertEqual(floor["in_flight"], ["k1"])  # union: the first failure's item stays
        sha = co.autosave(reloaded, path)["sha256"]  # good save, still without k1
        self.assertEqual(json.loads(read(path))["in_flight"], [])
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, sha)
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "STALE_CHECKPOINT_IN_FLIGHT"))
        self.assertEqual(parent, before)
        self.assertFalse(parent["admission"]["open"])

    def test_90_malformed_in_flight_or_log_id_is_refused_not_raised(self):
        # Review 06 (A2): a hash-valid checkpoint with non-string ids must get a structured
        # refusal, not a TypeError.
        for field in ("in_flight", "log"):
            parent, child = shift(), self.child()
            path = os.path.join(self.d, "child-a-%s.json" % field)
            se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
            co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
            floor = parent["children"]["child-a"]["pending"]["failed_at"]
            bad = json.loads(json.dumps(child))
            bad["save_seq"] = floor["save_seq"] + 1
            if field == "in_flight":
                bad["in_flight"] = [["k1"]]
            else:
                bad["log"] = [{"event": "item_completed", "id": ["k1"]}]
            data = json.dumps(bad, indent=2, sort_keys=True).encode("utf-8")
            co._atomic_write(path, data)
            before = se.snapshot(parent)
            out = self.recover(parent, "child-a", path, hashlib.sha256(data).hexdigest())
            self.assertEqual((out["recovered"], out["reason"]),
                             (False, "CHECKPOINT_UNREADABLE"), field)
            self.assertEqual(parent, before)

    def test_91_non_item_completed_event_with_the_lost_id_does_not_count_as_completion(self):
        # Contrast for the item_completed filter: the reloaded checkpoint logs an event of
        # another type carrying the lost item's id; it must not excuse the missing item.
        parent, child = shift(), self.child()
        path = os.path.join(self.d, "child-a.json")
        co.checkpoint_child(parent, "child-a", child, path)  # good save, no item
        se.adopt(child, "agent-c", "k1", backlog(), 1001, generation=1)
        co.checkpoint_child(parent, "child-a", child, path, writer=failing_writer)
        reloaded, _ = co.load_checked(path)
        reloaded["log"] = list(reloaded.get("log") or []) + [{"event": "item_adopted", "id": "k1"}]
        floor = parent["children"]["child-a"]["pending"]["failed_at"]["save_seq"]
        sha = None
        while sha is None or reloaded["save_seq"] <= floor:  # counter must pass the floor
            sha = co.autosave(reloaded, path)["sha256"]
        before = se.snapshot(parent)
        out = self.recover(parent, "child-a", path, sha)
        self.assertEqual((out["recovered"], out["reason"]),
                         (False, "STALE_CHECKPOINT_IN_FLIGHT"))
        self.assertEqual(parent, before)


class OwnTeam(unittest.TestCase):
    """The holder's own team: admission, drain, idempotent retirement, other owners untouched."""

    def setUp(self):
        self.procs = []

    def tearDown(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    def admit(self, state, member, **kw):
        args = dict(role="reviewer", scope="repo/x", risk="low", cost=1, now=1001,
                    generation=1)
        args.update(kw)
        return se.admit_member(state, "agent-1", member, **args)

    def test_66_admission_refused_by_risk_budget_scope_or_seats(self):
        state = shift()
        before = se.snapshot(state)
        self.assertEqual(self.admit(state, "m1", risk="high")["reason"], "RISK_TOO_HIGH")
        self.assertEqual(self.admit(state, "m1", cost=99)["reason"], "BUDGET_EXCEEDED")
        self.assertEqual(self.admit(state, "m1", scope="other-org")["reason"], "OUT_OF_SCOPE")
        self.assertEqual(self.admit(state, "m1", persistent=True)["reason"],
                         "PERSISTENT_NEEDS_REVIEW_AND_DISARM")
        self.assertEqual(state, before)  # refusals change nothing
        for m in ("m1", "m2", "m3"):
            self.assertTrue(self.admit(state, m)["admitted"])
        self.assertEqual(self.admit(state, "m4")["reason"], "SEATS_FULL")
        self.assertEqual(self.admit(state, "m1")["reason"], "ALREADY_ADMITTED")
        self.assertEqual(len(state["team"]["members"]), 3)
        self.assertEqual(state["budget"]["spent"], 3)
        self.assertEqual(state["team"]["members"]["m1"]["mode"], "ephemeral")

    def test_67_drain_finishes_in_flight_work_before_retiring(self):
        state = shift()
        self.admit(state, "m1")
        se.assign_member(state, "agent-1", "m1", "k1", 1002, generation=1)
        out = se.retire_member(state, "agent-1", "m1", 1003, generation=1)
        self.assertEqual((out["retired"], out["reason"], out["in_flight"]),
                         (False, "DRAINING", ["k1"]))
        self.assertEqual(se.assign_member(state, "agent-1", "m1", "k2", 1004,
                                          generation=1)["reason"], "MEMBER_DRAINING")
        se.member_done(state, "agent-1", "m1", "k1", 1005, generation=1)
        done = se.retire_member(state, "agent-1", "m1", 1006, generation=1)
        self.assertTrue(done["retired"])
        self.assertEqual(done["receipt"]["member"], "m1")  # ephemeral leaves an exit receipt

    def test_68_retirement_is_idempotent(self):
        state = shift()
        self.admit(state, "m1")
        first = se.retire_member(state, "agent-1", "m1", 1002, generation=1)
        after_first = se.snapshot(state)
        second = se.retire_member(state, "agent-1", "m1", 1003, generation=1)
        self.assertEqual((first["retired"], second["reason"]), (True, "ALREADY_RETIRED"))
        self.assertEqual(second["receipt"], first["receipt"])
        self.assertEqual(state, after_first)

    def test_69_member_of_another_owner_is_never_touched(self):
        state = shift()
        foreign = {"owner": "shift-other", "role": "writer", "scope": "repo/x", "risk": "low",
                   "cost": 1, "mode": "ephemeral", "review_at": None, "disarm": None,
                   "status": "active", "in_flight": ["their-item"], "admitted_at": 900,
                   "exit_receipt": None}
        state["team"]["members"]["their-m"] = dict(foreign)
        for call in (lambda: se.retire_member(state, "agent-1", "their-m", 1002, generation=1),
                     lambda: se.assign_member(state, "agent-1", "their-m", "k", 1002,
                                              generation=1),
                     lambda: se.member_done(state, "agent-1", "their-m", "their-item", 1002,
                                            generation=1)):
            with self.assertRaises(se.ShiftError) as err:
                call()
            self.assertEqual(err.exception.code, "NOT_YOUR_MEMBER")
        self.assertEqual(state["team"]["members"]["their-m"], foreign)

    def test_70_shutdown_rehearsal_only_on_a_disposable_child(self):
        state = shift()
        self.admit(state, "m1")
        child = spawn_disposable()
        self.procs.append(child["_popen"])
        bystander = spawn_disposable()
        self.procs.append(bystander["_popen"])
        se.retire_member(state, "agent-1", "m1", 1002, generation=1)
        self.assertTrue(wdg.terminate_disposable(child)["terminated"])
        # replaying the stop after the child is gone affects no new process
        fresh = spawn_disposable()
        self.procs.append(fresh["_popen"])
        self.assertEqual(wdg.terminate_disposable(child)["reason"], "ALREADY_GONE")
        self.assertIsNone(fresh["_popen"].poll())
        self.assertIsNone(bystander["_popen"].poll())

    def test_71_creating_or_deleting_a_shared_resource_is_parked(self):
        state = shift()
        for action in ("create", "delete"):
            out = se.request_shared_change(state, "agent-1", "shared-queue", action, 1002,
                                           generation=1, owner="platform-team")
            self.assertEqual((out["done"], out["reason"]), (False, "SHARED_RESOURCE_NOT_OWNED"))
        self.assertEqual([p["operation"] for p in state["parked"]],
                         ["create:shared-queue", "delete:shared-queue"])
        self.assertEqual(state["status"], se.ACTIVE)
        self.assertEqual(self.admit(state, "t0", kind="tool", decision="none")["reason"],
                         "DECIDED_NOT_TO")
        self.assertNotIn("t0", state["team"]["members"])

    def test_72_own_tool_retires_without_touching_other_owners_dependents(self):
        state = shift()
        others = [{"id": "their-job", "owner": "shift-other", "active": False}]
        self.assertTrue(self.admit(state, "lint-cli", kind="tool", decision="configure",
                                   dependents=others, verification="lint-cli --version",
                                   expires_at=2000)["admitted"])
        out = se.retire_member(state, "agent-1", "lint-cli", 1002, generation=1)
        self.assertTrue(out["retired"])
        self.assertEqual(state["team"]["members"]["lint-cli"]["dependents"], others)
        busy = shift()
        live = [{"id": "their-job", "owner": "shift-other", "active": True}]
        self.admit(busy, "lint-cli", kind="tool", decision="create", dependents=live)
        before = se.snapshot(busy)
        blocked = se.retire_member(busy, "agent-1", "lint-cli", 1002, generation=1)
        self.assertEqual((blocked["retired"], blocked["reason"]), (False, "DEPENDENTS_ACTIVE"))
        self.assertEqual(busy, before)


class WorkLoopContinuity(unittest.TestCase):
    """Postmortem night-20261125: continuity must not end the work loop on its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "shift.json")

    def tearDown(self):
        self.tmp.cleanup()

    def deadline_shift(self, deadline=1100):
        return se.open_shift(shift_id="shift-1", principal="owner-1", scope="repo/x",
                             backlog=None, capacity=2, budget={"deadline": deadline},
                             holder="agent-1", supervisor_target=SUP, now=1000,
                             lease_secs=LEASE,
                             capabilities={"heartbeat_transport": "omp:background-job"})

    def test_100_the_holder_lifts_its_own_postflight_freeze_on_its_next_turn(self):
        state = shift()
        co.postflight(state, "agent-1", 1001, generation=1)
        self.assertEqual(state["admission"]["reason"], "POSTFLIGHT")
        self.assertTrue(co.reopen_admission(state, self.path, "agent-1", 1002,
                                            generation=1)["reopened"])
        self.assertEqual(state["admission"], {"open": True, "reason": None})
        late = self.deadline_shift()
        co.postflight(late, "agent-1", 1001, generation=1)
        self.assertEqual(co.reopen_admission(late, self.path, "agent-1", 1100,
                                             generation=1)["reason"], "DEADLINE_REACHED")
        self.assertFalse(late["admission"]["open"])
        for reason in ("PREFLIGHT_INCONSISTENT", "SPEND_CAP_REACHED", "DEADLINE_REACHED"):
            other = shift()
            other["admission"] = {"open": False, "reason": reason}
            self.assertFalse(co.reopen_admission(other, self.path, "agent-1", 1002,
                                                 generation=1)["reopened"], reason)
            self.assertEqual(other["admission"]["reason"], reason)

    def test_101_preflight_handoff_and_diagnosis_name_the_cutoff_and_the_heartbeat(self):
        state = self.deadline_shift()
        found = co.preflight(state, "agent-1", 1001, generation=1)["findings"]
        self.assertEqual((found["budget_left"], found["cutoff"], found["heartbeat"]),
                         (None, None, "not_armed"))
        se.arm_heartbeat(state, "agent-1", 1001, generation=1, transport="omp:background-job",
                         job_ref="bg_1", fires_at=1100, bound_target=SUP)
        self.assertEqual(co.preflight(state, "agent-1", 1002,
                                      generation=1)["findings"]["heartbeat"], "armed")
        self.assertIn("- heartbeat: armed until 1100",
                      co.render_handoff(state, now=1002, stale_after_secs=300))
        self.assertEqual(co.preflight(state, "agent-1", 1100, generation=1)["action"],
                         "close_at_cutoff")
        se.close_at_cutoff(state, "agent-1", 1100, generation=1)
        self.assertIn("- stop: cutoff DEADLINE_REACHED",
                      co.render_handoff(state, now=1100, stale_after_secs=300))
        diag = co.diagnose(state, now=1100)
        self.assertEqual(diag["stop"], {"kind": "cutoff", "reason": "DEADLINE_REACHED"})
        self.assertEqual(diag["heartbeat"], {"armed": False, "fires_at": 1100})

    def test_102_load_checked_migrates_a_v0_2_0_file(self):
        legacy = shift()
        for key in ("heartbeat", "stop"):
            legacy.pop(key, None)
        legacy["budget"] = {"limit": 5, "spent": 0}
        co.autosave(legacy, self.path)
        state, revision = co.load_checked(self.path)
        self.assertEqual(revision, "current")
        self.assertEqual(sorted(state), sorted(shift()))
        self.assertEqual(state["budget"]["money"], None)
        self.assertIsNone(state["stop"])


if __name__ == "__main__":
    unittest.main()
