'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
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

test('audio-converter declares renderer-invokable main hook capability', () => {
  const manifest = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'plugins', 'audio-converter', 'manifest.json'),
    'utf-8',
  ));
  const rendererSource = fs.readFileSync(
    path.join(__dirname, '..', 'plugins', 'audio-converter', 'renderer.js'),
    'utf-8',
  );

  assert.deepEqual(manifest.mainApi.hooks, ['convertAudio']);
  assert.deepEqual(manifest.mainApi.capabilities, ['audio-convert']);
  assert.match(rendererSource, /invokeHook\(plugin\.id,\s*['"]convertAudio['"]/);
  assert.match(rendererSource, /readTempFileAsDataUrl/);
  assert.doesNotMatch(rendererSource, /previewConvertAudio/);
  assert.doesNotMatch(rendererSource, /convertAndWriteAudioAsset/);
  assert.doesNotMatch(rendererSource, /pluginId:\s*['"]audio-converter['"]/);
});

test('asset-manager declares v2.4 asset provider capabilities', () => {
  const manifest = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'plugins', 'asset-manager', 'manifest.json'),
    'utf-8',
  ));
  const rendererSource = fs.readFileSync(
    path.join(__dirname, '..', 'plugins', 'asset-manager', 'renderer.js'),
    'utf-8',
  );

  assert.ok(manifest.renderer.capabilities.includes('asset-type-provider'));
  assert.ok(manifest.renderer.capabilities.includes('asset-import-handler'));
  assert.ok(manifest.renderer.capabilities.includes('image-import-pipeline'));
  assert.match(rendererSource, /registerCapability\(['"]asset-type-provider['"]/);
  assert.match(rendererSource, /registerCapability\(['"]image-import-pipeline['"]/);
  assert.match(rendererSource, /paletteSlots\s*=\s*unique\s*\+\s*\(hasTransparent\s*\?\s*1\s*:\s*0\)/);
  assert.match(rendererSource, /originalIndexed\s*=\s*extractIndexedSourcePalette\(read\.dataUrl\)/);
  assert.match(rendererSource, /originalIndexed\.format === 'bmp'/);
  assert.match(rendererSource, /extractIndexedBmpPalette\(dataUrl\)/);
  assert.match(rendererSource, /encodeBmpSourceAsIndexedPng\(originalIndexed\)/);
  assert.match(rendererSource, /targetExtension:\s*['"]\.png['"]/);
  assert.match(rendererSource, /targetMatchesSource\s*=/);
  assert.match(rendererSource, /convertedDataUrl:\s*bmpDataUrl/);
  assert.match(rendererSource, /resizeResult\.skipped/);
  assert.match(rendererSource, /extractIndexedPngPalette\(workingDataUrl\)/);
  assert.match(rendererSource, /encodeImageDataWithIndexedPalette\(imageData,\s*preserveIndexed\)/);
  assert.match(rendererSource, /ensureIndexedTransparentIndexUsed\(savedDataUrl,\s*extractIndexedPngPalette\(savedDataUrl\)\)/);
  assert.match(rendererSource, /indices\[indices\.length - 1\]\s*=\s*0/);
  assert.match(rendererSource, /savedDataUrl\s*=\s*workingDataUrl/);
  assert.match(rendererSource, /convertedDataUrl:\s*savedDataUrl/);
  assert.match(rendererSource, /mountReloadButton\(\{ root,\s*api,\s*logger \}\)/);
  assert.match(rendererSource, /reloadResources\?\.\(\{ keepSelection:\s*true \}\)/);
  assert.match(rendererSource, /buildPreviewPaletteFromDataUrl/);
});

function makePngChunk(type, data) {
  const chunk = Buffer.alloc(12 + data.length);
  chunk.writeUInt32BE(data.length, 0);
  chunk.write(type, 4, 4, 'ascii');
  data.copy(chunk, 8);
  return chunk;
}

function makeIndexedPngDataUrl({ palette, transparentIndex }) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(1, 0);
  ihdr.writeUInt32BE(1, 4);
  ihdr[8] = 8;
  ihdr[9] = 3;
  const plte = Buffer.from(palette.flatMap((color) => [color.r, color.g, color.b]));
  const trns = Buffer.alloc(transparentIndex + 1, 255);
  trns[transparentIndex] = 0;
  const bytes = Buffer.concat([
    signature,
    makePngChunk('IHDR', ihdr),
    makePngChunk('PLTE', plte),
    makePngChunk('tRNS', trns),
    makePngChunk('IEND', Buffer.alloc(0)),
  ]);
  return `data:image/png;base64,${bytes.toString('base64')}`;
}

test('asset-manager preview palette exposes exactly 16 slots including transparency', async () => {
  const renderer = await importPluginModule('asset-manager', 'renderer.js');
  const dataUrl = makeIndexedPngDataUrl({
    transparentIndex: 2,
    palette: [
      { r: 0, g: 0, b: 0 },
      { r: 252, g: 0, b: 0 },
      { r: 0, g: 252, b: 0 },
    ],
  });

  const palette = renderer.buildPreviewPaletteFromDataUrl(dataUrl, [], { maxColors: 16 });
  assert.equal(palette.length, 16);
  assert.equal(palette[2].transparent, true);
  assert.equal(palette[2].g, 252);
  assert.equal(palette[15].empty, true);
});

test('asset preview renderer uses asset-manager palette helper and 16 swatches', () => {
  const rendererSource = fs.readFileSync(
    path.join(__dirname, '..', 'renderer', 'renderer.js'),
    'utf-8',
  );

  assert.match(rendererSource, /assets:\s*\{/);
  assert.match(rendererSource, /reloadResources:\s*async/);
  assert.match(rendererSource, /getPluginCapability\(['"]asset-manager['"]\)\?\.buildPreviewPalette/);
  assert.match(rendererSource, /extractDisplayPalette\(imageData,\s*16\)/);
  assert.match(rendererSource, /renderPaletteSwatches\(el\.inlinePalette,\s*colors\)/);
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
