// node --test mcp-tools/shared-browser-mcp/test
import test from 'node:test';
import assert from 'node:assert/strict';
import { filterCall } from '../lib/proxy.mjs';

const S = 'kiro-default-1-1';

test('forces the session on every call', () => {
  const r = filterCall({ name: 'agent_browser_open', arguments: { url: 'https://example.com' } }, S);
  assert.equal(r.params.arguments.session, S);
});

test('refuses another session, namespace, restore and extraArgs', () => {
  for (const args of [{ session: 'other' }, { namespace: 'x' }, { restore: true }, { extraArgs: ['--headed'] }, { idleTimeout: '0' }]) {
    assert.ok(filterCall({ name: 'agent_browser_open', arguments: args }, S).error, JSON.stringify(args));
  }
});

test('accepts its own session id', () => {
  assert.ok(filterCall({ name: 'x', arguments: { session: S } }, S).params);
});

test('refuses flag-like values anywhere in the arguments', () => {
  assert.ok(filterCall({ name: 'agent_browser_click', arguments: { selector: '--no-pin-tab' } }, S).error);
  assert.ok(filterCall({ name: 'x', arguments: { a: { b: [' --action-policy=/tmp/p'] } } }, S).error);
  assert.ok(filterCall({ name: 'x', arguments: { text: 'a -- b' } }, S).params);
});

import { ACCOUNT_FREE_TOOLS, TAB_TOOLS } from '../lib/proxy.mjs';

test('page reads and actions need the account check; tab moves are locked', () => {
  for (const t of ['agent_browser_snapshot', 'agent_browser_get_text', 'agent_browser_click', 'agent_browser_fill', 'agent_browser_eval',
    'agent_browser_get_title', 'agent_browser_tab_list']) {
    assert.ok(!ACCOUNT_FREE_TOOLS.has(t), t);
  }
  assert.ok(ACCOUNT_FREE_TOOLS.has('agent_browser_open'));
  assert.ok(TAB_TOOLS.has('agent_browser_tab_switch') && !TAB_TOOLS.has('agent_browser_tab_list'));
});

import { accountVerdict, isTargetId } from '../lib/proxy.mjs';

test('target ids used in CDP URLs are plain alphanumerics', () => {
  assert.ok(isTargetId('2EE60210FABBDE21900FA7FDE8CFFAD0'));
  for (const id of ['../activate/x', 'a/b', '', 'x?y', undefined]) assert.ok(!isTargetId(id), String(id));
});

test('account verdict: match, mismatch, none, and fail closed', () => {
  assert.equal(accountVerdict('w@x.io', ['p@y.io', 'w@x.io'], 'work'), null);
  assert.match(accountVerdict('w@x.io', ['p@y.io'], 'work'), /^ACCOUNT_MISMATCH/);
  assert.match(accountVerdict('w@x.io', [], 'work'), /^ACCOUNT_UNVERIFIED/);
  assert.equal(accountVerdict('none', [], 'public'), null);
  assert.match(accountVerdict('none', ['p@y.io'], 'public'), /^ACCOUNT_MISMATCH/);
  assert.match(accountVerdict('', ['w@x.io'], 'work'), /^ACCOUNT_UNVERIFIED/);
});

test('open only reaches http(s) or about:blank, never a logout URL', () => {
  const call = (url) => filterCall({ name: 'agent_browser_open', arguments: { url } }, S);
  for (const url of ['file:///home/u/.ssh/id_ed25519', 'javascript:alert(1)', 'data:text/html,x', 'chrome://settings',
    'https://accounts.google.com/Logout', 'https://github.com/logout', 'https://x.io/u/signout?a=1', ' FILE:///etc/passwd', 42]) {
    assert.match(call(url).error || '', /^url_refused/, String(url));
  }
  for (const url of ['https://example.com', 'http://example.com/a', 'example.com/x', 'about:blank', 'https://docs.x.io/logout-guide']) {
    assert.ok(call(url).params, url);
  }
});
