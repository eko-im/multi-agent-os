#!/usr/bin/python3
"""Backoff/jitter and daily-limit stop of secret-pipe, with a fake `op` runner
and a fake sleep (no vault, no waiting). Includes a mutation of the jitter."""
import importlib.machinery, importlib.util, os, sys, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__))
loader = importlib.machinery.SourceFileLoader("sp", os.path.join(HERE, "..", "secret-pipe"))
spec = importlib.util.spec_from_loader("sp", loader)
sp = importlib.util.module_from_spec(spec)
loader.exec_module(sp)
tmp = tempfile.mkdtemp()
sp.LOCK_DIR = os.path.join(tmp, "locks")
sp.SA_ENV = os.path.join(tmp, "sa.env")
open(sp.SA_ENV, "w").write("OP_SERVICE_ACCOUNT_TOKEN=fake\n")
OK = '{"fields":[{"label":"password","value":"x-fake-1234567"}]}'
HOURLY = "[ERROR] Too many requests. Your client has been rate-limited. Try again in  seconds"
DAILY = "[ERROR] Too many requests. Daily limit exceeded for this account"


def runner(script):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        rc, out, err = script[min(len(calls), len(script)) - 1]
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)
    return run, calls


def main():
    bad = 0
    sleeps = []
    run, calls = runner([(1, "", HOURLY), (1, "", HOURLY), (0, OK, "")])
    v = sp._op_item("eko", "a", sleep=sleeps.append, run=run)
    ok = v["fields"][0]["value"] and len(calls) == 3 and len(sleeps) == 2 \
        and 0 <= sleeps[0] <= 5 and 0 <= sleeps[1] <= 10
    bad += not ok
    print("PASS" if ok else "FAIL", "horário: 2 retries com espera dentro do teto", [round(s, 2) for s in sleeps])

    sleeps = []
    run, calls = runner([(1, "", HOURLY)])
    try:
        sp._op_item("eko", "b", sleep=sleeps.append, run=run)
        ok = False
    except sp.SecretError:
        ok = len(calls) == sp.RETRIES + 1
    bad += not ok
    print("PASS" if ok else "FAIL", f"desiste depois de {sp.RETRIES} retries ({len(calls)} chamadas)")

    sleeps = []
    run, calls = runner([(1, "", DAILY)])
    try:
        sp._op_item("eko", "c", sleep=sleeps.append, run=run)
        ok = False
    except sp.SecretError:
        ok = len(calls) == 1 and not sleeps
    bad += not ok
    print("PASS" if ok else "FAIL", "limite diário: para na 1ª chamada, sem retry")

    # jitter is random: many draws must not all be equal
    draws = []
    for _ in range(20):
        sl = []
        r, _c = runner([(1, "", HOURLY), (0, OK, "")])
        sp._op_item("eko", "d", sleep=sl.append, run=r)
        draws.append(sl[0])
    ok = len(set(round(d, 6) for d in draws)) > 15
    bad += not ok
    print("PASS" if ok else "FAIL", "jitter: esperas variam", len(set(round(d, 6) for d in draws)))

    # mutation: jitter removed -> the variance test must catch it
    orig = sp.random.uniform
    sp.random.uniform = lambda a, b: b
    draws = []
    for _ in range(20):
        sl = []
        r, _c = runner([(1, "", HOURLY), (0, OK, "")])
        sp._op_item("eko", "e", sleep=sl.append, run=r)
        draws.append(sl[0])
    sp.random.uniform = orig
    killed = len(set(draws)) == 1
    bad += not killed
    print("PASS" if killed else "FAIL", "mutation: sem jitter, o teste de variação falharia")

    # cache: get() twice on the same item -> one runner call
    sp._ITEMS.clear()
    r, c = runner([(0, OK, "")])
    orig_item = sp._op_item
    sp._op_item = lambda v, i, **kw: orig_item(v, i, run=r, sleep=lambda s: None)
    sp.AGENT_VAULTS = {"eko"}
    sp.get("eko:f:password")
    sp.get("op://eko/f/password")
    sp._op_item = orig_item
    ok = len(c) == 1
    bad += not ok
    print("PASS" if ok else "FAIL", "cache em memória: 2 get() do mesmo item = 1 leitura", len(c))
    print("FALHAS:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
