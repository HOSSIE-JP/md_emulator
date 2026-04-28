'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function makeTempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'md-editor-plugin-test-'));
}

function writePlugin(userData, id, manifest, files = {}) {
  const pluginDir = path.join(userData, 'plugins', id);
  fs.mkdirSync(pluginDir, { recursive: true });
  fs.writeFileSync(
    path.join(pluginDir, 'manifest.json'),
    JSON.stringify({ id, name: id, version: '1.0.0', types: ['build'], ...manifest }, null, 2),
    'utf-8',
  );
  fs.writeFileSync(path.join(pluginDir, 'index.js'), "'use strict';\nmodule.exports = {};\n", 'utf-8');
  Object.entries(files).forEach(([relativePath, content]) => {
    const abs = path.join(pluginDir, relativePath);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, content, 'utf-8');
  });
}

test('listPlugins reads user plugins and normalizes manifest fields', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'alpha', {
    name: 'Alpha Plugin',
    types: ['editor', 'asset'],
    hooks: ['getTab', 'onActivate'],
    dependencies: ['beta', 'beta', 'gamma'],
    tab: { label: 'Alpha' },
  });

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const alpha = pluginManager.listPlugins().find((plugin) => plugin.id === 'alpha');

  assert.equal(alpha.name, 'Alpha Plugin');
  assert.deepEqual(alpha.pluginTypes, ['editor', 'asset']);
  assert.equal(alpha.pluginType, 'editor');
  assert.deepEqual(alpha.hooks, ['getTab', 'onActivate']);
  assert.deepEqual(alpha.dependencies, ['beta', 'gamma']);
  assert.equal(alpha.enabled, true);
  assert.equal(alpha.isUserPlugin, true);
});

test('setEnabledWithDependencies enables dependencies and reports missing ones', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'alpha', { dependencies: ['beta', 'missing-plugin'] });
  writePlugin(userData, 'beta', {});

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  pluginManager.setEnabled('alpha', false);
  pluginManager.setEnabled('beta', false);

  const result = pluginManager.setEnabledWithDependencies('alpha', true);
  const state = JSON.parse(fs.readFileSync(path.join(userData, 'plugins-state.json'), 'utf-8'));

  assert.equal(result.ok, true);
  assert.deepEqual(new Set(result.changedIds), new Set(['alpha', 'beta']));
  assert.deepEqual(result.missingDependencies, ['missing-plugin']);
  assert.equal(state.alpha.enabled, true);
  assert.equal(state.beta.enabled, true);
});

test('setEnabledWithDependencies disables dependent plugins', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'alpha', { dependencies: ['beta'] });
  writePlugin(userData, 'beta', {});

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const result = pluginManager.setEnabledWithDependencies('beta', false);
  const state = JSON.parse(fs.readFileSync(path.join(userData, 'plugins-state.json'), 'utf-8'));

  assert.equal(result.ok, true);
  assert.deepEqual(new Set(result.changedIds), new Set(['alpha', 'beta']));
  assert.equal(state.alpha.enabled, false);
  assert.equal(state.beta.enabled, false);
});

test('listPlugins exposes safe renderer module metadata', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'alpha', {
    types: ['editor'],
    tab: { label: 'Alpha', page: 'alpha' },
    renderer: {
      entry: 'renderer.js',
      styles: ['style.css'],
      page: 'alpha',
      capabilities: ['page', 'alpha-tool', 'alpha-tool'],
    },
  }, {
    'renderer.js': 'export function activatePlugin() {}\n',
    'style.css': '.alpha {}\n',
  });

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const alpha = pluginManager.listPlugins().find((plugin) => plugin.id === 'alpha');
  const assets = pluginManager.getRendererAssets('alpha');

  assert.equal(alpha.hasRenderer, true);
  assert.equal(new URL(alpha.rendererAssets.scriptUrl).protocol, 'file:');
  assert.deepEqual(alpha.renderer.capabilities, ['page', 'alpha-tool']);
  assert.equal(assets.ok, true);
  assert.equal(assets.renderer.page, 'alpha');
});

test('listPlugins rejects renderer files outside the plugin directory', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'alpha', {
    renderer: {
      entry: '../outside.js',
      styles: ['style.css'],
      capabilities: ['page'],
    },
  }, {
    'style.css': '.alpha {}\n',
  });

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const alpha = pluginManager.listPlugins().find((plugin) => plugin.id === 'alpha');

  assert.equal(alpha.hasRenderer, false);
  assert.equal(alpha.rendererAssets, null);
  assert.match(alpha.renderer.error, /outside plugin directory/);
});

test('user plugins override builtin renderer assets for the same id', () => {
  const userData = makeTempUserData();
  writePlugin(userData, 'asset-manager', {
    types: ['editor', 'asset'],
    tab: { label: 'User Assets', page: 'assets' },
    renderer: {
      entry: 'user-renderer.js',
      styles: ['user-style.css'],
      page: 'assets',
      capabilities: ['page', 'asset-manager'],
    },
  }, {
    'user-renderer.js': 'export function activatePlugin() {}\n',
    'user-style.css': '.user-assets {}\n',
  });

  const pluginManager = loadWithMockedElectron(path.join(__dirname, '..', 'plugin-manager.js'), { userData });
  const assetManager = pluginManager.listPlugins().find((plugin) => plugin.id === 'asset-manager');

  assert.equal(assetManager.isUserPlugin, true);
  assert.equal(assetManager.hasRenderer, true);
  assert.match(new URL(assetManager.rendererAssets.scriptUrl).pathname, /user-renderer\.js$/);
  assert.equal(assetManager.name, 'asset-manager');
});
