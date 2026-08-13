#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

let raw = '';
for await (const chunk of process.stdin) raw += chunk;
let data = {};
try { data = JSON.parse(raw || '{}'); } catch { data = {}; }

const cwd = data.workspace?.current_dir || data.cwd || process.cwd();
// project_dir is the original launch directory; install-state records live
// at the project root, so check it first (the session may have navigated).
const projectDir = data.workspace?.project_dir || cwd;
const model = data.model?.display_name || data.model?.id || 'Claude';
const effort = data.effort?.level ? `/${data.effort.level}` : '';
const fast = data.fast_mode ? '/fast' : '';
const pct = Math.floor(data.context_window?.used_percentage || 0);
const project = path.basename(cwd) || cwd;

// Environment identity marker: show "MAD_OS Env" when the governed MAD OS
// environment is active — i.e. the session env flag is set (settings.json
// "env" block) or the project root carries an install-state record.
const madEnv =
  process.env.MADVENTURES_ENV === '1' ||
  fs.existsSync(path.join(projectDir, '.claude', 'INSTALLATION_STATE.json')) ||
  fs.existsSync(path.join(projectDir, '.claude', 'MADVENTURES_INSTALLATION_STATE.json')) ||
  fs.existsSync(path.join(cwd, '.claude', 'INSTALLATION_STATE.json')) ||
  fs.existsSync(path.join(cwd, '.claude', 'MADVENTURES_INSTALLATION_STATE.json'));
const envTag = madEnv ? '[MAD_OS Env] ' : '';

function git(args) {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 250 }).trim();
  } catch { return ''; }
}
const branch = git(['branch', '--show-current']) || git(['rev-parse', '--short', 'HEAD']);
const dirty = git(['status', '--porcelain']) ? '*' : '';
const doctrine = fs.existsSync(path.join(cwd, '04-agents', 'role-registry.md')) ? 'founderos:builder' : 'madventures';
const pr = data.pr?.number ? ` PR#${data.pr.number}` : '';
const wt = data.worktree?.name ? ` wt:${data.worktree.name}` : '';
console.log(`${envTag}[${doctrine}] ${project} ${branch ? `@${branch}${dirty}` : ''}${pr}${wt} | ${model}${effort}${fast} | ctx ${pct}%`.replace(/\s+/g, ' ').trim());
