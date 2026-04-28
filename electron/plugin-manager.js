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
const { pathToFileURL } = require('url');
const { app } = require('electron');

function getPluginsDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'plugins');
  }
  return path.join(__dirname, 'plugins');
}

// ユーザーが独自に追加できるプラグインディレクトリ (常に書き込み可能)
function getUserPluginsDir() {
  return path.join(app.getPath('userData'), 'plugins');
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

function normalizeRendererCapabilities(renderer) {
  if (!Array.isArray(renderer?.capabilities)) return [];
  return Array.from(new Set(
    renderer.capabilities
      .map((capability) => String(capability || '').trim())
      .filter(Boolean),
  ));
}

function resolvePluginFile(pluginDir, relativePath) {
  const value = String(relativePath || '').trim();
  if (!value || path.isAbsolute(value)) return null;

  const root = path.resolve(pluginDir);
  const abs = path.resolve(root, value);
  const rel = path.relative(root, abs);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) {
    return null;
  }
  return abs;
}

function normalizeRenderer(manifest, pluginDir) {
  const raw = manifest.renderer && typeof manifest.renderer === 'object'
    ? manifest.renderer
    : null;
  if (!raw) {
    return { renderer: null, rendererAssets: null, hasRenderer: false };
  }

  const renderer = {
    entry: String(raw.entry || '').trim(),
    styles: Array.isArray(raw.styles)
      ? raw.styles.map((style) => String(style || '').trim()).filter(Boolean)
      : [],
    page: String(raw.page || raw.mountPage || manifest.tab?.page || '').trim(),
    capabilities: normalizeRendererCapabilities(raw),
  };

  const entryPath = resolvePluginFile(pluginDir, renderer.entry);
  if (!entryPath || !fs.existsSync(entryPath)) {
    return {
      renderer: { ...renderer, error: 'renderer entry is missing or outside plugin directory' },
      rendererAssets: null,
      hasRenderer: false,
    };
  }

  const stylePaths = [];
  for (const style of renderer.styles) {
    const stylePath = resolvePluginFile(pluginDir, style);
    if (!stylePath || !fs.existsSync(stylePath)) {
      return {
        renderer: { ...renderer, error: `renderer style is missing or outside plugin directory: ${style}` },
        rendererAssets: null,
        hasRenderer: false,
      };
    }
    stylePaths.push(stylePath);
  }

  return {
    renderer,
    rendererAssets: {
      scriptUrl: pathToFileURL(entryPath).href,
      styleUrls: stylePaths.map((stylePath) => pathToFileURL(stylePath).href),
    },
    hasRenderer: true,
  };
}

function isPluginEnabled(id) {
  const s = readState();
  return Boolean(s[id]?.enabled ?? true);
}

// ── プラグイン一覧 ──────────────────────────────────────────────────────────

function listPlugins() {
  const builtinDir = getPluginsDir();
  const userDir = getUserPluginsDir();
  const state = readState();

  // ユーザープラグインを優先し、同一 ID は上書き
  const pluginEntries = []; // { id, baseDir }
  const seen = new Set();

  function collectFrom(dir, isUser) {
    if (!fs.existsSync(dir)) return;
    fs.readdirSync(dir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .forEach((d) => {
        if (!seen.has(d.name)) {
          seen.add(d.name);
          pluginEntries.push({ id: d.name, baseDir: dir, isUser });
        }
      });
  }

  collectFrom(userDir, true);    // ユーザープラグイン優先
  collectFrom(builtinDir, false); // 組み込みプラグイン

  return pluginEntries
    .map(({ id, baseDir, isUser }) => {
      let manifest = { id, name: id, description: '', version: '0.0.0' };
      const manifestPath = path.join(baseDir, id, 'manifest.json');
      try {
        manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      } catch (_) {}

      const pluginDir = path.join(baseDir, id);
      const hasGenerator = fs.existsSync(path.join(pluginDir, 'index.js'));
      const pluginTypes = normalizePluginTypes(manifest);
      const rendererInfo = normalizeRenderer(manifest, pluginDir);

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
        renderer: rendererInfo.renderer,
        hasRenderer: rendererInfo.hasRenderer,
        rendererAssets: rendererInfo.rendererAssets,
        enabled: Boolean(state[id]?.enabled ?? true),
        isUserPlugin: isUser,  // ユーザー追加プラグインか否か
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id, 'ja'));
}

function getRendererAssets(id) {
  const plugin = listPlugins().find((p) => p.id === id);
  if (!plugin) {
    return { ok: false, error: `plugin not found: ${id}` };
  }
  if (!plugin.hasRenderer || !plugin.rendererAssets) {
    return { ok: false, error: `plugin has no renderer module: ${id}` };
  }
  return {
    ok: true,
    id: plugin.id,
    renderer: plugin.renderer,
    rendererAssets: plugin.rendererAssets,
  };
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
  // ユーザープラグインを優先して探す
  const userIndexPath = path.join(getUserPluginsDir(), id, 'index.js');
  const builtinIndexPath = path.join(getPluginsDir(), id, 'index.js');
  const indexPath = fs.existsSync(userIndexPath) ? userIndexPath
    : fs.existsSync(builtinIndexPath) ? builtinIndexPath
    : null;
  if (!indexPath) return null;
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
  getRendererAssets,
  setEnabled,
  setEnabledWithDependencies,
  runGenerator,
  invokeHook,
  isPluginEnabled,
  getPluginsDir,
  getUserPluginsDir,
};
