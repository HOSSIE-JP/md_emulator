'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

function readPackageConfig() {
  return fs.readFileSync(path.join(__dirname, '..', 'electron-builder.yml'), 'utf-8');
}

test('packaging includes the bundled game editor sample projects', () => {
  const config = readPackageConfig();

  assert.match(config, /from:\s*projects\/sample_block_game/);
  assert.match(config, /to:\s*projects\/sample_block_game/);
  assert.match(config, /from:\s*projects\/sample_slideshow/);
  assert.match(config, /to:\s*projects\/sample_slideshow/);
  assert.doesNotMatch(config, /from:\s*projects\/sample\s/);
  assert.doesNotMatch(config, /to:\s*projects\/sample\s/);
});
