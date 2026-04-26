'use strict';

/**
 * plugin-manager.js
 * electron/plugins/ フォルダのプラグインを管理する（Main プロセス専用）。
 *
 * プラグイン構成:
 *   electron/plugins/<id>/manifest.json   – { id, name, description, version }
 *   electron/plugins/<id>/index.js        – module.exports = { manifest, generateSource(assets) }
 */

const path = require('path');
const fs = require('fs');
const { app } = require('electron');

function getPluginsDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'plugins');
  }
  return path.join(__dirname, 'plugins');
}

// ── ステート永続化 ─────────────────────────────────────────────────────────

function getStateFile() {
  return path.join(app.getPath('userData'), 'plugins-state.json');
}

function readState() {
  try {
    if (fs.existsSync(getStateFile())) {
      return JSON.parse(fs.readFileSync(getStateFile(), 'utf-8'));
    }
  } catch (_) {}
  return {};
}

function writeState(s) {
  const dir = path.dirname(getStateFile());
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(getStateFile(), JSON.stringify(s, null, 2), 'utf-8');
}

// ── プラグイン一覧 ──────────────────────────────────────────────────────────

function listPlugins() {
  const pluginsDir = getPluginsDir();
  if (!fs.existsSync(pluginsDir)) return [];
  const state = readState();

  return fs.readdirSync(pluginsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const id = d.name;
      let manifest = { id, name: id, description: '', version: '0.0.0' };
      const manifestPath = path.join(pluginsDir, id, 'manifest.json');
      try {
        manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      } catch (_) {}

      // index.js の有無を確認してジェネレータがあるかを伝える
      const hasGenerator = fs.existsSync(path.join(pluginsDir, id, 'index.js'));

      return {
        id,
        name: manifest.name || id,
        description: manifest.description || '',
        version: manifest.version || '0.0.0',
        hasGenerator,
        // デフォルトは有効 (state に記録がなければ true)
        enabled: Boolean(state[id]?.enabled ?? true),
      };
    });
}

// ── 有効 / 無効切替 ────────────────────────────────────────────────────────

function setEnabled(id, enabled) {
  const s = readState();
  s[id] = { ...(s[id] || {}), enabled: Boolean(enabled) };
  writeState(s);
}

// ── ジェネレータ実行 ────────────────────────────────────────────────────────

function getPlugin(id) {
  const indexPath = path.join(getPluginsDir(), id, 'index.js');
  if (!fs.existsSync(indexPath)) return null;
  // require キャッシュを強制クリアしてリロードに対応
  const resolved = require.resolve(indexPath);
  delete require.cache[resolved];
  try {
    return require(indexPath);
  } catch (e) {
    return { _loadError: String(e.message || e) };
  }
}

function runGenerator(id, assets) {
  const s = readState();
  if (s[id] !== undefined && !s[id].enabled) {
    return { ok: false, error: `プラグイン "${id}" は無効になっています` };
  }
  const plugin = getPlugin(id);
  if (!plugin) return { ok: false, error: `プラグイン "${id}" の index.js が見つかりません` };
  if (plugin._loadError) return { ok: false, error: `プラグイン "${id}" の読み込みエラー: ${plugin._loadError}` };
  if (typeof plugin.generateSource !== 'function') {
    return { ok: false, error: `プラグイン "${id}" に generateSource 関数がありません` };
  }
  try {
    return plugin.generateSource(assets);
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}

module.exports = { listPlugins, setEnabled, runGenerator };
