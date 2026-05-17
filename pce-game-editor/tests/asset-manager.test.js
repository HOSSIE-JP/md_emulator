'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const assets = require('../pce-asset-manager');

function tempProject() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pce-editor-assets-'));
}

test('asset document normalizes image and sound assets', () => {
  const project = tempProject();
  const doc = assets.writeAssetDocument(project, {
    assets: [
      { id: 'image', type: 'image', source: 'assets/images/a.pceimg.json' },
      { id: 'beep', type: 'psg-sequence', options: { period: 400 } },
    ],
  });
  assert.equal(doc.assets.length, 2);
  assert.equal(assets.readAssetDocument(project).assets[0].type, 'image');
});

test('asset source cannot escape project root', () => {
  const project = tempProject();
  assert.throws(() => assets.resolveAssetSource(project, {
    id: 'bad',
    type: 'image',
    source: '../bad.png',
  }), /配下のみ/);
});

test('generateAssetSources writes C and header files', () => {
  const project = tempProject();
  fs.mkdirSync(path.join(project, 'assets', 'images'), { recursive: true });
  fs.writeFileSync(path.join(project, 'assets', 'images', 'sample.pceimg.json'), JSON.stringify({
    width: 2,
    height: 2,
    pixels: [[0, 1], [1, 0]],
  }), 'utf-8');
  assets.writeAssetDocument(project, {
    assets: [
      { id: 'image', type: 'image', source: 'assets/images/sample.pceimg.json' },
      { id: 'beep', type: 'psg-sequence', options: { period: 300 } },
    ],
  });
  const result = assets.generateAssetSources(project);
  assert.equal(result.assetCount, 2);
  const source = fs.readFileSync(result.sourcePath, 'utf-8');
  assert.match(source, /pce_editor_tone_period = 300/);
  assert.match(source, /pce_editor_cc65_bss_anchor/);
});
