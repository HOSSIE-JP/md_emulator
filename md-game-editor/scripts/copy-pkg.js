const fs = require('fs');
const path = require('path');

const appRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(appRoot, '..');

const fromPkg = path.join(repoRoot, 'frontend', 'pkg');
const toPkg = path.join(appRoot, 'pkg');
const fromWrapper = path.join(repoRoot, 'frontend', 'md-emulator.js');
const fromTypes = path.join(repoRoot, 'frontend', 'md-emulator.d.ts');
const toWrapper = path.join(appRoot, 'md-emulator.js');
const toTypes = path.join(appRoot, 'md-emulator.d.ts');
const fromPlayer = path.join(repoRoot, 'frontend', 'wasm-player.js');
const toPlayer = path.join(appRoot, 'wasm-player.js');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    ensureDir(dest);
    for (const name of fs.readdirSync(src)) {
      copyRecursive(path.join(src, name), path.join(dest, name));
    }
    return;
  }

  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function main() {
  if (!fs.existsSync(fromPkg)) {
    throw new Error(`missing source pkg directory: ${fromPkg}`);
  }

  copyRecursive(fromPkg, toPkg);

  if (!fs.existsSync(fromWrapper)) {
    throw new Error(`missing wrapper file: ${fromWrapper}`);
  }
  copyRecursive(fromWrapper, toWrapper);

  if (fs.existsSync(fromTypes)) {
    copyRecursive(fromTypes, toTypes);
  }

  if (fs.existsSync(fromPlayer)) {
    copyRecursive(fromPlayer, toPlayer);
  }

  console.log('Copied frontend WASM assets into md-game-editor directory.');
}

main();
