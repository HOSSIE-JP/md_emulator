'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

test('main entry auto-starts under Electron even when require.main differs', () => {
  const main = loadWithMockedElectron(path.join(__dirname, '..', 'main.js'), {
    userData: path.join(__dirname, '..', 'node_modules', '.main-entry-test'),
  });
  assert.equal(main.shouldAutoStart({
    versions: { electron: '41.3.0' },
    mainModule: { id: 'electron-bootstrap' },
    currentModule: { id: 'pce-main' },
  }), true);
});

test('main entry stays import-safe in plain Node tests', () => {
  const main = loadWithMockedElectron(path.join(__dirname, '..', 'main.js'), {
    userData: path.join(__dirname, '..', 'node_modules', '.main-entry-test'),
  });
  assert.equal(main.shouldAutoStart({
    versions: {},
    mainModule: { id: 'test-runner' },
    currentModule: { id: 'pce-main' },
  }), false);
});

test('test play context resolves EmulatorJS data loader and PCE core', () => {
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'pce-main-testplay-'));
  const main = loadWithMockedElectron(path.join(__dirname, '..', 'main.js'), { userData });
  const emulatorRoot = path.join(userData, 'tools', 'emulators', 'emulatorjs-pce');
  const dataDir = path.join(emulatorRoot, 'data');
  const romPath = path.join(userData, 'projects', 'sample', 'out', 'sample.pce');
  fs.mkdirSync(path.join(dataDir, 'cores'), { recursive: true });
  fs.mkdirSync(path.dirname(romPath), { recursive: true });
  fs.writeFileSync(path.join(dataDir, 'loader.js'), '');
  fs.writeFileSync(path.join(dataDir, 'cores', 'mednafen_pce-wasm.data'), '');
  fs.writeFileSync(romPath, Buffer.alloc(8192));

  const runtime = main.resolveEmulatorJsRuntime(emulatorRoot);
  assert.equal(runtime.dataDir, dataDir);
  assert.equal(runtime.loaderPath, path.join(dataDir, 'loader.js'));
  assert.equal(runtime.coreAsset, 'mednafen_pce-wasm.data');

  const context = main.makeTestPlayContext({ romPath });
  assert.equal(context.ok, true);
  assert.match(context.context.emulatorJsDataUrl, /\/data\/$/);
  assert.match(context.context.emulatorJsLoaderUrl, /\/data\/loader\.js$/);
});
