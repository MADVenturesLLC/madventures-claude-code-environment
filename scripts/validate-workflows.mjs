#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
for (const relative of [
  'project/.claude/workflows',
  'plugin/madventures-founderos/workflows',
  'VISIBLE_PROJECT_TEMPLATE/CLAUDE_FOLDER_CONTENTS/workflows',
]) {
  const directory = path.join(root, relative);
  const scripts = fs.existsSync(directory) ? fs.readdirSync(directory).filter(name => name.endsWith('.js')) : [];
  if (scripts.length) failures.push(`${relative}: executable JavaScript orchestration remains: ${scripts.join(', ')}`);
}

const migrationPath = path.join(root, 'python-control-plane', 'WORKFLOW_MIGRATION.json');
const migration = JSON.parse(fs.readFileSync(migrationPath, 'utf8'));
const capabilities = Object.entries(migration.capabilities ?? {});
if (migration.javascriptExecution !== 'retired') failures.push('migration map must retire JavaScript execution');
if (capabilities.length !== 14) failures.push(`migration map must preserve 14 capabilities, found ${capabilities.length}`);
for (const [name, value] of capabilities) {
  if (!['THIN_ADAPTER', 'MERGE'].includes(value.classification)) failures.push(`${name}: invalid classification`);
  if (!value.pythonRoute) failures.push(`${name}: missing Python route`);
}

if (failures.length) {
  console.error('AUTHORITATIVE ENGINE VALIDATION FAILED');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log('AUTHORITATIVE ENGINE VALIDATION PASSED (14 capabilities, 0 executable JavaScript workflows)');
