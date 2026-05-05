'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');

async function importTilemapCore() {
  return import(pathToFileURL(path.join(__dirname, '..', 'plugins', 'tilemap-editor', 'tilemap-core.mjs')).href);
}

test('tilemap-editor writes Tiled-compatible TMX and TSX subset', async () => {
  const core = await importTilemapCore();
  const map = core.createBlankTilemap({
    name: 'stage_1',
    tilesetName: 'stage_tiles',
    width: 4,
    height: 3,
    tileWidth: 8,
    tileHeight: 8,
    layerName: 'Ground',
  });
  map.tilesetImage = 'stage_tiles.png';
  map.tilesetImageWidth = 32;
  map.tilesetImageHeight = 16;
  map.tilesetColumns = 4;
  map.tilesetTileCount = 8;
  map.layers[0].data = [
    1, 2, 0, 0,
    3, 4, 0, 0,
    0, 0, 5, 6,
  ];
  map.layers.push({
    name: 'Ground priority',
    visible: true,
    opacity: 1,
    priority: true,
    data: [
      0, 0, 0, 0,
      1, 1, 0, 0,
      0, 0, 1, 1,
    ],
  });

  const tmx = core.buildTmx(map);
  const tsx = core.buildTsx(map);

  assert.match(tmx, /<map[^>]+orientation="orthogonal"[^>]+width="4"[^>]+height="3"[^>]+infinite="0"/);
  assert.match(tmx, /<tileset firstgid="1" source="\.\.\/tilesets\/stage_tiles\.tsx"\/>/);
  assert.match(tmx, /<layer id="1" name="Ground" width="4" height="3">/);
  assert.match(tmx, /<data encoding="csv">/);
  assert.match(tmx, /<layer id="2" name="Ground priority"/);
  assert.match(tsx, /<tileset[^>]+name="stage_tiles"[^>]+tilewidth="8"[^>]+tileheight="8"[^>]+tilecount="8"[^>]+columns="4"/);
  assert.match(tsx, /<image source="stage_tiles\.png" width="32" height="16"\/>/);
});

test('tilemap-editor parses its generated TMX and TSX subset', async () => {
  const core = await importTilemapCore();
  const map = core.createBlankTilemap({ name: 'stage_2', tilesetName: 'stage_tiles', width: 2, height: 2 });
  map.layers[0].name = 'Main';
  map.layers[0].data = [1, 0, 2, 3];

  const parsed = core.parseTmx(core.buildTmx(map));
  const tsx = core.parseTsx(core.buildTsx({
    ...map,
    tilesetImage: 'stage_tiles.png',
    tilesetColumns: 2,
    tilesetTileCount: 4,
    tilesetImageWidth: 16,
    tilesetImageHeight: 16,
  }));

  assert.equal(parsed.width, 2);
  assert.equal(parsed.height, 2);
  assert.equal(parsed.tileWidth, 8);
  assert.equal(parsed.tilesetSource, '../tilesets/stage_tiles.tsx');
  assert.equal(parsed.layers[0].name, 'Main');
  assert.deepEqual(parsed.layers[0].data, [1, 0, 2, 3]);
  assert.equal(tsx.tilesetName, 'stage_tiles');
  assert.equal(tsx.tilesetImage, 'stage_tiles.png');
  assert.equal(tsx.tilesetColumns, 2);
});

test('tilemap-editor manifest and renderer register runtime capability without page-root display override', () => {
  const pluginDir = path.join(__dirname, '..', 'plugins', 'tilemap-editor');
  const manifest = JSON.parse(fs.readFileSync(path.join(pluginDir, 'manifest.json'), 'utf-8'));
  const rendererSource = fs.readFileSync(path.join(pluginDir, 'renderer.js'), 'utf-8');
  const styleSource = fs.readFileSync(path.join(pluginDir, 'style.css'), 'utf-8');

  assert.deepEqual(manifest.types, ['editor', 'asset']);
  assert.equal(manifest.renderer.entry, 'renderer.js');
  assert.ok(manifest.renderer.capabilities.includes('tilemap-editor'));
  assert.match(rendererSource, /registerCapability\(['"]tilemap-editor['"]/);
  assert.match(rendererSource, /buildTmx/);
  assert.match(rendererSource, /buildTsx/);
  assert.doesNotMatch(styleSource, /\.tilemap-editor-page\s*\{[^}]*display\s*:/);
});
