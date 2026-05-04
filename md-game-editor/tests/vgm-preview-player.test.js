'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const { pathToFileURL } = require('node:url');

async function loadPreviewModule() {
  return import(pathToFileURL(path.join(__dirname, '..', 'plugins', 'midi-converter', 'vgm-preview-player.mjs')).href);
}

function makeVgmFixture() {
  const header = Buffer.alloc(0x40);
  header.write('Vgm ', 0, 4, 'ascii');
  header.writeUInt32LE(0x00000151, 0x08);
  header.writeUInt32LE(3579545, 0x0c);
  header.writeUInt32LE(7670454, 0x2c);
  const body = Buffer.from([
    0x52, 0xa0, 0x34,
    0x52, 0xa4, 0x2c,
    0x52, 0x28, 0xf0,
    0x50, 0x90,
    0x61, 0x10, 0x00,
    0x67, 0x66, 0x00, 0x02, 0x00, 0x00, 0x00, 0xaa, 0xbb,
    0x70,
    0x52, 0x28, 0x00,
    0x66,
  ]);
  return Buffer.concat([header, body]);
}

test('VGM preview parser reads YM2612, PSG, waits, data blocks, and end', async () => {
  const preview = await loadPreviewModule();
  const parsed = preview.parseVgmBytes(makeVgmFixture());

  assert.equal(parsed.ok, true, parsed.error);
  assert.equal(parsed.version, 0x00000151);
  assert.equal(parsed.ym2612Clock, 7670454);
  assert.equal(parsed.sn76489Clock, 3579545);
  assert.equal(parsed.meta.ym2612Writes, 4);
  assert.equal(parsed.meta.psgWrites, 1);
  assert.equal(parsed.meta.waitSamples, 17);
  assert.equal(parsed.meta.durationSec, 17 / 44100);
  assert.equal(parsed.warnings.length, 0);
});

test('VGM preview parser reports unsupported commands and canPreview only accepts VGM sources', async () => {
  const preview = await loadPreviewModule();
  const fixture = Buffer.concat([makeVgmFixture().subarray(0, -1), Buffer.from([0xff])]);
  const parsed = preview.parseVgmBytes(fixture);

  assert.equal(parsed.ok, true, parsed.error);
  assert.ok(parsed.warnings.some((warning) => warning.includes('Unsupported VGM command')));
  assert.equal(preview.canPreviewVgmEntry({ type: 'XGM2', sourcePath: 'music/theme.vgm' }), true);
  assert.equal(preview.canPreviewVgmEntry({ type: 'XGM2', files: ['music/theme.vgm'] }), true);
  assert.equal(preview.canPreviewVgmEntry({ type: 'XGM', sourcePath: 'music/theme.xgm' }), false);
});
