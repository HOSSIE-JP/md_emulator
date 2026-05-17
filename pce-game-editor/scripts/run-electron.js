'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const appRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(appRoot, '..');
const isWin = process.platform === 'win32';
const cliName = isWin ? 'electron.cmd' : 'electron';

const candidates = [
  path.join(appRoot, 'node_modules', '.bin', cliName),
  path.join(repoRoot, 'node_modules', '.bin', cliName),
  path.join(repoRoot, 'md-game-editor', 'node_modules', '.bin', cliName),
];

const electronBin = candidates.find((candidate) => fs.existsSync(candidate)) || 'electron';
const child = spawn(electronBin, ['.'], {
  cwd: appRoot,
  stdio: 'inherit',
  shell: isWin,
});

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code == null ? 1 : code);
});
