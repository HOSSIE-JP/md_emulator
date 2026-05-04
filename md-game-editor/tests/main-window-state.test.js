'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'md-editor-window-test-'));
}

function loadMainForWindowState(userData) {
  return loadWithMockedElectron(path.join(__dirname, '..', 'main.js'), {
    userData,
    app: {
      whenReady() {
        return { then() {} };
      },
    },
  }).__test;
}

function loadMainWithBuildSystem(userData) {
  delete require.cache[require.resolve('../build-system')];
  delete require.cache[require.resolve('../plugin-manager')];
  const main = loadWithMockedElectron(path.join(__dirname, '..', 'main.js'), {
    userData,
    app: {
      whenReady() {
        return { then() {} };
      },
    },
  }).__test;
  return {
    main,
    buildSystem: require('../build-system'),
  };
}

test('main window bounds are clamped before saving or restoring', () => {
  const api = loadMainForWindowState(makeTempUserData());

  assert.deepEqual(api.normalizeWindowBounds({ width: 100, height: 100 }), {
    width: 960,
    height: 640,
  });
  assert.deepEqual(api.normalizeWindowBounds({ x: 12.6, y: 40.2, width: 1440.4, height: 900.5 }), {
    width: 1440,
    height: 901,
  });
});

test('main window bounds persist to userData and restore on next read', () => {
  const userData = makeTempUserData();
  const api = loadMainForWindowState(userData);
  const fakeWindow = {
    isDestroyed: () => false,
    getNormalBounds: () => ({ x: 32, y: 48, width: 1366, height: 768 }),
  };

  assert.equal(api.saveMainWindowBounds(fakeWindow), true);
  assert.deepEqual(api.readMainWindowBounds(), { width: 1366, height: 768 });

  const statePath = path.join(userData, 'window-state.json');
  assert.ok(fs.existsSync(statePath));
});

test('log snapshots are normalized and capped for popout forwarding', () => {
  const api = loadMainForWindowState(makeTempUserData());
  const entries = Array.from({ length: 4002 }, (_, index) => ({
    source: index === 4001 ? '' : 'build',
    text: `line ${index}`,
    level: index === 4001 ? '' : 'warn',
    timestamp: index,
  }));

  const snapshot = api.normalizeLogSnapshot({ entries });
  assert.equal(snapshot.entries.length, 4000);
  assert.equal(snapshot.entries[0].text, 'line 2');
  const normalizedEntry = api.normalizeLogEntry({ text: 'hello' });
  assert.equal(normalizedEntry.source, 'app');
  assert.equal(normalizedEntry.text, 'hello');
  assert.equal(normalizedEntry.level, 'info');
  assert.equal(typeof normalizedEntry.timestamp, 'number');
});

test('asset source picker default filter includes MIDI music files', () => {
  const api = loadMainForWindowState(makeTempUserData());
  const assetFilter = api.DEFAULT_ASSET_FILE_FILTERS.find((filter) => filter.name === 'Assets');

  assert.ok(assetFilter);
  assert.ok(assetFilter.extensions.includes('mid'));
  assert.ok(assetFilter.extensions.includes('midi'));
  assert.deepEqual(api.normalizeDialogFilters([]), api.DEFAULT_ASSET_FILE_FILTERS);
});

test('project plugin roles restore exclusive plugin enabled state in main process', () => {
  const userData = makeTempUserData();
  const { main, buildSystem } = loadMainWithBuildSystem(userData);
  const projectDir = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'md-editor-role-project-')), 'demo');

  buildSystem.createProject(projectDir, {
    title: 'Role Sync',
    pluginRoles: { builder: 'block-game-builder' },
  }, 'int main(void) { return 0; }\n');

  const result = main.syncProjectPluginRoleState();
  const pluginState = JSON.parse(fs.readFileSync(path.join(userData, 'plugins-state.json'), 'utf-8'));

  assert.equal(result.ok, true);
  assert.equal(result.synced[0].roleId, 'builder');
  assert.equal(result.synced[0].pluginId, 'block-game-builder');
  assert.notEqual(pluginState['block-game-builder']?.enabled, false);
  assert.notEqual(pluginState['block-stage-editor']?.enabled, false);
  assert.equal(pluginState.slideshow.enabled, false);
});
