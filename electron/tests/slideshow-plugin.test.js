'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const slideshow = require(path.join(__dirname, '..', 'plugins', 'slideshow', 'index.js'));

test('slideshow build hook limits SGDK source scan to generated main.c', () => {
  const messages = [];
  const result = slideshow.onBuildStart(
    { projectDir: 'project' },
    { logger: { info: (message) => messages.push(message) } },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.makeVariables, { SRC_C: 'src/main.c' });
  assert.match(messages[0], /build start/);
});

test('slideshow build log hook does not duplicate compiler errors', () => {
  const errors = [];
  const result = slideshow.onBuildLog(
    { level: 'error', line: 'src/main.c: error' },
    { logger: { error: (message) => errors.push(message) } },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(errors, []);
});
