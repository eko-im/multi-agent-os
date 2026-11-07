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
  for (const t of ['agent_browser_snapshot', 'agent_browser_get_text', 'agent_browser_click', 'agent_browser_fill', 'agent_browser_eval']) {
    assert.ok(!ACCOUNT_FREE_TOOLS.has(t), t);
  }
  assert.ok(ACCOUNT_FREE_TOOLS.has('agent_browser_open'));
  assert.ok(TAB_TOOLS.has('agent_browser_tab_switch') && !TAB_TOOLS.has('agent_browser_tab_list'));
});
