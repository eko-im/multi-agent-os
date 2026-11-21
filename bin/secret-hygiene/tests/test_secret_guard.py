#!/usr/bin/python3
"""Cases for secret-guard + mutation-check: each BLOCK case must stop being
blocked when its rule is removed (proves the rule, not luck, catches it)."""
import importlib.machinery, importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "..", "secret-guard")
FAKE = "FAKE_SECRET_for_test_only_0000"

BLOCK = [
    ("op-reveal-unpiped", "op read op://work/SiteLogin/password"),
    ("op-reveal-unpiped", "( set -a; source ~/.config/op/service-accounts/ai-agents.env; set +a; op item get 'SiteLogin' --vault work --fields label=password --reveal )"),
    ("op-reveal-unpiped", "op item get X --vault eko --format json 2>/dev/null"),
    ("op-run-no-masking", "op run --no-masking -- printenv"),
    ("echo-secret-var", 'echo "token: ${OP_SERVICE_ACCOUNT_TOKEN:+SET}${OP_SERVICE_ACCOUNT_TOKEN:-UNSET}"'),
    ("echo-secret-var", 'echo $GITHUB_TOKEN'),
    ("echo-secret-var", 'printf "%s\\n" "$DB_PASSWORD"'),
    ("printenv", "printenv SITE_API_TOKEN"),
    ("dump-env", "env"),
    ("xtrace-with-secret", "set -x; PW=$(op read op://eko/x/password); ssh vm 'cat >/dev/null' <<< \"$PW\""),
    ("cat-secret-file", "cat ~/.config/op/service-accounts/ai-agents.env"),
    ("cat-secret-file", "head -c 200 ~/.codex/config.toml"),
    ("cat-secret-file", "cat .env"),
    ("aws-get-secret-value", "aws secretsmanager get-secret-value --secret-id x --query SecretString --output text | wc -c"),
    ("cli-prints-secret", "gh auth token --user ekson73"),
    ("cli-prints-secret", "kubectl get secret db -o yaml"),
    ("cli-prints-secret", "security find-generic-password -s foo -w"),
    ("gh-secret-body", 'gh secret set FOO --body "$VAL"'),
    ("secret-in-argv", 'curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user'),
    ("secret-in-argv", 'mysql -u root --pass' + 'word=' + 'fixture1 db'),  # split: keeps scanners off a fake
]

ALLOW = [
    "op read op://work/SiteLogin/password | ssh my-vm 'python3 login.py'",
    "PW=$(op read op://eko/x/password); test -n \"$PW\" && echo set",
    "( set -a; source ~/.config/op/service-accounts/ai-agents.env; set +a; op item get X --vault work --fields label=credential --reveal | gh secret set FOO )",
    "op item get X --vault eko --fields label=password --reveal > \"$tmpf\"",
    "op run --env-file=.env.tpl -- ./deploy.sh",
    "op inject -i cfg.tpl -o cfg.json",
    "op item list --vault eko --format json | jq length",
    'echo "len=${#GITHUB_TOKEN}"',
    'echo "${OP_SERVICE_ACCOUNT_TOKEN:+SET}"',
    'printf %s "$DB_PASSWORD" | ssh vm "cat > /run/pw"',
    "env | cut -d= -f1 | sort",
    "set -x; make build",
    "grep -c TOKEN ~/.config/op/service-accounts/ai-agents.env",
    "jq keys ~/.kiro/secrets.json",
    "source ~/.config/op/service-accounts/ai-agents.env",
    'GH_TOKEN="$(gh auth token --user ekson73)" gh pr list',
    "gh auth token | gh secret set FOO",
    "curl -s https://api.github.com/zen",
    "cat README.md",
    "git status && git log --oneline -3",
    "echo hello world",
    "docker login --password-stdin -u x < pwfile",
    "op read op://x/y/z # secret-guard:ok",
]


def run(cmd, guard=GUARD):
    ev = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}}
    p = subprocess.run([guard], input=json.dumps(ev), capture_output=True, text=True,
                       env={**os.environ, "HOME": os.environ["HOME"]})
    return p.returncode, p.stderr


def load(path):
    loader = importlib.machinery.SourceFileLoader("sg", path)
    spec = importlib.util.spec_from_loader("sg", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


def main():
    bad = 0
    for rid, cmd in BLOCK:
        rc, err = run(cmd)
        ok = rc == 2 and f"({rid})" in err
        bad += not ok
        print(("PASS" if ok else "FAIL"), "block", rid, "rc=", rc)
    for cmd in ALLOW:
        rc, err = run(cmd)
        ok = rc == 0
        bad += not ok
        print(("PASS" if ok else "FAIL"), "allow rc=", rc, err.strip()[:80] if not ok else "")
    # kiro-cli / Kiro Crew shapes
    for ev in ({"hook_event_name": "preToolUse", "tool_name": "execute_bash", "tool_input": {"command": "env"}},
               {"tool": "execute_bash", "input": json.dumps({"command": "env"})}):
        p = subprocess.run([GUARD], input=json.dumps(ev), capture_output=True, text=True)
        bad += p.returncode != 2
        print("PASS" if p.returncode == 2 else "FAIL", "shape", list(ev))
    # read-type tools
    for ev, want in (({"tool_name": "Read", "tool_input": {"file_path": "/Users/x/.config/op/service-accounts/ai-agents.env"}}, 2),
                     ({"tool_name": "read_file", "tool_input": {"path": "/repo/.env"}}, 2),
                     ({"tool_name": "fs_read", "tool_input": {"path": "/Users/x/.codex/config.toml"}}, 2),
                     ({"tool_name": "read_file", "tool_input": {"path": "/repo/.env.example"}}, 0),
                     ({"tool_name": "read_file", "tool_input": {"path": "/repo/README.md"}}, 0),
                     ({"tool_name": "fs_write", "tool_input": {"path": "/repo/.env"}}, 0)):
        p = subprocess.run([GUARD], input=json.dumps(ev), capture_output=True, text=True)
        ok = p.returncode == want
        bad += not ok
        print("PASS" if ok else "FAIL", "read-tool", ev["tool_name"], ev["tool_input"]["file_path" if "file_path" in ev["tool_input"] else "path"], p.returncode)
    m0 = load(GUARD)
    m0.SECRET_PATH = __import__("re").compile(r"$^")  # mutation: path rule emptied
    killed = not m0.read_paths({"tool_name": "read_file", "tool_input": {"path": "/repo/.env"}})
    bad += not killed
    print("PASS" if killed else "FAIL", "mutation sem SECRET_PATH -> passa")
    # mutation-check: drop each rule, the cases of that rule must pass through
    m = load(GUARD)
    names = {r.__name__: r for r in m.RULES}
    rule_of = {"op-reveal-unpiped": "op_reveal_unpiped", "op-run-no-masking": "op_reveal_unpiped",
               "echo-secret-var": "echo_secret_var", "printenv": "echo_secret_var", "dump-env": "echo_secret_var",
               "xtrace-with-secret": "xtrace", "cat-secret-file": "cat_secret_file",
               "aws-get-secret-value": "secret_printing_cli", "cli-prints-secret": "secret_printing_cli",
               "gh-secret-body": "secret_in_argv", "secret-in-argv": "secret_in_argv"}
    for rid, cmd in BLOCK:
        fn = names[rule_of[rid]]
        m.RULES[:] = [r for r in names.values() if r is not fn]
        res = m.check(cmd)
        m.RULES[:] = list(names.values())
        killed = res is None or res[0] != rid
        bad += not killed
        print(("PASS" if killed else "FAIL"), "mutation sem", fn.__name__, "->", "passa" if res is None else res[0])
    print("FALHAS:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
