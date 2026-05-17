'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const { loadPreloadWithMockedElectron } = require('./helpers/mock-electron');

test('preload exposes pceAPI methods', async () => {
  const { exposed, invocations } = loadPreloadWithMockedElectron(path.join(__dirname, '..', 'preload.js'));
  assert.equal(typeof exposed.pceAPI.runBuild, 'function');
  await exposed.pceAPI.runBuild({ dryRun: true });
  assert.equal(invocations[0].channel, 'build:run');
});
