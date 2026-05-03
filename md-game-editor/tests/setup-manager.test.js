'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'md-editor-setup-test-'));
}

function loadSetupManager(userData) {
  return loadWithMockedElectron(path.join(__dirname, '..', 'setup-manager.js'), { userData });
}

test('test play settings are normalized before saving', () => {
  const userData = makeTempUserData();
  const setupManager = loadSetupManager(userData);

  const saved = setupManager.saveTestPlaySettings({
    keyboard: { A: ' KeyQ ', START: '' },
    gamepad: { B: 'button:5', INVALID: 'button:99' },
    gamepadDeadzone: 2,
    debug: { autoRefresh: false, vramTileLayout: 'bad-layout' },
  });

  assert.equal(saved.keyboard.A, 'KeyQ');
  assert.equal(saved.keyboard.START, 'Enter');
  assert.equal(saved.gamepad.B, 'button:5');
  assert.equal(saved.gamepad.INVALID, undefined);
  assert.equal(saved.gamepadDeadzone, 0.95);
  assert.equal(saved.debug.autoRefresh, false);
  assert.equal(saved.debug.vramTileLayout, '256x512');

  const reloaded = setupManager.getTestPlaySettings();
  assert.deepEqual(reloaded, saved);
});

test('default test play settings are returned as independent objects', () => {
  const setupManager = loadSetupManager(makeTempUserData());
  const first = setupManager.getDefaultTestPlaySettings();
  first.keyboard.A = 'KeyP';

  const second = setupManager.getDefaultTestPlaySettings();
  assert.equal(second.keyboard.A, 'KeyA');
});

test('SGDK auto detection picks the newest extracted toolchain with makelib.gen', () => {
  const userData = makeTempUserData();
  const sgdkRoot = path.join(userData, 'tools', 'sgdk');
  fs.mkdirSync(path.join(sgdkRoot, 'SGDK-1.80'), { recursive: true });
  fs.mkdirSync(path.join(sgdkRoot, 'SGDK-2.11'), { recursive: true });
  fs.writeFileSync(path.join(sgdkRoot, 'SGDK-2.11', 'makelib.gen'), '', 'utf-8');

  const setupManager = loadSetupManager(userData);
  const status = setupManager.checkSgdk();

  assert.equal(status.installed, true);
  assert.equal(status.version, '2.11');
  assert.equal(status.path, path.join(sgdkRoot, 'SGDK-2.11'));
});

test('Marsdev path resolution accepts either the root or m68k-elf directory', () => {
  const userData = makeTempUserData();
  const marsdevRoot = path.join(userData, 'marsdev-custom');
  const gdkDir = path.join(marsdevRoot, 'm68k-elf');
  fs.mkdirSync(gdkDir, { recursive: true });
  fs.writeFileSync(path.join(gdkDir, 'makelib.gen'), '', 'utf-8');

  const setupManager = loadSetupManager(userData);
  setupManager.setMarsdevPath(marsdevRoot);

  assert.equal(setupManager.getMarsdevPath(), gdkDir);
  const status = setupManager.checkMarsdev();
  assert.equal(status.installed, true);
  assert.equal(status.path, gdkDir);
  assert.equal(typeof status.version, 'string');
});
