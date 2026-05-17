'use strict';

const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { app } = require('electron');

function getPluginsDir() {
  return app.isPackaged ? path.join(process.resourcesPath, 'plugins') : path.join(__dirname, 'plugins');
}

function getUserPluginsDir() {
  return path.join(app.getPath('userData'), 'plugins');
}

function getStateFile() {
  return path.join(app.getPath('userData'), 'plugins-state.json');
}

function readState() {
  try {
    if (fs.existsSync(getStateFile())) return JSON.parse(fs.readFileSync(getStateFile(), 'utf-8'));
  } catch (_) {}
  return {};
}

function writeState(state) {
  fs.mkdirSync(path.dirname(getStateFile()), { recursive: true });
  fs.writeFileSync(getStateFile(), JSON.stringify(state, null, 2), 'utf-8');
}

function uniqueStrings(values) {
  return Array.from(new Set((Array.isArray(values) ? values : [])
    .map((value) => String(value || '').trim())
    .filter(Boolean)));
}

function normalizeRoles(manifest = {}) {
  return (Array.isArray(manifest.roles) ? manifest.roles : []).map((role) => {
    const id = String(typeof role === 'string' ? role : role?.id || '').trim();
    if (!id) return null;
    const order = Number(role?.order);
    return {
      id,
      label: String(role?.label || (id === 'builder' ? 'Build' : id === 'testplay' ? 'Test Play' : id)),
      exclusive: Object.prototype.hasOwnProperty.call(role || {}, 'exclusive') ? Boolean(role.exclusive) : true,
      order: Number.isFinite(order) ? order : (id === 'builder' ? 10 : id === 'testplay' ? 20 : 100),
    };
  }).filter(Boolean).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id, 'ja'));
}

function safePluginPath(pluginDir, relativePath) {
  const value = String(relativePath || '').trim();
  if (!value || path.isAbsolute(value)) return null;
  const root = path.resolve(pluginDir);
  const abs = path.resolve(root, value);
  const rel = path.relative(root, abs);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) return null;
  return abs;
}

function normalizeRenderer(manifest, pluginDir) {
  const raw = manifest.renderer && typeof manifest.renderer === 'object' ? manifest.renderer : null;
  if (!raw) return { renderer: null, rendererAssets: null, hasRenderer: false };

  const renderer = {
    entry: String(raw.entry || '').trim(),
    styles: uniqueStrings(raw.styles),
    page: String(raw.page || raw.mountPage || manifest.tab?.page || '').trim(),
    capabilities: uniqueStrings(raw.capabilities),
  };

  const entryPath = safePluginPath(pluginDir, renderer.entry);
  if (!entryPath || !fs.existsSync(entryPath)) {
    return { renderer: { ...renderer, error: 'renderer entry is missing or outside plugin directory' }, rendererAssets: null, hasRenderer: false };
  }

  const stylePaths = [];
  for (const style of renderer.styles) {
    const stylePath = safePluginPath(pluginDir, style);
    if (!stylePath || !fs.existsSync(stylePath)) {
      return { renderer: { ...renderer, error: `renderer style is missing or outside plugin directory: ${style}` }, rendererAssets: null, hasRenderer: false };
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

function collectPluginDirs() {
  const entries = [];
  const seen = new Set();
  const collect = (baseDir, isUserPlugin) => {
    if (!fs.existsSync(baseDir)) return;
    for (const entry of fs.readdirSync(baseDir, { withFileTypes: true })) {
      if (!entry.isDirectory() || seen.has(entry.name)) continue;
      seen.add(entry.name);
      entries.push({ id: entry.name, baseDir, isUserPlugin });
    }
  };
  collect(getUserPluginsDir(), true);
  collect(getPluginsDir(), false);
  return entries;
}

function normalizeMainApi(manifest = {}) {
  const mainApi = manifest.mainApi && typeof manifest.mainApi === 'object' ? manifest.mainApi : {};
  return {
    hooks: uniqueStrings(mainApi.hooks),
    capabilities: uniqueStrings(mainApi.capabilities),
  };
}

function listPlugins() {
  const state = readState();
  return collectPluginDirs().map(({ id, baseDir, isUserPlugin }) => {
    const pluginDir = path.join(baseDir, id);
    const manifestPath = path.join(pluginDir, 'manifest.json');
    let manifest = { id, name: id, version: '0.0.0', types: ['unknown'] };
    try {
      manifest = { ...manifest, ...JSON.parse(fs.readFileSync(manifestPath, 'utf-8')) };
    } catch (_) {}
    const rendererInfo = normalizeRenderer(manifest, pluginDir);
    const pluginTypes = uniqueStrings(manifest.types).length > 0 ? uniqueStrings(manifest.types) : ['unknown'];
    return {
      id,
      name: manifest.name || id,
      description: manifest.description || '',
      version: manifest.version || '0.0.0',
      icon: String(manifest.icon || manifest.tab?.icon || '').trim().toLowerCase(),
      pluginTypes,
      pluginType: pluginTypes[0],
      tab: manifest.tab || null,
      dependencies: uniqueStrings(manifest.dependencies),
      hooks: uniqueStrings(manifest.hooks),
      mainApi: normalizeMainApi(manifest),
      permissions: uniqueStrings(manifest.permissions),
      roles: normalizeRoles(manifest),
      hasGenerator: fs.existsSync(path.join(pluginDir, 'index.js')),
      renderer: rendererInfo.renderer,
      hasRenderer: rendererInfo.hasRenderer,
      rendererAssets: rendererInfo.rendererAssets,
      enabled: Boolean(state[id]?.enabled ?? true),
      isUserPlugin,
    };
  }).sort((a, b) => a.id.localeCompare(b.id, 'ja'));
}

function isPluginEnabled(id) {
  return Boolean(readState()[id]?.enabled ?? true);
}

function roleSupported(plugin, roleId) {
  return (plugin?.roles || []).some((role) => role.id === roleId && role.exclusive !== false);
}

function exclusiveRoleIds(plugin) {
  return (plugin?.roles || []).filter((role) => role.exclusive !== false).map((role) => role.id);
}

function setEnabled(id, enabled) {
  const state = readState();
  state[id] = { ...(state[id] || {}), enabled: Boolean(enabled) };
  writeState(state);
}

function setEnabledWithDependencies(id, enabled) {
  const pluginId = String(id || '').trim();
  const plugins = listPlugins();
  const pluginMap = new Map(plugins.map((plugin) => [plugin.id, plugin]));
  if (!pluginMap.has(pluginId)) return { ok: false, error: `plugin not found: ${pluginId}`, changed: [], changedIds: [] };

  const state = readState();
  const changed = [];
  const missingDependencies = [];
  const setState = (targetId, nextEnabled, reason) => {
    const prev = Boolean(state[targetId]?.enabled ?? true);
    if (prev === nextEnabled) return;
    state[targetId] = { ...(state[targetId] || {}), enabled: nextEnabled };
    changed.push({ id: targetId, enabled: nextEnabled, reason });
  };
  const dependents = new Map();
  for (const plugin of plugins) {
    for (const dep of plugin.dependencies || []) {
      dependents.set(dep, [...(dependents.get(dep) || []), plugin.id]);
    }
  }
  const disableTree = (rootId, reason) => {
    const stack = [rootId];
    const visited = new Set();
    while (stack.length > 0) {
      const current = stack.pop();
      if (visited.has(current)) continue;
      visited.add(current);
      setState(current, false, current === rootId ? reason : `depends-on:${rootId}`);
      (dependents.get(current) || []).forEach((next) => stack.push(next));
    }
  };

  if (enabled) {
    const stack = [pluginId];
    const visited = new Set();
    while (stack.length > 0) {
      const current = stack.pop();
      if (visited.has(current)) continue;
      visited.add(current);
      const plugin = pluginMap.get(current);
      if (!plugin) continue;
      setState(current, true, current === pluginId ? 'self' : `required-by:${pluginId}`);
      for (const dep of plugin.dependencies || []) {
        if (pluginMap.has(dep)) stack.push(dep);
        else missingDependencies.push(dep);
      }
    }
    for (const roleId of exclusiveRoleIds(pluginMap.get(pluginId))) {
      for (const plugin of plugins) {
        if (plugin.id !== pluginId && roleSupported(plugin, roleId)) disableTree(plugin.id, `exclusive-role:${roleId}`);
      }
    }
  } else {
    disableTree(pluginId, 'self');
  }

  writeState(state);
  return { ok: true, changed, changedIds: changed.map((entry) => entry.id), missingDependencies: uniqueStrings(missingDependencies) };
}

function setExclusiveRoleSelection(roleId, id) {
  const role = String(roleId || '').trim();
  const pluginId = String(id || '').trim();
  if (!role) return { ok: false, error: 'role id is empty', changed: [], changedIds: [] };
  if (!pluginId) return { ok: true, changed: [], changedIds: [], missingDependencies: [] };
  const plugin = listPlugins().find((entry) => entry.id === pluginId);
  if (!plugin) return { ok: false, error: `plugin not found: ${pluginId}`, changed: [], changedIds: [] };
  if (!roleSupported(plugin, role)) return { ok: false, error: `plugin ${pluginId} does not support exclusive role: ${role}`, changed: [], changedIds: [] };
  return setEnabledWithDependencies(pluginId, true);
}

function getPluginDirectory(id) {
  const pluginId = String(id || '').trim();
  if (!pluginId) return null;
  const userDir = path.join(getUserPluginsDir(), pluginId);
  if (fs.existsSync(userDir)) return userDir;
  const builtinDir = path.join(getPluginsDir(), pluginId);
  return fs.existsSync(builtinDir) ? builtinDir : null;
}

function getPlugin(id) {
  const dir = getPluginDirectory(id);
  if (!dir) return null;
  const indexPath = path.join(dir, 'index.js');
  if (!fs.existsSync(indexPath)) return null;
  const resolved = require.resolve(indexPath);
  delete require.cache[resolved];
  try {
    return require(resolved);
  } catch (err) {
    return { _loadError: String(err.message || err) };
  }
}

async function invokeHook(id, hookName, payload = {}, context = {}) {
  if (!isPluginEnabled(id)) return { ok: false, error: `プラグイン "${id}" は無効になっています` };
  const plugin = getPlugin(id);
  if (!plugin) return { ok: false, error: `プラグイン "${id}" の index.js が見つかりません` };
  if (plugin._loadError) return { ok: false, error: `プラグイン "${id}" の読み込みエラー: ${plugin._loadError}` };
  const hook = plugin[hookName];
  if (typeof hook !== 'function') return { ok: true, skipped: true };
  try {
    const result = await hook(payload, context);
    return result && typeof result === 'object' && Object.prototype.hasOwnProperty.call(result, 'ok')
      ? result
      : { ok: true, result: result ?? null };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
}

function canInvokeRendererHook(pluginInfo, hookName) {
  const hook = String(hookName || '').trim();
  return Boolean(
    hook
    && pluginInfo?.enabled
    && (pluginInfo.hooks || []).includes(hook)
    && (pluginInfo.mainApi?.hooks || []).includes(hook),
  );
}

async function invokeRendererHook(id, hookName, payload = {}, context = {}) {
  const plugin = listPlugins().find((entry) => entry.id === id);
  if (!plugin) return { ok: false, error: `plugin not found: ${id}` };
  if (!canInvokeRendererHook(plugin, hookName)) return { ok: false, error: `renderer is not allowed to invoke hook: ${id}.${hookName}` };
  return invokeHook(id, hookName, payload, context);
}

function getRendererAssets(id) {
  const plugin = listPlugins().find((entry) => entry.id === id);
  if (!plugin) return { ok: false, error: `plugin not found: ${id}` };
  if (!plugin.hasRenderer || !plugin.rendererAssets) return { ok: false, error: `plugin has no renderer module: ${id}` };
  return { ok: true, id: plugin.id, renderer: plugin.renderer, rendererAssets: plugin.rendererAssets };
}

module.exports = {
  canInvokeRendererHook,
  getPluginDirectory,
  getPluginsDir,
  getRendererAssets,
  getUserPluginsDir,
  invokeHook,
  invokeRendererHook,
  isPluginEnabled,
  listPlugins,
  setEnabled,
  setEnabledWithDependencies,
  setExclusiveRoleSelection,
};
