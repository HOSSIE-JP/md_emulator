'use strict';

/**
 * plugin-manager.js
 * electron/plugins/ フォルダのプラグインを管理する（Main プロセス専用）。
 *
 * プラグイン構成:
 *   electron/plugins/<id>/manifest.json
 *   electron/plugins/<id>/index.js
 *
 * manifest v2 (後方互換あり):
 *   {
 *     "id": "plugin-id",
 *     "name": "Plugin Name",
 *     "description": "...",
 *     "version": "1.0.0",
 *     "type": "build",                // 旧式: 単一タイプ
 *     "types": ["build", "logger"], // 新式: 複数タイプ
 *     "hooks": ["onBuildStart", "onBuildLog", "onBuildEnd"]
 *   }
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

function normalizePluginTypes(manifest) {
  if (Array.isArray(manifest.types) && manifest.types.length > 0) {
    return manifest.types.map((t) => String(t || '').trim()).filter(Boolean);
  }
  if (manifest.type) {
    return [String(manifest.type).trim()].filter(Boolean);
  }
  return ['unknown'];
}

function normalizeHooks(manifest) {
  if (!Array.isArray(manifest.hooks)) return [];
  return manifest.hooks.map((h) => String(h || '').trim()).filter(Boolean);
}

function normalizeDependencies(manifest) {
  if (!Array.isArray(manifest.dependencies)) return [];
  return Array.from(new Set(
    manifest.dependencies
      .map((id) => String(id || '').trim())
      .filter(Boolean),
  ));
}

function isPluginEnabled(id) {
  const s = readState();
  return Boolean(s[id]?.enabled ?? true);
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
      const pluginTypes = normalizePluginTypes(manifest);

      return {
        id,
        name: manifest.name || id,
        description: manifest.description || '',
        version: manifest.version || '0.0.0',
        pluginTypes,
        pluginType: pluginTypes[0] || 'unknown',
        tab: manifest.tab || null,
        dependencies: normalizeDependencies(manifest),
        hooks: normalizeHooks(manifest),
        hasGenerator,
        // デフォルトは有効 (state に記録がなければ true)
        enabled: Boolean(state[id]?.enabled ?? true),
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id, 'ja'));
}

// ── 有効 / 無効切替 ────────────────────────────────────────────────────────

function setEnabled(id, enabled) {
  const s = readState();
  s[id] = { ...(s[id] || {}), enabled: Boolean(enabled) };
  writeState(s);
}

function setEnabledWithDependencies(id, enabled) {
  const pluginId = String(id || '').trim();
  if (!pluginId) {
    return { ok: false, error: 'plugin id is empty', changed: [], changedIds: [] };
  }

  const plugins = listPlugins();
  const pluginMap = new Map(plugins.map((p) => [p.id, p]));
  if (!pluginMap.has(pluginId)) {
    return { ok: false, error: `plugin not found: ${pluginId}`, changed: [], changedIds: [] };
  }

  const state = readState();
  const changed = [];
  const missingDependencies = [];

  const setStateEnabled = (targetId, nextEnabled, reason) => {
    const prevEnabled = Boolean(state[targetId]?.enabled ?? true);
    if (prevEnabled === nextEnabled) return;
    state[targetId] = { ...(state[targetId] || {}), enabled: nextEnabled };
    changed.push({ id: targetId, enabled: nextEnabled, reason });
  };

  if (enabled) {
    const stack = [pluginId];
    const visited = new Set();
    while (stack.length > 0) {
      const currentId = stack.pop();
      if (visited.has(currentId)) continue;
      visited.add(currentId);

      const current = pluginMap.get(currentId);
      if (!current) continue;
      setStateEnabled(currentId, true, currentId === pluginId ? 'self' : `required-by:${pluginId}`);

      (current.dependencies || []).forEach((depId) => {
        if (pluginMap.has(depId)) {
          stack.push(depId);
        } else {
          missingDependencies.push(depId);
        }
      });
    }
  } else {
    const dependentsMap = new Map();
    plugins.forEach((plugin) => {
      (plugin.dependencies || []).forEach((depId) => {
        const current = dependentsMap.get(depId) || [];
        current.push(plugin.id);
        dependentsMap.set(depId, current);
      });
    });

    const stack = [pluginId];
    const visited = new Set();
    while (stack.length > 0) {
      const currentId = stack.pop();
      if (visited.has(currentId)) continue;
      visited.add(currentId);

      setStateEnabled(currentId, false, currentId === pluginId ? 'self' : `depends-on:${pluginId}`);
      const dependents = dependentsMap.get(currentId) || [];
      dependents.forEach((dependerId) => stack.push(dependerId));
    }
  }

  writeState(state);
  return {
    ok: true,
    changed,
    changedIds: changed.map((entry) => entry.id),
    missingDependencies: Array.from(new Set(missingDependencies)),
  };
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

async function runGenerator(id, assets, context = {}) {
  if (!isPluginEnabled(id)) {
    return { ok: false, error: `プラグイン "${id}" は無効になっています` };
  }
  const plugin = getPlugin(id);
  if (!plugin) return { ok: false, error: `プラグイン "${id}" の index.js が見つかりません` };
  if (plugin._loadError) return { ok: false, error: `プラグイン "${id}" の読み込みエラー: ${plugin._loadError}` };

  const fn = typeof plugin.generateSourceAsync === 'function'
    ? plugin.generateSourceAsync
    : plugin.generateSource;

  if (typeof fn !== 'function') {
    return { ok: false, error: `プラグイン "${id}" に generateSource 関数がありません` };
  }

  try {
    const result = await fn(assets, context);
    return result || { ok: true, sourceCode: '' };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}

async function invokeHook(id, hookName, payload = {}, context = {}) {
  if (!isPluginEnabled(id)) {
    return { ok: false, error: `プラグイン "${id}" は無効になっています` };
  }

  const plugin = getPlugin(id);
  if (!plugin) return { ok: false, error: `プラグイン "${id}" の index.js が見つかりません` };
  if (plugin._loadError) return { ok: false, error: `プラグイン "${id}" の読み込みエラー: ${plugin._loadError}` };

  const hookFn = plugin[hookName];
  if (typeof hookFn !== 'function') {
    return { ok: true, skipped: true };
  }

  try {
    const result = await hookFn(payload, context);
    if (result && typeof result === 'object' && Object.prototype.hasOwnProperty.call(result, 'ok')) {
      return result;
    }
    return { ok: true, result: result === undefined ? null : result };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}

module.exports = {
  listPlugins,
  setEnabled,
  setEnabledWithDependencies,
  runGenerator,
  invokeHook,
  isPluginEnabled,
};
