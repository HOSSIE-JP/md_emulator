'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const manifest = require('./manifest.json');
const { convertMidiBufferToVgm } = require('./converter-core');

function sanitizeSymbol(value, fallback = 'midi_bgm') {
  const raw = String(value || fallback)
    .replace(/\.[^.]+$/, '')
    .replace(/[^A-Za-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();
  const symbol = raw || fallback;
  return /^[A-Za-z_]/.test(symbol) ? symbol : `bgm_${symbol}`;
}

function normalizeBool(value, defaultValue = true) {
  if (value == null) return defaultValue;
  return Boolean(value);
}

function toProjectRelative(projectDir, absolutePath) {
  return path.relative(projectDir, absolutePath).replace(/\\/g, '/');
}

function findBundledXgmTool(payload = {}) {
  const explicit = String(payload.xgmToolPath || '');
  if (explicit) return explicit;

  const candidates = [
    path.join(__dirname, '..', '..', 'data', 'tools', 'sgdk', 'SGDK-2.11', 'bin', 'xgmtool.exe'),
    process.env.GDK ? path.join(process.env.GDK, 'bin', 'xgmtool.exe') : '',
    process.env.SGDK ? path.join(process.env.SGDK, 'bin', 'xgmtool.exe') : '',
    path.join('D:', 'homebrew', 'SGDK', 'sgdk', 'current', 'bin', 'xgmtool.exe'),
  ].filter(Boolean);

  return candidates.find((candidate) => fs.existsSync(candidate)) || '';
}

function convertMidiMusic(payload = {}, context = {}) {
  const logger = context.logger || console;
  const sourcePath = String(payload.sourcePath || '');
  if (!sourcePath || !fs.existsSync(sourcePath)) {
    return { ok: false, error: '入力 MIDI ファイルが見つかりません。' };
  }

  const projectDir = String(context.projectDir || payload.projectDir || '');
  if (!projectDir) {
    return { ok: false, error: 'projectDir が指定されていません。' };
  }

  const symbol = sanitizeSymbol(payload.symbol || path.basename(sourcePath, path.extname(sourcePath)));
  const outputs = payload.outputs || {};
  const writeVgm = normalizeBool(outputs.vgm, true);
  const writeXgm = normalizeBool(outputs.xgm, true);
  const registerAsset = normalizeBool(outputs.registerAsset, false);
  if (!writeVgm && !writeXgm) {
    return { ok: false, error: 'VGM または XGM の出力を少なくとも 1 つ有効にしてください。' };
  }

  const musicDir = path.join(projectDir, 'res', 'music');
  fs.mkdirSync(musicDir, { recursive: true });

  const vgmPath = path.join(musicDir, `${symbol}.vgm`);
  const xgmPath = path.join(musicDir, `${symbol}.xgm`);

  logger.info?.(`[${manifest.id}] MIDI 変換開始: ${path.basename(sourcePath)} -> ${symbol}`);
  let converted = null;
  try {
    converted = convertMidiBufferToVgm(fs.readFileSync(sourcePath));
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
  }
  if (!converted?.ok) return converted || { ok: false, error: 'MIDI 変換に失敗しました。' };

  fs.writeFileSync(vgmPath, converted.vgm);

  const warnings = Array.isArray(converted.warnings) ? [...converted.warnings] : [];
  const diagnostics = Array.isArray(converted.diagnostics) ? [...converted.diagnostics] : [];

  if (writeXgm) {
    const xgmTool = findBundledXgmTool(payload);
    if (!xgmTool) {
      const message = 'xgmtool が見つからないため XGM 変換をスキップしました。VGM は保存済みです。';
      warnings.push(message);
      diagnostics.push({ level: 'warn', code: 'midi-converter-xgm', message });
    } else {
      const xgmResult = spawnSync(xgmTool, [vgmPath, xgmPath], {
        windowsHide: true,
        encoding: 'utf-8',
      });
      if (xgmResult.error || xgmResult.status !== 0 || !fs.existsSync(xgmPath)) {
        const detail = (xgmResult.stderr || xgmResult.stdout || xgmResult.error?.message || '').trim();
        const message = `XGM 変換に失敗しました: ${detail || 'xgmtool failed'}`;
        warnings.push(message);
        diagnostics.push({ level: 'warn', code: 'midi-converter-xgm', message });
      }
    }
  }

  const files = {};
  if (fs.existsSync(vgmPath)) files.vgm = toProjectRelative(projectDir, vgmPath);
  if (writeXgm && fs.existsSync(xgmPath)) files.xgm = toProjectRelative(projectDir, xgmPath);

  return {
    ok: true,
    pluginId: manifest.id,
    symbol,
    files,
    absoluteFiles: {
      vgm: fs.existsSync(vgmPath) ? vgmPath : '',
      xgm: fs.existsSync(xgmPath) ? xgmPath : '',
    },
    asset: registerAsset && files.vgm ? {
      type: 'XGM2',
      name: symbol,
      sourcePath: `music/${symbol}.vgm`,
    } : null,
    diagnostics,
    warnings,
    stats: converted.stats || {},
  };
}

module.exports = {
  convertMidiMusic,
  _private: {
    findBundledXgmTool,
    sanitizeSymbol,
  },
};
