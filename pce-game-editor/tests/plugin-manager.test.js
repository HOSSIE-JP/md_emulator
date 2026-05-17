'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function tempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pce-editor-plugin-'));
}

function writePlugin(userData, id, manifest, files = {}) {
  const dir = path.join(userData, 'plugins', id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify({
    id,
    name: id,
    version: '1.0.0',
    types: ['editor'],
    ...manifest,
  }, null, 2), 'utf-8');
  Object.entries(files).forEach(([rel, content]) => {
    const abs = path.join(dir, rel);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, content, 'utf-8');
  });
}

test('plugin manager exposes renderer assets and roles', () => {
  const userData = tempUserData();
  writePlugin(userData, 'alpha', {
    icon: 'Code',
    roles: [{ id: 'builder', label: 'Build', exclusive: true, order: 10 }],
    renderer: { entry: 'renderer.js', styles: ['style.css'], page: 'alpha', capabilities: ['page', 'page', 'tool'] },
  }, {
    'renderer.js': 'export function activatePlugin() {}\n',
    'style.css': '.alpha {}\n',
  });
  const manager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const plugin = manager.listPlugins().find((entry) => entry.id === 'alpha');
  assert.equal(plugin.icon, 'code');
  assert.equal(plugin.hasRenderer, true);
  assert.deepEqual(plugin.renderer.capabilities, ['page', 'tool']);
  assert.equal(plugin.roles[0].id, 'builder');
});

test('plugin manager rejects renderer paths outside plugin directory', () => {
  const userData = tempUserData();
  writePlugin(userData, 'alpha', {
    renderer: { entry: '../renderer.js', page: 'alpha', capabilities: ['page'] },
  });
  const manager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const plugin = manager.listPlugins().find((entry) => entry.id === 'alpha');
  assert.equal(plugin.hasRenderer, false);
  assert.equal(plugin.rendererAssets, null);
});

test('renderer hook requires hook and mainApi declarations', async () => {
  const userData = tempUserData();
  writePlugin(userData, 'alpha', {
    hooks: ['convert'],
    mainApi: { hooks: ['convert'] },
  }, {
    'index.js': "'use strict'; module.exports = { convert(){ return { ok: true, value: 1 }; } };",
  });
  writePlugin(userData, 'beta', {
    hooks: ['convert'],
  }, {
    'index.js': "'use strict'; module.exports = { convert(){ return { ok: true, value: 1 }; } };",
  });
  const manager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  assert.equal((await manager.invokeRendererHook('alpha', 'convert', {})).ok, true);
  assert.equal((await manager.invokeRendererHook('beta', 'convert', {})).ok, false);
});
