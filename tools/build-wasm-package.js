const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..');
const frontendRoot = path.join(repoRoot, 'frontend');
const romsRoot = path.join(frontendRoot, 'roms');

function parseArgs(argv) {
  const options = {
    profile: 'dev',
  };

  for (const arg of argv) {
    if (arg === '--dev') {
      options.profile = 'dev';
      continue;
    }
    if (arg === '--release') {
      options.profile = 'release';
      continue;
    }
    throw new Error(`Unknown option: ${arg}`);
  }

  return options;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    shell: false,
    stdio: 'inherit',
    ...options,
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${result.status}`);
  }
}

function buildWasm(profile) {
  const args = [
    'build',
    'crates/md-wasm',
    '--target',
    'web',
    '--out-dir',
    '../../frontend/pkg',
  ];

  if (profile === 'dev') {
    args.push('--dev');
  } else if (profile === 'release') {
    args.push('--release');
  } else {
    throw new Error(`Unsupported WASM profile: ${profile}`);
  }

  run('wasm-pack', args);
}

function getBuildVersion(profile) {
  if (profile === 'release') {
    const result = spawnSync('git', ['rev-parse', '--short', 'HEAD'], {
      cwd: repoRoot,
      encoding: 'utf8',
      shell: false,
    });

    if (result.status === 0) {
      const sha = result.stdout.trim();
      if (sha) return sha;
    }
  }

  return String(Math.floor(Date.now() / 1000));
}

function writeServiceWorker(profile) {
  const templatePath = path.join(frontendRoot, 'sw.template.js');
  const outputPath = path.join(frontendRoot, 'sw.js');
  const version = getBuildVersion(profile);
  const template = fs.readFileSync(templatePath, 'utf8');
  fs.writeFileSync(outputPath, template.replace(/__BUILD_VERSION__/g, version), 'utf8');
  console.log(`Generated frontend/sw.js (version: ${version})`);
}

function writeBundledRomIndex() {
  fs.mkdirSync(romsRoot, { recursive: true });

  const files = fs
    .readdirSync(romsRoot, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name !== 'index.json')
    .map((entry) => entry.name)
    .sort();

  const indexPath = path.join(romsRoot, 'index.json');
  fs.writeFileSync(indexPath, JSON.stringify({ files }), 'utf8');
  console.log(`Generated frontend/roms/index.json (${files.length} ROMs)`);
}

function main() {
  const { profile } = parseArgs(process.argv.slice(2));
  console.log(`=== Build WASM package (${profile}) ===`);
  buildWasm(profile);
  writeServiceWorker(profile);
  writeBundledRomIndex();
  console.log(`WASM package is ready: ${path.relative(repoRoot, path.join(frontendRoot, 'pkg'))}`);
}

try {
  main();
} catch (error) {
  console.error(error.message || error);
  if (/wasm-pack/.test(String(error.message || error))) {
    console.error('Hint: install wasm-pack first with `cargo install wasm-pack --locked`.');
    console.error('Hint: wasm-pack also bootstraps wasm-bindgen; if that step is denied, check that TEMP/TMP and the Cargo cache are writable.');
  }
  process.exit(1);
}
