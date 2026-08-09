import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const profile = process.argv[2] ?? 'baseline';
let input = '';
for await (const chunk of process.stdin) input += chunk;

try {
  const parsed = JSON.parse(input);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('input must be a JSON object');
} catch (error) {
  process.stderr.write(`MAD Ventures hook denied malformed input: ${error.message}\n`);
  process.exit(2);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const sourceCandidates = [
  path.join(projectRoot, '.claude', 'control-plane', 'src'),
  path.resolve(here, '..', '..', '..', 'python-control-plane', 'src'),
  path.resolve(here, '..', 'python-control-plane', 'src'),
];
const source = sourceCandidates.find(candidate => fs.existsSync(path.join(candidate, 'madclaude', 'hook_cli.py')));
if (!source) {
  process.stderr.write('MAD Ventures hook denied the event because the Python policy engine is unavailable.\n');
  process.exit(2);
}

const configured = process.env.MADCLAUDE_PYTHON ? [[process.env.MADCLAUDE_PYTHON]] : [];
const runtimes = [...configured, ...(process.platform === 'win32' ? [['py', '-3'], ['python']] : [['python3'], ['python']])];
let lastError = '';
for (const [runtime, ...prefix] of runtimes) {
  const child = spawnSync(runtime, [...prefix, '-m', 'madclaude.hook_cli', '--profile', profile], {
    input,
    encoding: 'utf8',
    env: {
      ...process.env,
      PYTHONPATH: source,
      PYTHONDONTWRITEBYTECODE: '1',
      MADCLAUDE_REPO_ROOT: projectRoot,
    },
  });
  if (child.error?.code === 'ENOENT') {
    lastError = child.error.message;
    continue;
  }
  if (child.stdout) process.stdout.write(child.stdout);
  if (child.stderr) process.stderr.write(child.stderr);
  process.exit(child.status ?? 2);
}

process.stderr.write(`MAD Ventures hook denied the event because Python 3 is unavailable${lastError ? `: ${lastError}` : '.'}\n`);
process.exit(2);
