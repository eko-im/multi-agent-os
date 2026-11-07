# shared-browser-mcp

One already-logged-in Chrome, many agents. Each MCP client gets **one pinned
tab** on a shared Chrome (reached over CDP on loopback), served as a stdio MCP
server over `ssh`, so no port is opened. It wraps
[`agent-browser mcp`](https://github.com/vercel-labs/agent-browser).

Status: phase 1 (validation). Tested on Linux with agent-browser 0.41.2 and
Chrome 155. Generic: no host, account or org lives in this directory; all of it
goes in a local `$SB_HOME/env` on the browser host.

**Not ready for real accounts yet.** Two parts of the design are still open:

- **One profile per account is not set up on the tested host.** The validation
  host had one Chrome profile holding two Google accounts. The port check only
  catches two identities configured with different accounts on the same port;
  it does not split accounts that share a profile. Create one profile (and one
  CDP port) per account before using it with real logins.
- **The GitHub account check is untested.** The `<meta name="user-login">` probe
  was not run against GitHub, and no `ACCOUNT_MISMATCH` between two GitHub
  accounts has been measured. Only the Google `authuser` case was tested.

## Model

```
MCP client --stdio--> ssh -T <host> shared-browser-mcp <harness> <account>
   └─> lib/proxy.mjs (lease, filters, account check, cleanup)
         └─> agent-browser mcp --tools core   (AGENT_BROWSER_CDP=<profile port>, PIN_TAB=1)
               └─> Chrome profile for <account>, CDP on 127.0.0.1 only
```

- **One Chrome profile per account.** Cookies are per profile, so two accounts
  in one profile can be mixed silently (measured: a work task landed on the
  personal Google account because it is `authuser=0`). The second argument names
  the account profile; `SB_CDP_<account>` is its CDP port and
  `SB_ACCOUNT_<account>` is the e-mail or login its pages must show (`none` for
  a profile with no login: any visible account is then a mismatch). Both are
  **required**: the wrapper refuses to start without them, and refuses when two
  identities with different accounts point at the same CDP port.
- **agent-browser >= 0.41.0 is enforced** at start (older `--pin-tab` does not
  return `tab_locked`).
- **Account check before every tool that reads or acts on the page.** The proxy
  (not the model) reads the account e-mails in the page's account widgets and
  `<meta name="user-login">` over its own CDP connection. Expected account
  present: the call goes through. Another account: `ACCOUNT_MISMATCH`. None
  visible: `ACCOUNT_UNVERIFIED`. Only `open`, `get_url`, waits, history moves
  and `close` run without it (`get_title` and `tab_list` are checked: a title
  can show the account e-mail, and `tab_list` shows other tabs). Each check is logged
  with `probe_ms`. For Google, open URLs with `?authuser=<account>`: without it
  a profile holding two accounts lands on `authuser=0`.
- **Session fixed by the wrapper.** Tool arguments `session`, `namespace`,
  `restore*`, `extraArgs`, `idleTimeout`, `relaunch`, `allowedDomains`, CA
  options, and any value starting with `--` are refused. Tab switch/new/close
  are refused with `tab_locked`.
- **Lease** = `$SB_HOME/leases/<id>.json`, written on the first tool call and
  touched on every call. Liveness = an `flock` on `$SB_HOME/locks/<id>.lock`
  held by the proxy for its whole life.
- **Cleanup.** On stdin EOF or SIGTERM the proxy closes its tab over CDP
  (`agent-browser close` on a CDP session only detaches; the tab stays), closes
  the session and drops the lease. `bin/shared-browser-reaper` handles the rest:
  lock free (owner died) -> close tab; lease idle > `SB_IDLE_SEC` (silent network
  drop) -> SIGTERM the owner.
- **Admission.** Refused above `SB_MAX_LEASES` leases or below `SB_MIN_MEM_MB`
  of `MemAvailable`.
- **Policy.** `policy/default.json` (deny eval, downloads, uploads, network,
  state) or `policy/read-only.json`. agent-browser 0.41.2 matches policy on
  **action names** (`evaluate`, `screenshot`, `tab_list`, `close`, `launch`,
  `url`, `title`, `gettext` ...), not only the documented categories; a
  default-deny policy must allow `launch`, `close` and `tab_list` or attach,
  cleanup and the account check fail. Page output gets `--content-boundaries`
  and `--max-output`.
- **URLs.** Any `url` argument must be `http(s)` or `about:blank`; `file:`,
  `javascript:`, `data:`, `chrome:` and logout/signout paths are refused
  (`url_refused`). Measured: `open file://...` let a session read local files.
- **Lease write.** If the lease cannot be written (disk full, permissions) the
  call is refused with `lease_write_failed` instead of hanging.

## Install (on the browser host)

```bash
mkdir -p ~/sb/app && cp -r bin lib policy ~/sb/app/ && ln -sfn app/bin ~/sb/bin
npm i --prefix ~/sb/ab --ignore-scripts agent-browser@0.41.2   # >= 0.41 for tab_locked and #2238
cat > ~/sb/env <<'EOF'
SB_CDP=${SB_CDP:-9222}
SB_AGENT_BROWSER=$HOME/sb/ab/node_modules/.bin/agent-browser
SB_POLICY=${SB_POLICY:-$HOME/sb/app/policy/default.json}
SB_MAX_LEASES=10
SB_MIN_MEM_MB=3000
SB_IDLE_SEC=${SB_IDLE_SEC:-900}
# one block per account profile (required; one Chrome profile per account):
# SB_CDP_work=9222
# SB_ACCOUNT_work=someone@example.com
# SB_CDP_public=9224
# SB_ACCOUNT_public=none
EOF
chmod 600 ~/sb/env
```

Run the reaper every 2 minutes with the user timer in `systemd/` (a silent
network drop then holds a tab at most `SB_IDLE_SEC` + 2 min):

```bash
mkdir -p ~/.config/systemd/user && cp systemd/shared-browser-reaper.* ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now shared-browser-reaper.timer
```

Or cron: `*/2 * * * * SB_HOME=$HOME/sb $HOME/sb/bin/shared-browser-reaper >/dev/null`.

## Register (client side)

Kiro / Claude project `.mcp.json` shape; other harnesses need their own format.

```json
{"mcpServers": {"shared-browser": {
  "command": "ssh",
  "args": ["-T", "-o", "ControlMaster=no", "-o", "ControlPath=none",
           "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
           "<host>", "SB_HOME=$HOME/sb $HOME/sb/bin/shared-browser-mcp <harness> <account>"]}}}
```

`ControlMaster=no` gives each MCP its own connection, so it does not count
against the shared master's `MaxSessions` and one dropped master does not take
every agent down.

## Test

```bash
node --test mcp-tools/shared-browser-mcp/test/filter.test.mjs
node mcp-tools/shared-browser-mcp/test/mcp-client.mjs '[["agent_browser_open",{"url":"https://example.com"}]]' -- ssh -T <host> 'SB_HOME=$HOME/sb $HOME/sb/bin/shared-browser-mcp test public'
```

Never run the unpinned mode (`SB_PIN_TAB=0`, for the isolation mutation-check
only) against a Chrome that has human tabs: an unpinned `open` navigates the
active tab, whoever owns it.

## Known limits

- Admission count and lease creation are not atomic (see `shortcut:` in the code).
- `tab_list` runs only after the account check, but then it still lists other
  tabs' titles and URLs (it is not filtered to the session's own tab).
- The account probe only sees accounts a page exposes in `aria-label`, `title`,
  `data-email` or `<meta name="user-login">`; other sites return `ACCOUNT_UNVERIFIED`.
- The probe passes when the expected account appears **anywhere** in those
  attributes (an inbox listing a mail from it is enough) and it runs in the
  page's own JavaScript world, so a page can fake it. It catches a wrong
  profile or `authuser`, not a hostile page.
- A logout is refused only on `open`; clicking a "Sign out" link still works.
- Screenshots stay in `~/.agent-browser/tmp/screenshots` (0600) until removed.
- Values starting with `--` are refused even in plain text input.
- After a Chrome restart every call returns `tab_gone` (fails closed); the MCP
  client must restart the server to get a new tab.
- An account switch inside a page without navigation is caught only on the next
  checked tool call, not before.
