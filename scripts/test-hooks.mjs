#!/usr/bin/env node
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const adapter = path.join(root, 'project', '.claude', 'hooks', 'hook-adapter.mjs');
const failures = [];

function run(profile, payload, env = {}, hook = adapter) {
  return spawnSync(process.execPath, [hook, profile], {
    input: typeof payload === 'string' ? payload : JSON.stringify(payload),
    encoding: 'utf8',
    env: { ...process.env, CLAUDE_PROJECT_DIR: root, ...env },
  });
}

function expect(label, status, result) {
  if (result.status !== status) failures.push(`${label}: expected ${status}, got ${result.status}; ${result.stderr}`);
}

const pre = (tool_name, tool_input, agent_type) => ({ hook_event_name: 'PreToolUse', tool_name, tool_input, agent_type });
expect('read-only git', 0, run('baseline', pre('Bash', { command: 'git status --short' })));
expect('secret shell read', 2, run('baseline', pre('Bash', { command: 'cat .env' })));
expect('authority shell write', 2, run('baseline', pre('Bash', { command: 'sed -i.bak s/x/y/ .claude/settings.json' })));
expect('alternate destructive git', 2, run('baseline', pre('Bash', { command: 'git -C . reset --hard HEAD' })));
expect('hook self-modification', 2, run('baseline', pre('Write', { file_path: '.claude/hooks/hook-adapter.mjs' })));
expect('governance modification', 2, run('baseline', pre('Write', { file_path: '.claude/rules/40-governance-authority.md' })));
expect('secret glob', 2, run('baseline', pre('Glob', { path: '.', pattern: '**/.env*' })));
expect('malformed input', 2, run('baseline', '{'));
expect('portable adapter uses bundled Python policy', 2, run(
  'baseline',
  pre('Bash', { command: 'cat .env' }),
  { CLAUDE_PLUGIN_ROOT: path.join(root, 'plugin', 'madventures-founderos') },
  path.join(root, 'plugin', 'madventures-founderos', 'hooks', 'hook-adapter.mjs'),
));

expect('bounded SELECT', 0, run('sql', pre('Bash', { command: `psql "$DATABASE_URL" -c 'SELECT id FROM ledger LIMIT 10;'` }, 'neon-reader')));
expect('ordinary inspection', 0, run('sql', pre('Bash', { command: 'git status --short' }, 'neon-reader')));
expect('SQL update', 2, run('sql', pre('Bash', { command: `psql "$DATABASE_URL" -c 'UPDATE ledger SET state = 1;'` }, 'neon-reader')));
expect('interactive SQL', 2, run('sql', pre('Bash', { command: 'psql "$DATABASE_URL"' }, 'neon-reader')));
expect('multiple SQL statements', 2, run('sql', pre('Bash', { command: `psql -c 'SELECT 1; SELECT 2;'` }, 'neon-reader')));
expect('write-capable SQL function', 2, run('sql', pre('Bash', { command: `psql -c "SELECT nextval('ledger_seq');"` }, 'neon-reader')));

const status = spawnSync(process.execPath, [path.join(root, 'global', 'madventures-statusline.mjs')], {
  input: JSON.stringify({
    workspace: { current_dir: root },
    model: { display_name: 'Sonnet 5' },
    effort: { level: 'high' },
    context_window: { used_percentage: 42.8 },
  }),
  encoding: 'utf8',
});
if (status.status !== 0 || !status.stdout.includes('Sonnet 5/high') || !status.stdout.includes('ctx 42%')) {
  failures.push(`status line: status ${status.status}; ${status.stderr}`);
}

// Environment identity marker: with MADVENTURES_ENV=1 the statusline prefixes "[MAD_OS Env]".
// Use a temp workspace with no .claude state so the env flag is the only trigger.
const tmpWs = fs.mkdtempSync(path.join(os.tmpdir(), 'mad-statusline-'));
const marked = spawnSync(process.execPath, [path.join(root, 'global', 'madventures-statusline.mjs')], {
  env: { ...process.env, MADVENTURES_ENV: '1' },
  input: JSON.stringify({ workspace: { current_dir: tmpWs }, model: { id: 'Sonnet' } }),
  encoding: 'utf8',
});
if (marked.status !== 0 || !marked.stdout.includes('[MAD_OS Env]')) {
  failures.push(`status line env marker: status ${marked.status}; ${marked.stderr}`);
}
// Install-state activation: INSTALLATION_STATE.json at the project root marks the env.
fs.mkdirSync(path.join(tmpWs, '.claude'), { recursive: true });
fs.writeFileSync(path.join(tmpWs, '.claude', 'INSTALLATION_STATE.json'), '{}');
const stateMarked = spawnSync(process.execPath, [path.join(root, 'global', 'madventures-statusline.mjs')], {
  input: JSON.stringify({ workspace: { current_dir: path.join(tmpWs, 'subdir'), project_dir: tmpWs }, model: { id: 'Sonnet' } }),
  encoding: 'utf8',
});
if (stateMarked.status !== 0 || !stateMarked.stdout.includes('[MAD_OS Env]')) {
  failures.push(`status line install-state marker: status ${stateMarked.status}; ${stateMarked.stderr}`);
}
// Negative case: no env flag, no install-state record => no marker.
// Use a FRESH temp dir (tmpWs now carries the install-state file above).
const plainWs = fs.mkdtempSync(path.join(os.tmpdir(), 'mad-statusline-plain-'));
const plain = spawnSync(process.execPath, [path.join(root, 'global', 'madventures-statusline.mjs')], {
  input: JSON.stringify({ workspace: { current_dir: plainWs }, model: { id: 'Sonnet' } }),
  encoding: 'utf8',
});
if (plain.status !== 0 || plain.stdout.includes('[MAD_OS Env]')) {
  failures.push(`status line negative marker: status ${plain.status}; ${plain.stderr}`);
}
fs.rmSync(plainWs, { recursive: true, force: true });
fs.rmSync(tmpWs, { recursive: true, force: true });

if (failures.length) {
  console.error('HOOK/STATUSLINE TESTS FAILED');
  failures.forEach(failure => console.error(`- ${failure}`));
  process.exit(1);
}
console.log('HOOK/STATUSLINE TESTS PASSED');
