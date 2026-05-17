'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const portable = require('../portable-paths');

test('dev portable data is always under pce-game-editor/data', () => {
  const app = { isPackaged: false, getPath() { throw new Error('no app path'); } };
  assert.equal(
    portable.resolvePortableDataDir({ app, dirname: '/repo/pce-game-editor', platform: 'darwin' }),
    path.join('/repo/pce-game-editor', 'data'),
  );
});

test('packaged macOS data is next to the .app bundle', () => {
  const app = {
    isPackaged: true,
    getPath(name) {
      assert.equal(name, 'exe');
      return '/Applications/PCEGameEditor.app/Contents/MacOS/PCEGameEditor';
    },
  };
  assert.equal(
    portable.resolvePortableDataDir({ app, dirname: '/repo/pce-game-editor', platform: 'darwin' }),
    '/Applications/data',
  );
});

test('applyPortableMode sets userData and logs', () => {
  const calls = [];
  const app = {
    isPackaged: false,
    setPath(name, value) { calls.push([name, value]); },
  };
  const dataDir = portable.applyPortableMode(app, { dirname: '/repo/pce-game-editor', platform: 'linux' });
  assert.equal(dataDir, '/repo/pce-game-editor/data');
  assert.deepEqual(calls, [
    ['userData', '/repo/pce-game-editor/data'],
    ['logs', '/repo/pce-game-editor/data/logs'],
  ]);
});
