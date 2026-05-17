'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { resolveUnderRoot } = require('../pce-file-safety');

function tempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pce-editor-path-'));
}

test('resolveUnderRoot accepts project relative paths', () => {
  const root = tempRoot();
  const result = resolveUnderRoot(root, 'src/main.c', 'project');
  assert.equal(result.absPath, path.join(root, 'src', 'main.c'));
  assert.equal(result.relativePath, 'src/main.c');
});

test('resolveUnderRoot rejects traversal and absolute paths', () => {
  const root = tempRoot();
  assert.throws(() => resolveUnderRoot(root, '../outside.c', 'project'), /配下のみ/);
  assert.throws(() => resolveUnderRoot(root, '/tmp/outside.c', 'project'), /配下のみ/);
});

test('resolveUnderRoot rejects symlink escape through existing ancestor', () => {
  const root = tempRoot();
  const outside = tempRoot();
  fs.symlinkSync(outside, path.join(root, 'linked'), 'dir');
  assert.throws(() => resolveUnderRoot(root, 'linked/file.c', 'project'), /escapes root/);
});
