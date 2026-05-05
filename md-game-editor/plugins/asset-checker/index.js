'use strict';

const fs = require('fs');
const path = require('path');
const manifest = require('./manifest.json');

const TARGET_TYPES = new Set(['IMAGE', 'SPRITE', 'TILEMAP', 'TILESET', 'PALETTE', 'XGM', 'XGM2', 'WAV']);

function readTemplateSource() {
  return fs.readFileSync(path.join(__dirname, 'template', 'src', 'main.c'), 'utf-8');
}

function renderTemplate(template, values) {
  return template.replace(/\{\{([A-Z0-9_]+)\}\}/g, (_match, key) => String(values[key] ?? ''));
}

function normalizeType(asset) {
  return String(asset?.type || '').toUpperCase();
}

function sortByName(a, b) {
  return String(a.name || '').localeCompare(String(b.name || ''), undefined, { numeric: true });
}

function isIdentifier(value) {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(String(value || ''));
}

function escapeCString(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\r?\n/g, ' ');
}

function isBgmWav(asset) {
  const name = String(asset?.name || '').toLowerCase();
  const sourcePath = String(asset?.sourcePath || '').replace(/\\/g, '/').toLowerCase();
  return sourcePath.startsWith('bgm/') || /^bgm(?:_|$|-)/.test(name) || name.includes('_bgm');
}

function isHalfRateWav(asset) {
  const outRate = String(asset?.outRate || '').trim();
  return outRate === '6650';
}

function pathStem(value) {
  return path.basename(String(value || '').replace(/\\/g, '/')).replace(/\.[^.]*$/, '').toLowerCase();
}

function collectAssets(assets = []) {
  const normalized = (Array.isArray(assets) ? assets : [])
    .map((asset) => ({ ...asset, type: normalizeType(asset), name: String(asset?.name || '').trim() }))
    .filter((asset) => TARGET_TYPES.has(asset.type) && isIdentifier(asset.name));

  const images = normalized.filter((asset) => asset.type === 'IMAGE').sort(sortByName);
  const sprites = normalized.filter((asset) => asset.type === 'SPRITE').sort(sortByName);
  const tilemaps = normalized.filter((asset) => asset.type === 'TILEMAP').sort(sortByName);
  const tilesets = normalized.filter((asset) => asset.type === 'TILESET').sort(sortByName);
  const palettes = normalized.filter((asset) => asset.type === 'PALETTE').sort(sortByName);
  const bgms = normalized
    .filter((asset) => asset.type === 'XGM' || asset.type === 'XGM2' || (asset.type === 'WAV' && isBgmWav(asset)))
    .sort(sortByName);

  return { images, sprites, tilemaps, tilesets, palettes, bgms };
}

function arrayOrNone(entries, renderer, noneValue) {
  if (!entries.length) return `    ${noneValue}`;
  return entries.map(renderer).join(',\n');
}

function renderImageEntries(images) {
  return arrayOrNone(
    images,
    (asset) => `    { "${escapeCString(asset.name)}", &${asset.name} }`,
    '{ "none", NULL }',
  );
}

function renderSpriteEntries(sprites) {
  return arrayOrNone(
    sprites,
    (asset) => `    { "${escapeCString(asset.name)}", &${asset.name} }`,
    '{ "none", NULL }',
  );
}

function findTilesetForTilemap(tilemap, tilesets) {
  if (!tilesets.length) return null;
  const explicit = tilesets.find((entry) => entry.name === tilemap.tileset);
  if (explicit) return explicit;
  const tilemapStem = pathStem(tilemap.sourcePath);
  const byStem = tilesets.find((entry) => pathStem(entry.sourcePath) === tilemapStem || pathStem(entry.name) === tilemapStem);
  if (byStem) return byStem;
  return tilesets.length === 1 ? tilesets[0] : null;
}

function findPaletteForTileset(tileset, palettes) {
  if (!tileset || !palettes.length) return null;
  const bySource = palettes.find((entry) => String(entry.sourcePath || '') === String(tileset.sourcePath || ''));
  if (bySource) return bySource;
  const byName = palettes.find((entry) => entry.name === `${tileset.name}_palette` || entry.name === `${tileset.name}Palette`);
  if (byName) return byName;
  return palettes.length === 1 ? palettes[0] : null;
}

function renderTilemapEntries(tilemaps, tilesets, palettes) {
  return arrayOrNone(
    tilemaps,
    (asset) => {
      const tileset = findTilesetForTilemap(asset, tilesets);
      const palette = findPaletteForTileset(tileset, palettes);
      const tilesetPointer = tileset ? `&${tileset.name}` : 'NULL';
      const palettePointer = palette ? `&${palette.name}` : 'NULL';
      const note = tileset ? asset.name : `${asset.name} (no tileset)`;
      return `    { "${escapeCString(note)}", &${asset.name}, ${tilesetPointer}, ${palettePointer} }`;
    },
    '{ "none", NULL, NULL, NULL }',
  );
}

function renderBgmEntries(bgms) {
  return arrayOrNone(
    bgms,
    (asset) => {
      const kind = asset.type === 'WAV' ? 'BGM_KIND_WAV' : asset.type === 'XGM' ? 'BGM_KIND_XGM' : 'BGM_KIND_XGM2';
      const halfRate = asset.type === 'WAV' && isHalfRateWav(asset) ? 'TRUE' : 'FALSE';
      return `    { "${escapeCString(`${asset.name} (${asset.type})`)}", ${kind}, ${asset.name}, sizeof(${asset.name}), ${halfRate} }`;
    },
    '{ "none", BGM_KIND_XGM2, NULL, 0, FALSE }',
  );
}

function generateSource(assets = []) {
  const grouped = collectAssets(assets);
  const total = grouped.images.length + grouped.sprites.length + grouped.tilemaps.length + grouped.bgms.length;
  if (total === 0) {
    return {
      ok: false,
      error: 'IMAGE / SPRITE / TILEMAP / XGM / XGM2 / BGM 用 WAV アセットが見つかりません。',
    };
  }

  const sourceCode = renderTemplate(readTemplateSource(), {
    VERSION: manifest.version,
    IMAGE_COUNT: grouped.images.length,
    SPRITE_COUNT: grouped.sprites.length,
    TILEMAP_COUNT: grouped.tilemaps.length,
    BGM_COUNT: grouped.bgms.length,
    IMAGE_ENTRIES: renderImageEntries(grouped.images),
    SPRITE_ENTRIES: renderSpriteEntries(grouped.sprites),
    TILEMAP_ENTRIES: renderTilemapEntries(grouped.tilemaps, grouped.tilesets, grouped.palettes),
    BGM_ENTRIES: renderBgmEntries(grouped.bgms),
  });

  return { ok: true, sourceCode };
}

function onBuildStart(payload = {}, context = {}) {
  context?.logger?.info?.(`asset-checker build start: project=${payload?.projectDir || '-'}`);
  return {
    ok: true,
    makeVariables: {
      SRC_C: 'src/main.c',
    },
  };
}

function onBuildLog() {
  return { ok: true };
}

function onBuildEnd(payload, context = {}) {
  context?.logger?.info?.(`asset-checker build end: success=${Boolean(payload?.success)}`);
  return { ok: true };
}

function onBuildError(payload, context = {}) {
  context?.logger?.error?.(`asset-checker build error: ${payload?.error || 'unknown'}`);
  return { ok: true };
}

module.exports = {
  manifest,
  collectAssets,
  generateSource,
  readTemplateSource,
  onBuildStart,
  onBuildLog,
  onBuildEnd,
  onBuildError,
};
