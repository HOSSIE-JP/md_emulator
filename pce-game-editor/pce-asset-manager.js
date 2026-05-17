'use strict';

const fs = require('fs');
const path = require('path');
const { normalizeRelativePath, resolveUnderRoot } = require('./pce-file-safety');

const ASSET_FILE = path.join('assets', 'pce-assets.json');
const SUPPORTED_TYPES = new Set(['image', 'psg-sequence', 'tileset', 'tilemap', 'palette']);

function ensureDirSync(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function getAssetFilePath(projectDir) {
  return path.join(path.resolve(projectDir), ASSET_FILE);
}

function defaultAssets() {
  return {
    version: 1,
    assets: [],
  };
}

function normalizeAsset(asset = {}) {
  const id = String(asset.id || asset.name || '').trim();
  const type = String(asset.type || '').trim().toLowerCase();
  if (!id) throw new Error('asset id is required');
  if (!SUPPORTED_TYPES.has(type)) throw new Error(`unsupported asset type: ${type}`);
  const normalized = {
    id,
    type,
    name: String(asset.name || id).trim(),
    source: normalizeRelativePath(asset.source || ''),
    options: asset.options && typeof asset.options === 'object' ? { ...asset.options } : {},
  };
  if (asset.data && typeof asset.data === 'object') normalized.data = { ...asset.data };
  return normalized;
}

function normalizeAssetDocument(doc = {}) {
  const assets = Array.isArray(doc.assets) ? doc.assets : [];
  return {
    version: Number(doc.version) || 1,
    assets: assets.map(normalizeAsset),
  };
}

function ensureAssetFile(projectDir) {
  const filePath = getAssetFilePath(projectDir);
  if (!fs.existsSync(filePath)) {
    ensureDirSync(path.dirname(filePath));
    fs.writeFileSync(filePath, JSON.stringify(defaultAssets(), null, 2), 'utf-8');
  }
  return filePath;
}

function readAssetDocument(projectDir) {
  const filePath = ensureAssetFile(projectDir);
  try {
    return normalizeAssetDocument(JSON.parse(fs.readFileSync(filePath, 'utf-8')));
  } catch (err) {
    throw new Error(`asset file parse failed: ${err.message || err}`);
  }
}

function writeAssetDocument(projectDir, doc) {
  const normalized = normalizeAssetDocument(doc);
  const filePath = getAssetFilePath(projectDir);
  ensureDirSync(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(normalized, null, 2), 'utf-8');
  return normalized;
}

function resolveAssetSource(projectDir, asset) {
  const normalized = normalizeAsset(asset);
  if (!normalized.source) return { asset: normalized, absPath: null };
  const { absPath } = resolveUnderRoot(projectDir, normalized.source, 'project');
  return { asset: normalized, absPath };
}

function listAssets(projectDir) {
  const doc = readAssetDocument(projectDir);
  return {
    file: ASSET_FILE,
    assets: doc.assets.map((asset) => ({
      ...asset,
      exists: asset.source ? fs.existsSync(path.join(projectDir, asset.source)) : true,
    })),
  };
}

function upsertAsset(projectDir, nextAsset) {
  const doc = readAssetDocument(projectDir);
  const asset = normalizeAsset(nextAsset);
  const index = doc.assets.findIndex((entry) => entry.id === asset.id);
  if (index >= 0) {
    doc.assets[index] = asset;
  } else {
    doc.assets.push(asset);
  }
  return writeAssetDocument(projectDir, doc);
}

function deleteAsset(projectDir, id) {
  const doc = readAssetDocument(projectDir);
  const assetId = String(id || '').trim();
  const nextAssets = doc.assets.filter((asset) => asset.id !== assetId);
  if (nextAssets.length === doc.assets.length) {
    throw new Error(`asset not found: ${assetId}`);
  }
  return writeAssetDocument(projectDir, { ...doc, assets: nextAssets });
}

function readPceImageJson(absPath) {
  const parsed = JSON.parse(fs.readFileSync(absPath, 'utf-8'));
  const width = Math.max(1, Math.min(64, Number(parsed.width) || 16));
  const height = Math.max(1, Math.min(64, Number(parsed.height) || 16));
  const pixels = Array.isArray(parsed.pixels) ? parsed.pixels : [];
  const rows = [];
  for (let y = 0; y < height; y += 1) {
    const row = Array.isArray(pixels[y]) ? pixels[y] : [];
    rows.push(Array.from({ length: width }, (_unused, x) => Number(row[x]) & 0x0f));
  }
  return {
    width,
    height,
    pixels: rows,
    palette: Array.isArray(parsed.palette) ? parsed.palette.slice(0, 16) : [],
  };
}

function generateTextMosaicForImage(projectDir, asset) {
  const { absPath } = resolveAssetSource(projectDir, asset);
  if (!absPath || !fs.existsSync(absPath)) {
    return ['IMAGE FILE MISSING'];
  }
  const ext = path.extname(absPath).toLowerCase();
  if (ext === '.json' || ext === '.pceimg') {
    const image = readPceImageJson(absPath);
    return image.pixels.map((row) => row.map((value) => (value ? '#' : '.')).join(''));
  }
  return [`PNG:${path.basename(absPath)}`, 'Use SuperFamiconv setup', 'for hardware tiles.'];
}

function generateAssetSources(projectDir) {
  const doc = readAssetDocument(projectDir);
  const linesH = [
    '#ifndef PCE_EDITOR_GENERATED_ASSETS_H',
    '#define PCE_EDITOR_GENERATED_ASSETS_H',
    '',
    'extern const char * const pce_editor_image_rows[];',
    'extern const unsigned char pce_editor_image_row_count;',
    'extern const unsigned int pce_editor_tone_period;',
    '',
    '#endif',
    '',
  ];

  const image = doc.assets.find((asset) => asset.type === 'image');
  const sound = doc.assets.find((asset) => asset.type === 'psg-sequence');
  const rows = image ? generateTextMosaicForImage(projectDir, image).slice(0, 14) : ['NO IMAGE ASSET'];
  const tonePeriod = Number(sound?.options?.period || 512);

  const quotedRows = rows.map((row) => `  "${String(row).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`);
  const linesC = [
    '#include "assets.h"',
    '',
    'const char * const pce_editor_image_rows[] = {',
    `${quotedRows.join(',\n')}`,
    '};',
    `const unsigned char pce_editor_image_row_count = ${rows.length};`,
    `const unsigned int pce_editor_tone_period = ${Math.max(1, Math.min(4095, tonePeriod))};`,
    'unsigned char pce_editor_cc65_bss_anchor;',
    '',
  ];

  const generatedDir = path.join(projectDir, 'src', 'generated');
  ensureDirSync(generatedDir);
  const headerPath = path.join(generatedDir, 'assets.h');
  const sourcePath = path.join(generatedDir, 'assets.c');
  fs.writeFileSync(headerPath, linesH.join('\n'), 'utf-8');
  fs.writeFileSync(sourcePath, linesC.join('\n'), 'utf-8');
  return { headerPath, sourcePath, assetCount: doc.assets.length, imageRows: rows.length };
}

module.exports = {
  ASSET_FILE,
  SUPPORTED_TYPES,
  defaultAssets,
  deleteAsset,
  ensureAssetFile,
  generateAssetSources,
  getAssetFilePath,
  listAssets,
  normalizeAsset,
  normalizeAssetDocument,
  readAssetDocument,
  readPceImageJson,
  resolveAssetSource,
  upsertAsset,
  writeAssetDocument,
};
