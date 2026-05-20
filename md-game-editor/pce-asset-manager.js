'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const setupManager = require('./pce-setup-manager');
const { normalizeRelativePath, resolveUnderRoot } = require('./pce-file-safety');

const ASSET_FILE = path.join('assets', 'pce-assets.json');
const SUPPORTED_TYPES = new Set(['image', 'sprite', 'psg-sequence', 'tileset', 'tilemap', 'palette']);
const IMAGE_EXTENSIONS = new Set(['.png', '.bmp']);
const SPRITE_CELL_SIZES = new Set(['16x16', '16x32', '16x64', '32x16', '32x32', '32x64']);
const DEFAULT_BG_OPTIONS = Object.freeze({
  kind: 'background',
  paletteBank: 0,
  tileBase: 32,
  mapBase: 0,
  x: 0,
  y: 0,
  width: 0,
  height: 0,
  cellWidth: 8,
  cellHeight: 8,
  transparentIndex: 0,
});
const DEFAULT_SPRITE_OPTIONS = Object.freeze({
  kind: 'sprite',
  paletteBank: 0,
  tileBase: 384,
  mapBase: 0,
  x: 144,
  y: 104,
  width: 0,
  height: 0,
  cellWidth: 16,
  cellHeight: 16,
  transparentIndex: 0,
});

function ensureDirSync(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function isLikelyAbsolutePath(value = '') {
  const raw = String(value || '');
  return path.isAbsolute(raw) || /^[a-zA-Z]:[\\/]/.test(raw) || /^\\\\/.test(raw);
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

function clampInt(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(parsed)));
}

function sanitizeAssetId(value, fallback = 'asset') {
  const base = String(value || fallback)
    .replace(/\.[^.]+$/, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48);
  return base || fallback;
}

function normalizeAssetSource(source = '') {
  const raw = String(source || '').trim();
  if (!raw) return '';
  if (isLikelyAbsolutePath(raw)) {
    throw new Error(`project relative asset path is required: ${raw}`);
  }
  const cleaned = normalizeRelativePath(raw);
  if (cleaned.split('/').includes('..')) {
    throw new Error(`project relative asset path is required: ${raw}`);
  }
  return cleaned;
}

function normalizeImageOptions(asset = {}) {
  const rawOptions = asset.options && typeof asset.options === 'object' ? { ...asset.options } : {};
  const isSprite = asset.type === 'sprite' || rawOptions.kind === 'sprite';
  const defaults = isSprite ? DEFAULT_SPRITE_OPTIONS : DEFAULT_BG_OPTIONS;
  const options = { ...defaults, ...rawOptions };
  options.kind = isSprite ? 'sprite' : 'background';
  options.paletteBank = clampInt(options.paletteBank, 0, 15, defaults.paletteBank);
  options.tileBase = clampInt(options.tileBase, 0, 2047, defaults.tileBase);
  options.mapBase = clampInt(options.mapBase, 0, 2047, defaults.mapBase);
  options.x = clampInt(options.x, 0, 255, defaults.x);
  options.y = clampInt(options.y, 0, 255, defaults.y);
  options.width = clampInt(options.width, 0, 1024, defaults.width);
  options.height = clampInt(options.height, 0, 1024, defaults.height);
  options.transparentIndex = clampInt(options.transparentIndex, 0, 15, defaults.transparentIndex);
  if (isSprite) {
    let cellWidth = clampInt(options.cellWidth, 16, 32, defaults.cellWidth);
    let cellHeight = clampInt(options.cellHeight, 16, 64, defaults.cellHeight);
    const key = `${cellWidth}x${cellHeight}`;
    if (!SPRITE_CELL_SIZES.has(key)) {
      cellWidth = defaults.cellWidth;
      cellHeight = defaults.cellHeight;
    }
    options.cellWidth = cellWidth;
    options.cellHeight = cellHeight;
  } else {
    options.cellWidth = 8;
    options.cellHeight = 8;
  }
  return options;
}

function normalizeGeneratedData(data = {}) {
  if (!data || typeof data !== 'object') return {};
  const generated = data.generated && typeof data.generated === 'object'
    ? {
        ...data.generated,
        paletteFile: normalizeAssetSource(data.generated.paletteFile || ''),
        tilesFile: normalizeAssetSource(data.generated.tilesFile || ''),
        mapFile: normalizeAssetSource(data.generated.mapFile || ''),
        previewFile: normalizeAssetSource(data.generated.previewFile || ''),
        tileCount: clampInt(data.generated.tileCount, 0, 65535, 0),
        paletteCount: clampInt(data.generated.paletteCount, 0, 32, 0),
        vramBytes: clampInt(data.generated.vramBytes, 0, 65535, 0),
        warnings: Array.isArray(data.generated.warnings)
          ? data.generated.warnings.map((warning) => String(warning)).filter(Boolean)
          : [],
        paletteColors: Array.isArray(data.generated.paletteColors)
          ? data.generated.paletteColors.map((color) => String(color)).filter(Boolean).slice(0, 256)
          : [],
      }
    : null;
  return generated ? { ...data, generated } : { ...data };
}

function normalizeAsset(asset = {}) {
  const id = sanitizeAssetId(asset.id || asset.name || '');
  const type = String(asset.type || '').trim().toLowerCase();
  if (!id) throw new Error('asset id is required');
  if (!SUPPORTED_TYPES.has(type)) throw new Error(`unsupported asset type: ${type}`);
  const normalized = {
    id,
    type,
    name: String(asset.name || id).trim(),
    source: normalizeAssetSource(asset.source || ''),
    options: asset.options && typeof asset.options === 'object' ? { ...asset.options } : {},
  };
  if (type === 'image' || type === 'sprite') {
    normalized.options = normalizeImageOptions({ ...normalized, type });
  }
  if (asset.data && typeof asset.data === 'object') normalized.data = normalizeGeneratedData(asset.data);
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

function getMimeForPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.png') return 'image/png';
  if (ext === '.bmp') return 'image/bmp';
  if (ext === '.json') return 'application/json';
  if (ext === '.bin') return 'application/octet-stream';
  return 'application/octet-stream';
}

function listAssets(projectDir) {
  const doc = readAssetDocument(projectDir);
  return {
    file: ASSET_FILE,
    assets: doc.assets.map((asset) => {
      let exists = true;
      let pathError = '';
      if (asset.source) {
        try {
          const { absPath } = resolveUnderRoot(projectDir, asset.source, 'project');
          exists = fs.existsSync(absPath);
        } catch (err) {
          exists = false;
          pathError = err.message || String(err);
        }
      }
      return {
        ...asset,
        exists,
        pathError,
      };
    }),
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

function reorderAssets(projectDir, ids = []) {
  const doc = readAssetDocument(projectDir);
  const order = Array.isArray(ids) ? ids.map((id) => String(id)).filter(Boolean) : [];
  const byId = new Map(doc.assets.map((asset) => [asset.id, asset]));
  const nextAssets = [];
  for (const id of order) {
    if (byId.has(id)) {
      nextAssets.push(byId.get(id));
      byId.delete(id);
    }
  }
  nextAssets.push(...doc.assets.filter((asset) => byId.has(asset.id)));
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

function parsePngSize(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 24) return null;
  if (buffer.readUInt32BE(0) !== 0x89504e47 || buffer.readUInt32BE(4) !== 0x0d0a1a0a) return null;
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function parseBmpSize(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 26) return null;
  if (buffer.toString('ascii', 0, 2) !== 'BM') return null;
  const width = buffer.readInt32LE(18);
  const height = Math.abs(buffer.readInt32LE(22));
  return width > 0 && height > 0 ? { width, height } : null;
}

function readImageSize(absPath) {
  const buffer = fs.readFileSync(absPath);
  return parsePngSize(buffer) || parseBmpSize(buffer) || { width: 0, height: 0 };
}

function decodeDataUrl(dataUrl = '') {
  const match = String(dataUrl || '').match(/^data:([^;,]+)?(;base64)?,(.*)$/);
  if (!match) throw new Error('invalid image data URL');
  const mime = match[1] || 'application/octet-stream';
  const payload = match[3] || '';
  const buffer = match[2] ? Buffer.from(payload, 'base64') : Buffer.from(decodeURIComponent(payload), 'utf-8');
  return { mime, buffer };
}

function sourcePathForImport(payload = {}) {
  const raw = String(payload.sourcePath || '').trim();
  if (!raw) return null;
  if (isLikelyAbsolutePath(raw)) {
    if (!fs.existsSync(raw)) throw new Error(`source file not found: ${raw}`);
    return path.resolve(raw);
  }
  throw new Error('import source must be selected with an absolute file path');
}

function buildImageWarnings(asset, imageSize, generated = {}) {
  const options = normalizeImageOptions(asset);
  const warnings = [];
  const width = options.width || imageSize.width || 0;
  const height = options.height || imageSize.height || 0;
  if (options.kind === 'sprite') {
    const cellKey = `${options.cellWidth}x${options.cellHeight}`;
    if (!SPRITE_CELL_SIZES.has(cellKey)) {
      warnings.push(`PCE sprite cell size must be one of ${Array.from(SPRITE_CELL_SIZES).join(', ')}`);
    }
    if (width && width % 16 !== 0) warnings.push('Sprite sheet width is not aligned to 16px patterns');
    if (height && height % 16 !== 0) warnings.push('Sprite sheet height is not aligned to 16px patterns');
    const frameCount = width && height
      ? Math.max(1, Math.floor(width / options.cellWidth) * Math.floor(height / options.cellHeight))
      : 1;
    if (frameCount > 64) warnings.push('Sprite sheet contains more than 64 cells; PCE SATB displays up to 64 sprites');
    if (Math.floor(width / options.cellWidth) > 16) warnings.push('Many cells share the same scanline; hardware limit is 16 sprites per scanline');
  } else {
    if (width && width % 8 !== 0) warnings.push('BG image width is not aligned to 8px tiles');
    if (height && height % 8 !== 0) warnings.push('BG image height is not aligned to 8px tiles');
    if (width > 256 || height > 224) warnings.push('BG image exceeds the v1 recommended 256x224 viewport');
    const tileCount = generated.tileCount || 0;
    if (tileCount && options.tileBase < 256 && options.tileBase + tileCount > 256) {
      warnings.push('BG tiles overlap the sample text font VRAM area at tile 256');
    }
  }
  const paletteCount = generated.paletteCount || 0;
  if (paletteCount > 16) warnings.push('PCE image assets can use at most 16 palettes in v1');
  return warnings;
}

function vceWordToHex(word) {
  const r = word & 0x07;
  const g = (word >> 3) & 0x07;
  const b = (word >> 6) & 0x07;
  const to8 = (v) => Math.round((v / 7) * 255).toString(16).padStart(2, '0');
  return `#${to8(r)}${to8(g)}${to8(b)}`;
}

function readPaletteColors(buffer) {
  if (!Buffer.isBuffer(buffer)) return [];
  const colors = [];
  for (let offset = 0; offset + 1 < buffer.length && colors.length < 256; offset += 2) {
    colors.push(vceWordToHex(buffer.readUInt16LE(offset)));
  }
  return colors;
}

function relativeGeneratedPath(assetId, fileName) {
  return normalizeRelativePath(path.join('assets', 'generated', assetId, fileName));
}

function buildSuperFamiconvPlan(projectDir, asset, sourceAbs, options = {}) {
  const normalized = normalizeAsset(asset);
  const kind = normalized.type === 'sprite' ? 'sprite' : 'background';
  const generatedDir = path.join(projectDir, 'assets', 'generated', normalized.id);
  const paletteFile = relativeGeneratedPath(normalized.id, 'palette.bin');
  const tilesFile = relativeGeneratedPath(normalized.id, kind === 'sprite' ? 'patterns.bin' : 'tiles.bin');
  const mapFile = kind === 'sprite' ? '' : relativeGeneratedPath(normalized.id, 'map.bin');
  const previewFile = relativeGeneratedPath(normalized.id, 'preview.json');
  const paletteAbs = path.join(projectDir, paletteFile);
  const tilesAbs = path.join(projectDir, tilesFile);
  const mapAbs = mapFile ? path.join(projectDir, mapFile) : '';
  const toolPath = options.superfamiconvPath || setupManager.getSuperFamiconvPath();
  const command = toolPath || 'superfamiconv';
  const args = [
    '--in-image', sourceAbs,
    '--out-palette', paletteAbs,
    '--out-tiles', tilesAbs,
    '-M', kind === 'sprite' ? 'pce_sprite' : 'pce',
    '-B', '4',
    '-W', String(kind === 'sprite' ? 16 : 8),
    '-H', String(kind === 'sprite' ? 16 : 8),
  ];
  if (kind === 'background') {
    args.splice(4, 0, '--out-map', mapAbs);
    args.push('-T', String(normalized.options.tileBase || 0));
    args.push('-P', String(normalized.options.paletteBank || 0));
  } else {
    args.push('-S');
  }
  args.push('-v');
  return {
    kind,
    command,
    args,
    cwd: projectDir,
    files: { paletteFile, tilesFile, mapFile, previewFile },
    absFiles: { paletteAbs, tilesAbs, mapAbs, previewAbs: path.join(projectDir, previewFile) },
    generatedDir,
  };
}

function runSuperFamiconv(plan, options = {}) {
  if (!options.dryRun && (!plan.command || plan.command === 'superfamiconv') && !setupManager.getSuperFamiconvPath()) {
    throw new Error('SuperFamiconv が未設定です。Setup で SuperFamiconv をダウンロードしてください。');
  }
  ensureDirSync(plan.generatedDir);
  if (options.dryRun) {
    return { ok: true, command: plan.command, args: plan.args, dryRun: true };
  }
  const proc = spawnSync(plan.command, plan.args, {
    cwd: plan.cwd,
    encoding: 'utf-8',
    windowsHide: true,
  });
  if (proc.error) throw proc.error;
  if (proc.status !== 0) {
    const detail = [proc.stderr, proc.stdout].filter(Boolean).join('\n').trim();
    throw new Error(`SuperFamiconv failed (${proc.status}): ${detail || 'no output'}`);
  }
  const required = [plan.absFiles.paletteAbs, plan.absFiles.tilesAbs];
  if (plan.kind === 'background') required.push(plan.absFiles.mapAbs);
  for (const filePath of required) {
    if (!filePath || !fs.existsSync(filePath)) {
      throw new Error(`SuperFamiconv output missing: ${filePath}`);
    }
  }
  return {
    ok: true,
    command: plan.command,
    args: plan.args,
    stdout: proc.stdout || '',
    stderr: proc.stderr || '',
  };
}

function extractConversionWarnings(result = {}) {
  const lines = [result.stderr, result.stdout]
    .filter(Boolean)
    .join('\n')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.filter((line) => /warning|too many/i.test(line));
}

function uniqueWarnings(warnings = []) {
  return Array.from(new Set(warnings.map((warning) => String(warning || '').trim()).filter(Boolean)));
}

function createGeneratedMetadata(projectDir, asset, plan, sourceRel, imageSize, extraWarnings = []) {
  const palette = fs.existsSync(plan.absFiles.paletteAbs) ? fs.readFileSync(plan.absFiles.paletteAbs) : Buffer.alloc(0);
  const tiles = fs.existsSync(plan.absFiles.tilesAbs) ? fs.readFileSync(plan.absFiles.tilesAbs) : Buffer.alloc(0);
  const map = plan.absFiles.mapAbs && fs.existsSync(plan.absFiles.mapAbs) ? fs.readFileSync(plan.absFiles.mapAbs) : Buffer.alloc(0);
  const isSprite = asset.type === 'sprite';
  const generated = {
    ...plan.files,
    tileCount: isSprite ? Math.floor(tiles.length / 128) : Math.floor(tiles.length / 32),
    paletteCount: Math.ceil(palette.length / 32),
    vramBytes: tiles.length + map.length,
    warnings: [],
    paletteColors: readPaletteColors(palette),
  };
  generated.warnings = uniqueWarnings([...extraWarnings, ...buildImageWarnings(asset, imageSize, generated)]);
  const preview = {
    source: sourceRel,
    kind: isSprite ? 'sprite' : 'background',
    width: imageSize.width || 0,
    height: imageSize.height || 0,
    tileCount: generated.tileCount,
    paletteCount: generated.paletteCount,
    vramBytes: generated.vramBytes,
    warnings: generated.warnings,
  };
  ensureDirSync(path.dirname(plan.absFiles.previewAbs));
  fs.writeFileSync(plan.absFiles.previewAbs, JSON.stringify(preview, null, 2), 'utf-8');
  return { ...generated, previewFile: plan.files.previewFile };
}

function importImage(projectDir, payload = {}, options = {}) {
  const kind = payload.kind === 'sprite' || payload.type === 'sprite' ? 'sprite' : 'background';
  const sourceAbs = sourcePathForImport(payload);
  const sourceName = String(payload.sourceFileName || (sourceAbs ? path.basename(sourceAbs) : 'asset.png'));
  const sourceExt = path.extname(sourceName || sourceAbs || '').toLowerCase();
  if (!IMAGE_EXTENSIONS.has(sourceExt)) {
    throw new Error('PNG/BMP image files are supported');
  }
  if (sourceExt === '.bmp' && !payload.convertedDataUrl) {
    throw new Error('BMP import requires renderer-side PNG conversion before SuperFamiconv');
  }
  const id = sanitizeAssetId(payload.id || sourceName, kind === 'sprite' ? 'sprite_asset' : 'bg_asset');
  const assetType = kind === 'sprite' ? 'sprite' : 'image';
  const sourceSubdir = kind === 'sprite' ? 'assets/sprites' : 'assets/images';
  const storedExt = payload.convertedDataUrl ? '.png' : sourceExt;
  const sourceRel = normalizeRelativePath(path.join(sourceSubdir, `${id}${storedExt}`));
  const { absPath: destAbs } = resolveUnderRoot(projectDir, sourceRel, 'project');
  const toolPath = options.superfamiconvPath || setupManager.getSuperFamiconvPath();
  if (!options.dryRun && !toolPath) {
    throw new Error('SuperFamiconv が未設定です。Setup で SuperFamiconv をダウンロードしてください。');
  }
  ensureDirSync(path.dirname(destAbs));
  if (payload.convertedDataUrl) {
    const decoded = decodeDataUrl(payload.convertedDataUrl);
    if (decoded.mime && decoded.mime !== 'image/png') {
      throw new Error('converted image must be PNG');
    }
    fs.writeFileSync(destAbs, decoded.buffer);
  } else if (sourceAbs) {
    fs.copyFileSync(sourceAbs, destAbs);
  }
  const imageSize = readImageSize(destAbs);
  const baseAsset = normalizeAsset({
    id,
    type: assetType,
    name: String(payload.name || sourceName.replace(/\.[^.]+$/, '') || id).trim(),
    source: sourceRel,
    options: {
      ...payload.options,
      kind,
      paletteBank: payload.paletteBank ?? payload.options?.paletteBank,
      tileBase: payload.tileBase ?? payload.options?.tileBase,
      mapBase: payload.mapBase ?? payload.options?.mapBase,
      x: payload.x ?? payload.options?.x,
      y: payload.y ?? payload.options?.y,
      width: payload.width ?? payload.options?.width ?? imageSize.width,
      height: payload.height ?? payload.options?.height ?? imageSize.height,
      cellWidth: payload.cellWidth ?? payload.options?.cellWidth,
      cellHeight: payload.cellHeight ?? payload.options?.cellHeight,
      transparentIndex: payload.transparentIndex ?? payload.options?.transparentIndex,
    },
  });
  const plan = buildSuperFamiconvPlan(projectDir, baseAsset, destAbs, { superfamiconvPath: toolPath || options.superfamiconvPath });
  const commandResult = runSuperFamiconv(plan, options);
  const generated = createGeneratedMetadata(projectDir, baseAsset, plan, sourceRel, imageSize, extractConversionWarnings(commandResult));
  const asset = normalizeAsset({
    ...baseAsset,
    data: {
      ...(baseAsset.data || {}),
      generated,
      import: {
        originalFileName: sourceName,
        importedAt: new Date().toISOString(),
        converter: 'SuperFamiconv',
      },
    },
  });
  const doc = readAssetDocument(projectDir);
  const index = doc.assets.findIndex((entry) => entry.id === asset.id);
  if (index >= 0) doc.assets[index] = asset;
  else doc.assets.push(asset);
  const saved = writeAssetDocument(projectDir, doc);
  return {
    asset,
    assets: saved.assets,
    commandInfo: {
      command: plan.command,
      args: plan.args,
      cwd: plan.cwd,
      mode: kind === 'sprite' ? 'pce_sprite' : 'pce',
      dryRun: Boolean(options.dryRun),
    },
    conversion: commandResult,
  };
}

function previewSource(projectDir, relativePath = '') {
  if (!relativePath) throw new Error('asset source is required');
  const { absPath } = resolveUnderRoot(projectDir, relativePath, 'project');
  if (!fs.existsSync(absPath)) throw new Error('asset source not found');
  const data = fs.readFileSync(absPath).toString('base64');
  return {
    dataUrl: `data:${getMimeForPath(absPath)};base64,${data}`,
    mime: getMimeForPath(absPath),
    size: fs.statSync(absPath).size,
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
  return [`PNG:${path.basename(absPath)}`, 'Converted assets are', 'listed on screen.'];
}

function toCIdentifier(value) {
  const ident = String(value || 'asset').replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^([0-9])/, '_$1');
  return ident || 'asset';
}

function bufferToCArray(name, buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length === 0) return [];
  const lines = [`static const unsigned char ${name}[] = {`];
  for (let i = 0; i < buffer.length; i += 12) {
    const chunk = Array.from(buffer.subarray(i, i + 12)).map((value) => `0x${value.toString(16).padStart(2, '0')}`);
    lines.push(`  ${chunk.join(', ')}${i + 12 < buffer.length ? ',' : ''}`);
  }
  lines.push('};');
  return lines;
}

function readGeneratedBuffer(projectDir, relativePath) {
  if (!relativePath) return Buffer.alloc(0);
  try {
    const { absPath } = resolveUnderRoot(projectDir, relativePath, 'project');
    return fs.existsSync(absPath) ? fs.readFileSync(absPath) : Buffer.alloc(0);
  } catch (_err) {
    return Buffer.alloc(0);
  }
}

function cPointer(name, buffer) {
  return Buffer.isBuffer(buffer) && buffer.length > 0 ? name : '(const unsigned char *)0';
}

function numeric(value, min, max, fallback = 0) {
  return clampInt(value, min, max, fallback);
}

function generateConvertedAssetArrays(projectDir, assets, type) {
  const isSprite = type === 'sprite';
  const converted = assets.filter((asset) => asset.type === type && asset.data?.generated);
  const arrayLines = [];
  const metaLines = [];
  converted.forEach((asset, index) => {
    const ident = toCIdentifier(`pce_editor_${type}_${asset.id}`);
    const generated = asset.data.generated || {};
    const palette = readGeneratedBuffer(projectDir, generated.paletteFile);
    const tiles = readGeneratedBuffer(projectDir, generated.tilesFile);
    const map = isSprite ? Buffer.alloc(0) : readGeneratedBuffer(projectDir, generated.mapFile);
    arrayLines.push(...bufferToCArray(`${ident}_palette`, palette));
    arrayLines.push(...bufferToCArray(`${ident}_${isSprite ? 'patterns' : 'tiles'}`, tiles));
    if (!isSprite) arrayLines.push(...bufferToCArray(`${ident}_map`, map));
    if (arrayLines[arrayLines.length - 1] !== '') arrayLines.push('');
    const options = normalizeImageOptions(asset);
    if (isSprite) {
      metaLines.push(`  { ${cPointer(`${ident}_palette`, palette)}, ${palette.length}u, ${cPointer(`${ident}_patterns`, tiles)}, ${tiles.length}u, ${numeric(options.cellWidth, 16, 32, 16)}u, ${numeric(options.cellHeight, 16, 64, 16)}u, ${numeric(options.tileBase, 0, 2047, 384)}u, ${numeric(options.paletteBank, 0, 15, 0)}u, ${numeric(options.x, 0, 255, 144)}u, ${numeric(options.y, 0, 255, 104)}u }${index + 1 < converted.length ? ',' : ''}`);
    } else {
      const widthTiles = Math.max(1, Math.ceil(numeric(options.width, 0, 1024, 0) / 8));
      const heightTiles = Math.max(1, Math.ceil(numeric(options.height, 0, 1024, 0) / 8));
      metaLines.push(`  { ${cPointer(`${ident}_palette`, palette)}, ${palette.length}u, ${cPointer(`${ident}_tiles`, tiles)}, ${tiles.length}u, ${cPointer(`${ident}_map`, map)}, ${map.length}u, ${widthTiles}u, ${heightTiles}u, ${numeric(options.tileBase, 0, 2047, 32)}u, ${numeric(options.mapBase, 0, 2047, 0)}u, ${numeric(options.paletteBank, 0, 15, 0)}u }${index + 1 < converted.length ? ',' : ''}`);
    }
  });
  return { converted, arrayLines, metaLines };
}

function generateAssetSources(projectDir) {
  const doc = readAssetDocument(projectDir);
  const image = doc.assets.find((asset) => asset.type === 'image');
  const sound = doc.assets.find((asset) => asset.type === 'psg-sequence');
  const rows = image ? generateTextMosaicForImage(projectDir, image).slice(0, 14) : ['NO IMAGE ASSET'];
  const tonePeriod = Number(sound?.options?.period || 512);
  const bgGenerated = generateConvertedAssetArrays(projectDir, doc.assets, 'image');
  const spriteGenerated = generateConvertedAssetArrays(projectDir, doc.assets, 'sprite');

  const linesH = [
    '#ifndef PCE_EDITOR_GENERATED_ASSETS_H',
    '#define PCE_EDITOR_GENERATED_ASSETS_H',
    '',
    'typedef struct {',
    '  const unsigned char *palette;',
    '  unsigned int palette_size;',
    '  const unsigned char *tiles;',
    '  unsigned int tiles_size;',
    '  const unsigned char *map;',
    '  unsigned int map_size;',
    '  unsigned char width_tiles;',
    '  unsigned char height_tiles;',
    '  unsigned int tile_base;',
    '  unsigned int map_base;',
    '  unsigned char palette_bank;',
    '} pce_editor_bg_asset_t;',
    '',
    'typedef struct {',
    '  const unsigned char *palette;',
    '  unsigned int palette_size;',
    '  const unsigned char *patterns;',
    '  unsigned int patterns_size;',
    '  unsigned char cell_width;',
    '  unsigned char cell_height;',
    '  unsigned int pattern_base;',
    '  unsigned char palette_bank;',
    '  unsigned char x;',
    '  unsigned char y;',
    '} pce_editor_sprite_asset_t;',
    '',
    'extern const pce_editor_bg_asset_t pce_editor_bg_assets[];',
    'extern const unsigned char pce_editor_bg_asset_count;',
    'extern const pce_editor_sprite_asset_t pce_editor_sprite_assets[];',
    'extern const unsigned char pce_editor_sprite_asset_count;',
    'extern const char * const pce_editor_image_rows[];',
    'extern const unsigned char pce_editor_image_row_count;',
    'extern const unsigned int pce_editor_tone_period;',
    '',
    '#endif',
    '',
  ];

  const quotedRows = rows.map((row) => `  "${String(row).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`);
  const linesC = [
    '#include "assets.h"',
    '',
    ...bgGenerated.arrayLines,
    ...spriteGenerated.arrayLines,
    'const pce_editor_bg_asset_t pce_editor_bg_assets[] = {',
    ...(bgGenerated.metaLines.length ? bgGenerated.metaLines : ['  { (const unsigned char *)0, 0u, (const unsigned char *)0, 0u, (const unsigned char *)0, 0u, 0u, 0u, 0u, 0u, 0u }']),
    '};',
    `const unsigned char pce_editor_bg_asset_count = ${bgGenerated.converted.length};`,
    '',
    'const pce_editor_sprite_asset_t pce_editor_sprite_assets[] = {',
    ...(spriteGenerated.metaLines.length ? spriteGenerated.metaLines : ['  { (const unsigned char *)0, 0u, (const unsigned char *)0, 0u, 0u, 0u, 0u, 0u, 0u, 0u }']),
    '};',
    `const unsigned char pce_editor_sprite_asset_count = ${spriteGenerated.converted.length};`,
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
  return {
    headerPath,
    sourcePath,
    assetCount: doc.assets.length,
    imageRows: rows.length,
    bgCount: bgGenerated.converted.length,
    spriteCount: spriteGenerated.converted.length,
  };
}

module.exports = {
  ASSET_FILE,
  DEFAULT_BG_OPTIONS,
  DEFAULT_SPRITE_OPTIONS,
  SPRITE_CELL_SIZES,
  SUPPORTED_TYPES,
  buildSuperFamiconvPlan,
  defaultAssets,
  deleteAsset,
  ensureAssetFile,
  generateAssetSources,
  getAssetFilePath,
  importImage,
  listAssets,
  normalizeAsset,
  normalizeAssetDocument,
  previewSource,
  readAssetDocument,
  readPceImageJson,
  reorderAssets,
  resolveAssetSource,
  runSuperFamiconv,
  upsertAsset,
  writeAssetDocument,
};
