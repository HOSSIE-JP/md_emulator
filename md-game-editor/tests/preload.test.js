'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const { loadPreloadWithMockedElectron } = require('./helpers/mock-electron');

test('main preload exposes renderer API methods with the expected IPC channels', async () => {
  const { exposed, invocations, listeners } = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'preload.js'));
  const api = exposed.electronAPI;

  assert.equal(typeof api.openRomDialog, 'function');
  assert.equal(typeof api.generateProject, 'function');
  assert.equal(typeof api.listResDefinitions, 'function');
  assert.equal(typeof api.pickFile, 'function');
  assert.equal(typeof api.readTempFileAsDataUrl, 'function');
  assert.equal(typeof api.listPlugins, 'function');
  assert.equal(typeof api.getPluginRendererAssets, 'function');
  assert.equal(typeof api.invokePluginHook, 'function');
  assert.equal(typeof api.getPluginRoles, 'function');
  assert.equal(typeof api.setPluginRole, 'function');
  assert.equal(typeof api.saveProjectConfig, 'function');
  assert.equal(typeof api.openLogWindow, 'function');
  assert.equal(typeof api.syncLogWindow, 'function');
  assert.equal(typeof api.appendLogWindowEntry, 'function');
  assert.equal(typeof api.exportHtml, 'function');
  assert.equal(typeof api.getProjectStartupState, 'function');
  assert.equal(typeof api.quitApp, 'function');

  await api.readRomFile('game.bin');
  await api.pickFile({ title: 'Pick' });
  await api.readTempFileAsDataUrl('tmp.wav', { deleteAfter: true });
  await api.setPluginRole('builder', 'slideshow');
  await api.saveProjectConfig({ title: 'Saved' });
  await api.getPluginRendererAssets('asset-manager');
  await api.invokePluginHook('audio-converter', 'convertAudio', { sourcePath: 'in.wav' });
  await api.openLogWindow({ entries: [] });
  await api.appendLogWindowEntry({ source: 'app', text: 'hello' });
  await api.createCodeEntry({ path: 'src/new.c', type: 'file' });
  await api.getProjectStartupState();
  await api.quitApp();

  assert.deepEqual(invocations.slice(-5), [
    { channel: 'log:openWindow', args: [{ entries: [] }] },
    { channel: 'log:appendEntry', args: [{ source: 'app', text: 'hello' }] },
    { channel: 'codefs:create', args: [{ path: 'src/new.c', type: 'file' }] },
    { channel: 'project:getStartupState', args: [] },
    { channel: 'app:quit', args: [] },
  ]);

  assert.deepEqual(invocations.find((entry) => entry.channel === 'build:saveProjectConfig'), {
    channel: 'build:saveProjectConfig',
    args: [{ title: 'Saved' }],
  });

  let received = null;
  api.onBuildLog((payload) => { received = payload; });
  listeners.get('build-log')({}, { line: 'ok' });
  assert.deepEqual(received, { line: 'ok' });
});

test('setup preload exposes setup IPC helpers and progress listener', async () => {
  const { exposed, invocations, listeners } = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'setup-preload.js'));
  const api = exposed.electronSetup;

  await api.getStatus();
  await api.downloadSgdk('v2.11');
  await api.setMarsdevPath('C:/marsdev');

  assert.deepEqual(invocations, [
    { channel: 'setup:getStatus', args: [] },
    { channel: 'setup:downloadSgdk', args: ['v2.11'] },
    { channel: 'setup:setMarsdevPath', args: ['C:/marsdev'] },
  ]);

  let received = null;
  api.onProgress((payload) => { received = payload; });
  listeners.get('setup-progress')({}, { percent: 50 });
  assert.deepEqual(received, { percent: 50 });
});

test('testplay and debug preload APIs route to their IPC channels', async () => {
  const testplay = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'plugins', 'standard-emulator', 'testplay-preload.js'));
  await testplay.exposed.electronTestPlay.openDebugWindow({ tab: 'vram' });
  await testplay.exposed.electronTestPlay.getSettings();
  assert.deepEqual(testplay.invocations, [
    { channel: 'window:openDebug', args: [{ tab: 'vram' }] },
    { channel: 'testplay:getSettings', args: [] },
  ]);

  const settings = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'testplay-settings-preload.js'));
  await settings.exposed.testPlaySettingsAPI.saveSettings({ gamepadDeadzone: 0.25 });
  assert.deepEqual(settings.invocations, [
    { channel: 'testplay:saveSettings', args: [{ gamepadDeadzone: 0.25 }] },
  ]);

  const debug = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'debug-preload.js'));
  await debug.exposed.electronDebug.getWasmSnapshot();
  assert.deepEqual(debug.invocations, [
    { channel: 'debug:getWasmSnapshot', args: [{}] },
  ]);
});

test('api testplay preload routes API lifecycle IPC channels', async () => {
  const api = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'plugins', 'standard-api-emulator', 'api-testplay-preload.js'));

  await api.exposed.apiTestPlay.stopApiServer();
  await api.exposed.apiTestPlay.isApiServerRunning();

  assert.deepEqual(api.invocations, [
    { channel: 'api:stopServer', args: [] },
    { channel: 'api:isRunning', args: [] },
  ]);
});
