const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const appRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(appRoot, '..');

function runOrThrow(command, args, options) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    shell: false,
    ...options,
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${result.status}`);
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function copyFile(src, dest) {
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function prepareFrontendAssets() {
  console.log('Preparing frontend WASM assets...');
  runOrThrow(process.execPath, [path.join(appRoot, 'scripts', 'copy-pkg.js')], {
    cwd: appRoot,
  });
}

function prepareMdApiBinary() {
  const isWin = process.platform === 'win32';
  const sourceBin = path.join(repoRoot, 'target', 'release', isWin ? 'md-api.exe' : 'md-api');
  const destBin = path.join(
    appRoot,
    'plugins',
    'standard-api-emulator',
    'bin',
    isWin ? 'md-api.exe' : 'md-api',
  );

  if (!fs.existsSync(sourceBin)) {
    console.log('md-api release binary not found. Building md-api (release)...');
    runOrThrow('cargo', ['build', '-p', 'md-api', '--release'], { cwd: repoRoot });
  }

  if (!fs.existsSync(sourceBin)) {
    throw new Error(`md-api binary was not produced: ${sourceBin}`);
  }

  copyFile(sourceBin, destBin);

  if (!isWin) {
    fs.chmodSync(destBin, 0o755);
  }

  console.log(`Prepared standard-api-emulator md-api binary: ${destBin}`);
}

function injectBuildMeta() {
  runOrThrow(process.execPath, [path.join(appRoot, 'scripts', 'inject-build-meta.js')], {
    cwd: appRoot,
  });
}

function main() {
  console.log('=== Prepare MD Game Editor Distribution Assets ===');
  injectBuildMeta();
  prepareFrontendAssets();
  prepareMdApiBinary();
  console.log('=== Prepare completed ===');
}

main();
