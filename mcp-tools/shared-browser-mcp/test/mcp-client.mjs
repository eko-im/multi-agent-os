#!/usr/bin/env node
// Tiny MCP stdio client for live checks of shared-browser-mcp.
// usage: node mcp-client.mjs '<json array of [tool, args]>' -- <command...>
// e.g.   node mcp-client.mjs '[["agent_browser_open",{"url":"https://example.com"}]]' -- ssh -T host ~/sb/bin/shared-browser-mcp test
// Prints one JSON line per call: {tool, ms, isError, text (first 300 chars)}.
// Set HOLD_MS to keep the session open after the last call.
import { spawn } from 'node:child_process';
import readline from 'node:readline';

const sep = process.argv.indexOf('--');
const calls = JSON.parse(process.argv[2] || '[]');
const [cmd, ...cmdArgs] = process.argv.slice(sep + 1);
const child = spawn(cmd, cmdArgs, { stdio: ['pipe', 'pipe', 'inherit'] });
const waiters = new Map();
readline.createInterface({ input: child.stdout }).on('line', (l) => {
  let m; try { m = JSON.parse(l); } catch { return; }
  const w = waiters.get(m.id); if (w) { waiters.delete(m.id); w(m); }
});
let next = 1;
const rpc = (method, params) => new Promise((res) => {
  const id = next++; waiters.set(id, res);
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
});

await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'sb-test', version: '0' } });
child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
for (const [tool, args] of calls) {
  // ["sleep", {"ms": N}] pauses between calls (e.g. while a test restarts Chrome).
  if (tool === 'sleep') { await new Promise((r) => setTimeout(r, args.ms)); continue; }
  const t0 = performance.now();
  const r = tool === 'tools/list' ? await rpc('tools/list', {}) : await rpc('tools/call', { name: tool, arguments: args || {} });
  const ms = Math.round(performance.now() - t0);
  const text = r.result && r.result.content ? r.result.content.map((c) => c.text || '').join(' ') : JSON.stringify(r.result ? (r.result.tools || []).map((t) => t.name) : r.error);
  const isError = !!(r.error || (r.result && r.result.isError));
  // LENGTH_ONLY=tool1,tool2: print only the size of successful page output (no page data in logs).
  const lengthOnly = !isError && (process.env.LENGTH_ONLY || '').split(',').includes(tool);
  const shown = lengthOnly ? `<${text.length} chars, ${(text.match(/\brow\b/g) || []).length} rows, ${(text.match(/\blink\b/g) || []).length} links, content omitted>` : text.replace(/\s+/g, ' ').slice(0, Number(process.env.TEXT_MAX || 300));
  console.log(JSON.stringify({ tool, ms, isError, text: shown }));
}
if (process.env.HOLD_MS) await new Promise((r) => setTimeout(r, Number(process.env.HOLD_MS)));
child.stdin.end();
setTimeout(() => process.exit(0), 3000);
