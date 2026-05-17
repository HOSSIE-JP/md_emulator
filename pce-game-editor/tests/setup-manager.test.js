'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function tempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pce-editor-setup-'));
}

test('setup manager stores tools under userData/tools', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  assert.equal(setup.getToolsDir(), path.join(userData, 'tools'));
  assert.equal(setup.getCc65BaseDir(), path.join(userData, 'tools', 'cc65'));
});

test('setup catalog exposes predefined download sources', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const catalog = setup.getDownloadCatalog();
  const cc65 = catalog.tools.find((tool) => tool.kind === 'cc65');
  const llvmMos = catalog.tools.find((tool) => tool.kind === 'llvmMos');
  const emulatorJs = catalog.tools.find((tool) => tool.kind === 'emulatorJs');

  assert.equal(catalog.ok, true);
  assert.equal(cc65.defaultTargetDir, path.join(userData, 'tools', 'cc65'));
  assert.ok(cc65.sources.some((source) => source.source === 'sourceforge'));
  assert.ok(llvmMos.sources.some((source) => source.owner === 'llvm-mos' && source.repo === 'llvm-mos-sdk'));
  assert.ok(emulatorJs.sources.some((source) => source.type === 'cdn-index'));
});

test('setup manager selects matching GitHub release asset for platform and arch', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const release = {
    tag_name: 'v23.0.0',
    assets: [
      { name: 'llvm-mos-sdk-v23.0.0-win64.zip', browser_download_url: 'https://example.com/win.zip' },
      { name: 'llvm-mos-sdk-v23.0.0-darwin-arm64.tar.xz', browser_download_url: 'https://example.com/mac.tar.xz' },
      { name: 'llvm-mos-sdk-v23.0.0-source.zip', browser_download_url: 'https://example.com/source.zip' },
    ],
  };

  const asset = setup.selectReleaseAsset(release, 'llvmMos', { platform: 'darwin', arch: 'arm64' });
  assert.equal(asset.name, 'llvm-mos-sdk-v23.0.0-darwin-arm64.tar.xz');
});

test('setup manager builds disabled version option when release has no matching asset', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const versions = setup.buildGithubReleaseOptions('superfamiconv', [{
    tag_name: 'v0.11.0',
    html_url: 'https://github.com/Optiroc/SuperFamiconv/releases/tag/v0.11.0',
    assets: [
      { name: 'superfamiconv_win64_v0.11.0.zip', browser_download_url: 'https://example.com/win.zip' },
    ],
  }], { platform: 'darwin', arch: 'arm64' });

  assert.equal(versions.length, 1);
  assert.equal(versions[0].available, false);
  assert.match(versions[0].note, /実行バイナリ/);
});

test('setup manager exposes fixed cc65 snapshot as one-click Windows download', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const versions = setup.buildFixedVersionOptions('cc65', { platform: 'win32' });

  assert.equal(versions[0].available, true);
  assert.equal(versions[0].archiveName, 'cc65-snapshot-win32.zip');
  assert.match(versions[0].downloadUrl, /^https:\/\/sourceforge\.net\/projects\/cc65\//);
});

test('setup manager builds macOS cc65 Homebrew bottle options', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const formula = {
    versions: { stable: '2.19' },
    bottle: {
      stable: {
        files: {
          arm64_sequoia: { url: 'https://ghcr.io/v2/homebrew/core/cc65/blobs/sha256:arm64' },
          sonoma: { url: 'https://ghcr.io/v2/homebrew/core/cc65/blobs/sha256:x64' },
          x86_64_linux: { url: 'https://ghcr.io/v2/homebrew/core/cc65/blobs/sha256:linux' },
        },
      },
    },
  };

  const versions = setup.buildHomebrewBottleOptions('cc65', formula, { platform: 'darwin', arch: 'arm64' });
  assert.equal(versions.length, 1);
  assert.equal(versions[0].available, true);
  assert.equal(versions[0].source, 'homebrew-bottle');
  assert.match(versions[0].label, /arm64_sequoia/);
});

test('setup manager parses GHCR bearer challenge for Homebrew bottles', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const auth = setup.parseBearerAuthenticateHeader('Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:homebrew/core/cc65:pull"');

  assert.equal(auth.realm, 'https://ghcr.io/token');
  assert.equal(auth.service, 'ghcr.io');
  assert.equal(auth.scope, 'repository:homebrew/core/cc65:pull');
  assert.equal(
    setup.buildBearerTokenUrl(auth),
    'https://ghcr.io/token?service=ghcr.io&scope=repository%3Ahomebrew%2Fcore%2Fcc65%3Apull',
  );
});

test('setup manager parses EmulatorJS CDN archive versions', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const versions = setup.buildCdnIndexOptions('emulatorJs', [
    '<a href="4.2.2.7z">4.2.2.7z</a>',
    '<a href="4.2.3.7z">4.2.3.7z</a>',
  ].join('\n'));

  assert.equal(versions[0].version, '4.2.3');
  assert.equal(versions[0].archiveName, '4.2.3.7z');
  assert.match(versions[0].downloadUrl, /^https:\/\/cdn\.emulatorjs\.org\/releases\/4\.2\.3\.7z$/);
});

test('setup manager can detect configured tools', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const toolPath = path.join(userData, 'bin', process.platform === 'win32' ? 'cl65.exe' : 'cl65');
  fs.mkdirSync(path.dirname(toolPath), { recursive: true });
  fs.writeFileSync(toolPath, '');
  setup.setToolPath('cc65', toolPath);
  assert.equal(setup.getStatus().cc65.configured, true);
});

test('setup manager detects executable symlinks in large SDK archives', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const binDir = path.join(userData, 'tools', 'llvm-mos-sdk', 'llvm-mos', 'bin');
  fs.mkdirSync(binDir, { recursive: true });
  fs.writeFileSync(path.join(binDir, 'mos-clang'), '');
  fs.symlinkSync('mos-clang', path.join(binDir, 'mos-pce-clang'));

  assert.equal(setup.findExecutable(path.join(userData, 'tools', 'llvm-mos-sdk'), ['mos-pce-clang']), path.join(binDir, 'mos-pce-clang'));
});

test('emulator placeholder records GPL download policy without adding runtime', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const dir = setup.ensureEmulatorPlaceholder();
  const notice = fs.readFileSync(path.join(dir, 'README.txt'), 'utf-8');
  assert.match(notice, /not bundled/);
  assert.equal(fs.existsSync(path.join(dir, 'loader.js')), false);
});

test('setup manager auto-detects nested EmulatorJS runtime directory', () => {
  const userData = tempUserData();
  const setup = loadWithMockedElectron(path.join(__dirname, '..', 'pce-setup-manager.js'), { userData });
  const runtimeDir = path.join(setup.getEmulatorBaseDir(), 'EmulatorJS-main');
  fs.mkdirSync(path.join(runtimeDir, 'data'), { recursive: true });

  assert.equal(setup.findEmulatorJsRuntimeDir(setup.getEmulatorBaseDir()), runtimeDir);
});
