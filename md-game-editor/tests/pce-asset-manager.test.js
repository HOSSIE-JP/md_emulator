'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function makeTempDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function loadAssetManager(userData = makeTempDir('pce-assets-user-data-')) {
  delete require.cache[require.resolve('../pce-asset-manager')];
  delete require.cache[require.resolve('../pce-setup-manager')];
  return loadWithMockedElectron(path.join(__dirname, '..', 'pce-asset-manager.js'), {
    userData,
    paths: { userData, home: makeTempDir('pce-assets-home-') },
  });
}

function makePngDataUrl(width = 16, height = 16) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(16);
  ihdr.writeUInt32BE(13, 0);
  ihdr.write('IHDR', 4, 4, 'ascii');
  ihdr.writeUInt32BE(width, 8);
  ihdr.writeUInt32BE(height, 12);
  return `data:image/png;base64,${Buffer.concat([signature, ihdr, Buffer.alloc(8)]).toString('base64')}`;
}

function writeFile(projectDir, relativePath, bytes) {
  const absPath = path.join(projectDir, relativePath);
  fs.mkdirSync(path.dirname(absPath), { recursive: true });
  fs.writeFileSync(absPath, bytes);
}

test('PCE asset schema supports BG image, sprite, generated metadata, and legacy mosaic', () => {
  const assetManager = loadAssetManager();
  const image = assetManager.normalizeAsset({
    id: 'title-bg',
    type: 'image',
    name: 'Title BG',
    source: 'assets/images/title.png',
    options: { paletteBank: 2, tileBase: 64 },
    data: {
      generated: {
        paletteFile: 'assets/generated/title-bg/palette.bin',
        tilesFile: 'assets/generated/title-bg/tiles.bin',
        mapFile: 'assets/generated/title-bg/map.bin',
        previewFile: 'assets/generated/title-bg/preview.json',
        tileCount: 12,
        paletteCount: 2,
        vramBytes: 512,
        warnings: ['ok'],
      },
    },
  });
  const sprite = assetManager.normalizeAsset({
    id: 'hero',
    type: 'sprite',
    source: 'assets/sprites/hero.png',
    options: { cellWidth: 32, cellHeight: 64, paletteBank: 1 },
  });

  assert.equal(image.options.kind, 'background');
  assert.equal(image.options.cellWidth, 8);
  assert.equal(image.data.generated.tileCount, 12);
  assert.equal(sprite.options.kind, 'sprite');
  assert.equal(sprite.options.cellWidth, 32);
  assert.equal(sprite.options.cellHeight, 64);
  assert.throws(() => assetManager.normalizeAsset({ id: 'bad', type: 'image', source: '/tmp/bad.png' }), /project relative/);
  assert.throws(() => assetManager.normalizeAsset({ id: 'bad', type: 'image', source: 'C:\\bad\\asset.png' }), /project relative/);
  assert.throws(() => assetManager.normalizeAsset({ id: 'bad', type: 'image', source: '../bad.png' }), /project relative/);
});

test('PCE image import constructs SuperFamiconv commands for BG and sprites', () => {
  const assetManager = loadAssetManager();
  const projectDir = makeTempDir('pce-assets-import-');
  const bg = assetManager.importImage(projectDir, {
    sourceFileName: 'title.png',
    convertedDataUrl: makePngDataUrl(32, 16),
    kind: 'background',
    id: 'title',
    tileBase: 48,
  }, { dryRun: true, superfamiconvPath: '/tools/superfamiconv' });
  const sprite = assetManager.importImage(projectDir, {
    sourceFileName: 'hero.bmp',
    convertedDataUrl: makePngDataUrl(32, 32),
    kind: 'sprite',
    id: 'hero',
    cellWidth: 32,
    cellHeight: 32,
  }, { dryRun: true, superfamiconvPath: '/tools/superfamiconv' });

  assert.equal(bg.asset.type, 'image');
  assert.equal(bg.commandInfo.mode, 'pce');
  assert.ok(bg.commandInfo.args.includes('-M'));
  assert.ok(bg.commandInfo.args.includes('pce'));
  assert.ok(bg.commandInfo.args.includes('--out-map'));
  assert.equal(sprite.asset.type, 'sprite');
  assert.equal(sprite.commandInfo.mode, 'pce_sprite');
  assert.ok(sprite.commandInfo.args.includes('pce_sprite'));
  assert.notEqual(sprite.commandInfo.args.indexOf('-S'), -1);
  assert.match(sprite.asset.source, /^assets\/sprites\/hero\.png$/);
});

test('PCE asset manager rejects missing SuperFamiconv for real imports', () => {
  const assetManager = loadAssetManager();
  const projectDir = makeTempDir('pce-assets-missing-tool-');

  assert.throws(() => assetManager.importImage(projectDir, {
    sourceFileName: 'title.png',
    convertedDataUrl: makePngDataUrl(16, 16),
    kind: 'background',
    id: 'title',
  }), /SuperFamiconv/);
});

test('PCE asset preview and reorder stay inside project root', () => {
  const assetManager = loadAssetManager();
  const projectDir = makeTempDir('pce-assets-safety-');
  writeFile(projectDir, 'assets/images/title.png', Buffer.from([137, 80, 78, 71]));
  assetManager.writeAssetDocument(projectDir, {
    version: 1,
    assets: [
      { id: 'a', type: 'image', source: 'assets/images/title.png' },
      { id: 'b', type: 'sprite', source: 'assets/images/title.png' },
    ],
  });

  assert.equal(assetManager.previewSource(projectDir, 'assets/images/title.png').mime, 'image/png');
  assert.throws(() => assetManager.previewSource(projectDir, '../outside.png'), /project/);
  assert.throws(() => assetManager.previewSource(projectDir, '/tmp/outside.png'), /project/);

  const outsideDir = makeTempDir('pce-assets-outside-');
  const outsideFile = path.join(outsideDir, 'outside.png');
  fs.writeFileSync(outsideFile, Buffer.from([1, 2, 3]));
  fs.mkdirSync(path.join(projectDir, 'assets', 'links'), { recursive: true });
  try {
    fs.symlinkSync(outsideFile, path.join(projectDir, 'assets', 'links', 'outside.png'));
    assert.throws(() => assetManager.previewSource(projectDir, 'assets/links/outside.png'), /escapes root/);
  } catch (err) {
    if (!['EPERM', 'EACCES'].includes(err.code)) throw err;
  }

  const reordered = assetManager.reorderAssets(projectDir, ['b', 'a']);
  assert.deepEqual(reordered.assets.map((asset) => asset.id), ['b', 'a']);
});

test('PCE generated assets emit BG and sprite C arrays plus legacy fallback', () => {
  const assetManager = loadAssetManager();
  const projectDir = makeTempDir('pce-assets-generate-');
  writeFile(projectDir, 'assets/generated/bg/palette.bin', Buffer.alloc(32, 0x07));
  writeFile(projectDir, 'assets/generated/bg/tiles.bin', Buffer.alloc(64, 0x11));
  writeFile(projectDir, 'assets/generated/bg/map.bin', Buffer.alloc(8, 0x22));
  writeFile(projectDir, 'assets/generated/spr/palette.bin', Buffer.alloc(32, 0x03));
  writeFile(projectDir, 'assets/generated/spr/patterns.bin', Buffer.alloc(128, 0x44));
  assetManager.writeAssetDocument(projectDir, {
    version: 1,
    assets: [
      {
        id: 'bg',
        type: 'image',
        source: 'assets/images/bg.png',
        options: { width: 16, height: 16, tileBase: 32, mapBase: 0 },
        data: {
          generated: {
            paletteFile: 'assets/generated/bg/palette.bin',
            tilesFile: 'assets/generated/bg/tiles.bin',
            mapFile: 'assets/generated/bg/map.bin',
            tileCount: 2,
            paletteCount: 1,
            vramBytes: 72,
          },
        },
      },
      {
        id: 'spr',
        type: 'sprite',
        source: 'assets/sprites/spr.png',
        options: { width: 16, height: 16, cellWidth: 16, cellHeight: 16, tileBase: 384 },
        data: {
          generated: {
            paletteFile: 'assets/generated/spr/palette.bin',
            tilesFile: 'assets/generated/spr/patterns.bin',
            tileCount: 1,
            paletteCount: 1,
            vramBytes: 128,
          },
        },
      },
    ],
  });

  const result = assetManager.generateAssetSources(projectDir);
  const header = fs.readFileSync(result.headerPath, 'utf-8');
  const source = fs.readFileSync(result.sourcePath, 'utf-8');

  assert.equal(result.bgCount, 1);
  assert.equal(result.spriteCount, 1);
  assert.match(header, /pce_editor_bg_asset_t/);
  assert.match(header, /pce_editor_sprite_asset_t/);
  assert.match(source, /static const unsigned char pce_editor_image_bg_palette\[\]/);
  assert.match(source, /static const unsigned char pce_editor_sprite_spr_patterns\[\]/);
  assert.match(source, /const unsigned char pce_editor_bg_asset_count = 1/);
  assert.match(source, /const unsigned char pce_editor_sprite_asset_count = 1/);
  assert.match(source, /pce_editor_image_rows/);
});
