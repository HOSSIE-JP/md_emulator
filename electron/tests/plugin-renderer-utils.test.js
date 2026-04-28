'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');

async function importPluginModule(...segments) {
  return import(pathToFileURL(path.join(__dirname, '..', 'plugins', ...segments)).href);
}

test('asset-manager utility functions keep asset defaults stable', async () => {
  const utils = await importPluginModule('asset-manager', 'asset-utils.mjs');

  assert.equal(utils.inferTypeFromExtension('.png'), 'IMAGE');
  assert.equal(utils.inferTypeFromExtension('.mp3'), 'WAV');
  assert.equal(utils.inferTypeFromExtension('.tmx'), 'MAP');
  assert.deepEqual(utils.allowedTypesForExtension('.vgm'), ['XGM', 'XGM2']);
  assert.equal(utils.defaultSubDirForType('SPRITE'), 'sprite');
  assert.equal(utils.defaultSubDirForType('XGM2'), 'music');
  assert.equal(utils.normalizeSymbolName('123 Title Screen.png'), 'title_screen');
});

test('image-quantize utility functions snap and index colors', async () => {
  const utils = await importPluginModule('image-quantize-converter', 'quantize-utils.mjs');
  const imageData = {
    width: 3,
    height: 1,
    data: new Uint8ClampedArray([
      255, 0, 0, 255,
      0, 255, 0, 255,
      255, 0, 0, 0,
    ]),
  };

  assert.deepEqual(utils.snapColorToMegaDrive({ r: 255, g: 17, b: 90 }), { r: 252, g: 0, b: 108 });
  assert.equal(utils.countUniqueColors(imageData), 2);

  const quantized = utils.quantizeToIndexed16(imageData, { reserveTransparent: true });
  assert.equal(quantized.transparentIndex, 0);
  assert.equal(quantized.indices.length, 3);
  assert.equal(quantized.indices[2], 0);
  assert.ok(quantized.palette.length <= 16);
});
