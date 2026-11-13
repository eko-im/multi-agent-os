#!/usr/bin/env node
// shared-browser-mcp proxy.
// Sits between one MCP client (stdio) and `agent-browser mcp`, so that every
// client gets exactly one pinned tab on a shared, already-logged-in CDP Chrome.
// It fixes the session id, refuses arguments that would let the model leave
// that session or change policy, writes a lease, and closes its own tab on exit.
import { spawn, execFile } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';

// Shared tool arguments that agent-browser accepts on every MCP tool. The
// wrapper owns all of them: a model that could set `session` or `namespace`
// would escape its pinned tab; `restore*` would write cookies to disk.
export const FORBIDDEN_ARGS = new Set([
  'session', 'namespace', 'restore', 'restoreSave', 'restoreCheckUrl',
  'restoreCheckText', 'restoreCheckFn', 'extraArgs', 'caCert', 'useSystemCa',
  'clearCaCert', 'idleTimeout', 'relaunch', 'allowedDomains',
]);

// A pinned session keeps exactly one tab. Measured on 0.39.0: `--pin-tab` did
// not stop another session from `tab <targetId>` into it (0.41.2 does return
// tab_locked), and no version stops a switch into an unpinned human tab.
export const TAB_TOOLS = new Set(['agent_browser_tab_switch', 'agent_browser_tab_close', 'agent_browser_tab_new']);

// Tools that neither read page content nor act on it, so they run before the
// account is known (open is how the session reaches the page to check).
// Not here: get_title (a Gmail title shows the account e-mail) and tab_list
// (shows other tabs' titles and URLs); both go through the account check.
export const ACCOUNT_FREE_TOOLS = new Set([
  'agent_browser_open', 'agent_browser_get_url', 'agent_browser_wait_ms',
  'agent_browser_wait_for_load', 'agent_browser_close', 'agent_browser_back', 'agent_browser_forward',
  'agent_browser_reload', 'agent_browser_tools_profiles',
]);

// CDP target ids are 32 hex chars. The id goes into CDP URLs (/json/close/<id>,
// /devtools/page/<id>), so anything else (a path like ../activate/x) is ignored.
export const isTargetId = (id) => typeof id === 'string' && /^[A-Za-z0-9]{1,64}$/.test(id);

// Runs in the page over a separate CDP connection: returns the e-mails in
// account widgets (aria-label/title/data-email) and a GitHub-style
// <meta name="user-login">. Only these tokens leave the page, never content.
const ACCOUNT_PROBE = `(() => {
  const re = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/gi, out = new Set();
  for (const el of document.querySelectorAll('[aria-label],[data-email],[title]'))
    for (const a of ['aria-label', 'data-email', 'title']) {
      const v = el.getAttribute(a); if (v) (v.match(re) || []).forEach((e) => out.add(e.toLowerCase()));
    }
  const m = document.querySelector('meta[name="user-login"]');
  if (m && m.content) out.add(m.content.toLowerCase());
  return [...out].slice(0, 20);
})()`;

export function pageAccounts(cdpPort, targetId) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${cdpPort}/devtools/page/${targetId}`);
    const timer = setTimeout(() => { ws.close(); reject(new Error('account probe timed out')); }, 5000);
    ws.onerror = () => { clearTimeout(timer); reject(new Error('account probe could not reach the tab')); };
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression: ACCOUNT_PROBE, returnByValue: true } }));
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id !== 1) return;
      clearTimeout(timer); ws.close();
      resolve((m.result && m.result.result && m.result.result.value) || []);
    };
  });
}

// Decides the account check from the expected account and the accounts the
// page shows. expected 'none' = a profile with no login: any visible account
// is a mismatch. Empty expected fails closed (bin/shared-browser-mcp refuses
// to start without one; this guards a direct start of the proxy).
export function accountVerdict(expected, seen, identity) {
  if (!expected) return `ACCOUNT_UNVERIFIED: no account set for identity '${identity}'`;
  if (expected === 'none') {
    return seen.length ? `ACCOUNT_MISMATCH: identity '${identity}' expects no signed-in account but the page shows one; stop and report` : null;
  }
  if (seen.includes(expected)) return null;
  return seen.length
    ? `ACCOUNT_MISMATCH: the page is signed in as a different account than the one set for identity '${identity}'; switch account or stop and report`
    : `ACCOUNT_UNVERIFIED: no signed-in account visible on the page for identity '${identity}'`;
}

// agent-browser < 0.41.0 reads global flags anywhere in its argv, so a string
// value such as "--no-pin-tab" inside a selector could change the session
// (upstream #2238). shortcut: refuse every value that starts with "--";
// drop this once the pinned agent-browser is >= 0.41.0.
const FLAG_LIKE = /^\s*--[A-Za-z]/;

function scanFlagLike(value) {
  if (typeof value === 'string') return FLAG_LIKE.test(value);
  if (Array.isArray(value)) return value.some(scanFlagLike);
  if (value && typeof value === 'object') return Object.values(value).some(scanFlagLike);
  return false;
}

// Navigation targets. Measured: `open file:///home/...` lets the model read any
// local file (keys, env) and `open` runs before the account check, so a page
// could also send the model to a logout URL that signs the human out of the
// shared profile. Only http(s) and about:blank pass; logout/signout paths do not.
// shortcut: the logout match is by path only; a click on a "Sign out" link
// still works (it is account-checked but not blocked). Phase 2: per-site URL policy.
export function urlRefusal(url) {
  if (url === 'about:blank') return null;
  let u;
  try { u = new URL(/^[a-z][a-z0-9+.-]*:/i.test(url) ? url : `https://${url}`); } catch { return 'url_refused: not a valid URL'; }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return `url_refused: scheme '${u.protocol}' is not allowed (http, https or about:blank only)`;
  if (/\/(log|sign)[-_]?(out|off)(\/|$)/i.test(u.pathname)) return 'url_refused: logout/signout URLs would sign the shared profile out; stop and report';
  return null;
}

// Returns {params} with the session forced, or {error} with the reason.
export function filterCall(params, session) {
  const args = (params && params.arguments) || {};
  for (const key of Object.keys(args)) {
    if (!FORBIDDEN_ARGS.has(key)) continue;
    if (key === 'session' && args[key] === session) continue;
    return { error: `argument '${key}' is fixed by the wrapper and cannot be set by a tool call` };
  }
  if (scanFlagLike(args)) {
    return { error: 'a value starting with "--" is refused (agent-browser would read it as a global flag)' };
  }
  if (args.url !== undefined) {
    const why = typeof args.url === 'string' ? urlRefusal(args.url.trim()) : 'url_refused: url must be a string';
    if (why) return { error: why };
  }
  return { params: { ...params, arguments: { ...args, session } } };
}

function memAvailableMb() {
  try {
    const m = /MemAvailable:\s+(\d+)/.exec(fs.readFileSync('/proc/meminfo', 'utf8'));
    return m ? Math.floor(Number(m[1]) / 1024) : Infinity;
  } catch { return Infinity; }
}

function sanitizeUrl(u) {
  try { const x = new URL(u); return x.origin + x.pathname; } catch { return undefined; }
}

function main() {
  const env = process.env;
  const home = env.SB_HOME;
  const session = env.SB_SESSION;
  if (!home || !session) { process.stderr.write('shared-browser-mcp: start through bin/shared-browser-mcp\n'); process.exit(2); }
  const ab = env.SB_AGENT_BROWSER || 'agent-browser';
  const cdp = env.SB_CDP || '9222';
  const maxLeases = Number(env.SB_MAX_LEASES || 10);
  const minMemMb = Number(env.SB_MIN_MEM_MB || 3000);
  const leaseDir = path.join(home, 'leases');
  const leaseFile = path.join(leaseDir, `${session}.json`);
  const auditFile = path.join(home, 'audit.log');

  const childEnv = { ...env };
  for (const k of Object.keys(childEnv)) if (k.startsWith('AGENT_BROWSER_RESTORE')) delete childEnv[k];
  Object.assign(childEnv, {
    AGENT_BROWSER_SESSION: session,
    AGENT_BROWSER_CDP: cdp,
    AGENT_BROWSER_CONTENT_BOUNDARIES: '1',
    AGENT_BROWSER_MAX_OUTPUT: env.SB_MAX_OUTPUT || '50000',
  });
  // SB_PIN_TAB=0 exists only for the isolation mutation-check.
  const pinned = env.SB_PIN_TAB !== '0';
  if (pinned) childEnv.AGENT_BROWSER_PIN_TAB = '1'; else delete childEnv.AGENT_BROWSER_PIN_TAB;
  if (env.SB_POLICY) childEnv.AGENT_BROWSER_ACTION_POLICY = env.SB_POLICY;

  const audit = (rec) => {
    try { fs.appendFileSync(auditFile, JSON.stringify({ ts: new Date().toISOString(), session, ...rec }) + '\n', { mode: 0o600 }); } catch { /* audit must not break the session */ }
  };

  // `sh -c ... 9>&-` drops the lease lock fd so only this process holds it.
  const child = spawn('/bin/sh', ['-c', 'exec "$@" 9>&-', 'sh', ab, 'mcp', '--tools', env.SB_TOOLS || 'core'],
    { stdio: ['pipe', 'pipe', 'inherit'], env: childEnv });

  let lease = null;
  const pending = new Map();

  const writeLease = () => { fs.writeFileSync(leaseFile, JSON.stringify(lease), { mode: 0o600 }); };
  const captureTarget = () => new Promise((resolve) => {
    execFile(ab, ['--session', session, '--json', 'tab', 'list'], { env: childEnv, timeout: 15000 }, (err, out) => {
      if (!err && lease) {
        try {
          const tab = (JSON.parse(out).data.tabs || []).find((t) => t.active);
          if (tab && isTargetId(tab.targetId)) { lease.targetId = tab.targetId; writeLease(); }
        } catch { /* retried on the next call */ }
      }
      resolve();
    });
  });

  // Account check: before a tool reads or acts on the page, the wrapper (not
  // the model) asks the page which account it is signed in as and compares it
  // with the account configured for this identity (one Chrome profile per account).
  const expectedAccount = (env.SB_ACCOUNT || '').toLowerCase();
  let probeMs = 0;
  const checkAccount = async () => {
    probeMs = 0;
    if (!expectedAccount) return accountVerdict('', [], env.SB_IDENTITY);
    if (!lease.targetId) await captureTarget();
    if (!lease.targetId) return 'ACCOUNT_UNVERIFIED: no pinned tab yet';
    let seen;
    const t0 = performance.now();
    try { seen = await pageAccounts(cdp, lease.targetId); } catch (e) { return `ACCOUNT_UNVERIFIED: ${e.message}`; }
    probeMs = Math.round(performance.now() - t0);
    return accountVerdict(expectedAccount, seen, env.SB_IDENTITY);
  };

  const reply = (id, text) => {
    process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: `shared-browser: ${text}` }], isError: true } }) + '\n');
  };

  const admit = () => {
    let live = 0;
    try { live = fs.readdirSync(leaseDir).filter((f) => f.endsWith('.json')).length; } catch { /* empty */ }
    // shortcut: count and create are not atomic; two clients racing at the
    // last slot can both enter. Wrap in flock if the cap is ever hit in practice.
    if (live >= maxLeases) return `capacity ${live}/${maxLeases}, try later`;
    const mem = memAvailableMb();
    if (mem < minMemMb) return `low memory: MemAvailable ${mem} MB < ${minMemMb} MB`;
    return null;
  };

  const rl = readline.createInterface({ input: process.stdin });
  // Lines are handled one at a time so an async account check keeps order.
  let queue = Promise.resolve();
  rl.on('line', (line) => { queue = queue.then(() => handle(line)).catch(() => {}); });
  const handle = async (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { child.stdin.write(line + '\n'); return; }
    if (msg.method !== 'tools/call') { child.stdin.write(line + '\n'); return; }
    const tool = msg.params && msg.params.name;
    const f = pinned && TAB_TOOLS.has(tool)
      ? { error: 'tab_locked: one pinned tab per session; switching, opening or closing other tabs is refused' }
      : filterCall(msg.params, session);
    if (f.error) { audit({ tool, result: 'refused', reason: f.error }); reply(msg.id, f.error); return; }
    if (!lease) {
      const why = admit();
      if (why) { audit({ tool, result: 'refused', reason: why }); reply(msg.id, why); return; }
      lease = { id: session, harness: env.SB_HARNESS, identity: env.SB_IDENTITY, account: env.SB_ACCOUNT || null, cdp, pid: process.pid, started: new Date().toISOString() };
      // Measured: a failed write (disk full, EACCES) threw here and the client
      // never got a reply. Without a lease file the reaper cannot see the tab,
      // so refuse the call instead of running unleased.
      try { writeLease(); } catch (e) {
        lease = null;
        const why = `lease_write_failed: ${e.code || e.message}`;
        audit({ tool, result: 'refused', reason: why }); reply(msg.id, why); return;
      }
    } else {
      const now = new Date();
      try { fs.utimesSync(leaseFile, now, now); } catch { /* reaper may have removed it */ }
    }
    if (!ACCOUNT_FREE_TOOLS.has(tool)) {
      const bad = await checkAccount();
      if (bad) { audit({ tool, result: 'refused', reason: bad.split(':')[0], probe_ms: probeMs }); reply(msg.id, bad); return; }
      audit({ tool, account_check: 'ok', probe_ms: probeMs });
    }
    pending.set(msg.id, { tool, url: sanitizeUrl(f.params.arguments.url) });
    child.stdin.write(JSON.stringify({ ...msg, params: f.params }) + '\n');
  };

  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    process.stdout.write(line + '\n');
    try {
      const msg = JSON.parse(line);
      const p = pending.get(msg.id);
      if (!p) return;
      pending.delete(msg.id);
      audit({ tool: p.tool, url: p.url, result: (msg.error || (msg.result && msg.result.isError)) ? 'error' : 'ok' });
      // Without a pin the "active" tab may be someone else's (measured: an
      // unpinned open navigated a human tab and exit then closed it), so the
      // wrapper only records, and later closes, a tab it is pinned to.
      if (pinned && lease && !lease.targetId) captureTarget();
    } catch { /* not JSON-RPC */ }
  });

  let done = false;
  const shutdown = async (reason) => {
    if (done) return;
    done = true;
    audit({ event: 'shutdown', reason });
    // A client that disconnects right after its first call can beat the async
    // target capture; capture now so the pinned tab is not left behind.
    if (pinned && lease && !lease.targetId) await captureTarget();
    try { child.kill('SIGTERM'); } catch { /* already gone */ }
    if (lease && lease.targetId) {
      // `agent-browser close` on a CDP session only detaches; the tab stays.
      try { await fetch(`http://127.0.0.1:${cdp}/json/close/${lease.targetId}`); } catch { /* reaper retries */ }
    }
    if (lease) {
      await new Promise((r) => execFile(ab, ['--session', session, 'close'], { env: childEnv, timeout: 15000 }, () => r()));
      try { fs.unlinkSync(leaseFile); } catch { /* gone */ }
    }
    try { fs.unlinkSync(path.join(home, 'locks', `${session}.lock`)); } catch { /* gone */ }
    process.exit(0);
  };

  rl.on('close', () => shutdown('stdin closed'));
  child.on('exit', () => shutdown('agent-browser mcp exited'));
  for (const s of ['SIGTERM', 'SIGHUP', 'SIGINT']) process.on(s, () => shutdown(s));
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();
