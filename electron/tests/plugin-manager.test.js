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

function writePlugin(userData, id, manifest) {
  const pluginDir = path.join(userData, 'plugins', id);
  fs.mkdirSync(pluginDir, { recursive: true });
  fs.writeFileSync(
    path.join(pluginDir, 'manifest.json'),
    JSON.stringify({ id, name: id, version: '1.0.0', types: ['build'], ...manifest }, null, 2),
    'utf-8',
  );
  fs.writeFileSync(path.join(pluginDir, 'index.js'), "'use strict';\nmodule.exports = {};\n", 'utf-8');
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
