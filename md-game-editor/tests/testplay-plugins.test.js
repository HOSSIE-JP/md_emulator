'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

function readManifest(pluginId) {
  return JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'plugins', pluginId, 'manifest.json'),
    'utf-8',
  ));
}

test('standard WASM emulator owns its bundled testplay assets and handles launch', async () => {
  const pluginDir = path.join(__dirname, '..', 'plugins', 'standard-emulator');
  const manifest = readManifest('standard-emulator');
  const plugin = require(path.join(pluginDir, 'index.js'));

  assert.ok(manifest.permissions.includes('testplay.launch'));
  assert.ok(fs.existsSync(path.join(pluginDir, 'testplay.html')));
  assert.ok(fs.existsSync(path.join(pluginDir, 'testplay-preload.js')));

  let received = null;
  const result = await plugin.onTestPlay({ romPath: 'game.bin' }, {
    testPlay: {
      openWasmWindow: async (options) => {
        received = options;
        return { opened: true };
      },
    },
  });

  assert.deepEqual(received, { romPath: 'game.bin', pluginId: 'standard-emulator' });
  assert.equal(result.ok, true);
  assert.equal(result.handled, true);
});

test('standard API emulator declares UI and opens API-backed testplay window', async () => {
  const pluginDir = path.join(__dirname, '..', 'plugins', 'standard-api-emulator');
  const manifest = readManifest('standard-api-emulator');
  const plugin = require(path.join(pluginDir, 'index.js'));

  assert.equal(manifest.tab.page, 'api-emulator');
  assert.ok(manifest.renderer.capabilities.includes('api-emulator-control'));
  assert.ok(manifest.permissions.includes('api.start'));
  assert.ok(fs.existsSync(path.join(pluginDir, 'api-testplay.html')));
  assert.ok(fs.existsSync(path.join(pluginDir, 'api-testplay-preload.js')));

  let received = null;
  const result = await plugin.onTestPlay({ romPath: 'game.bin' }, {
    testPlay: {
      openApiWindow: async (options) => {
        received = options;
        return { opened: true, port: 8080 };
      },
    },
    logger: { info() {} },
  });

  assert.deepEqual(received, { romPath: 'game.bin', pluginId: 'standard-api-emulator' });
  assert.equal(result.ok, true);
  assert.equal(result.handled, true);
});
