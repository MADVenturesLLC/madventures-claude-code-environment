#!/usr/bin/env node
import path from 'node:path';
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

if (failures.length) {
  console.error('HOOK/STATUSLINE TESTS FAILED');
  failures.forEach(failure => console.error(`- ${failure}`));
  process.exit(1);
}
console.log('HOOK/STATUSLINE TESTS PASSED');
