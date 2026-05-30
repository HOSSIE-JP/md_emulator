'use strict';

const fs = require('fs');
const path = require('path');

const CORE_IDS = Object.freeze({
  MEGA_DRIVE: 'mega-drive',
  PC_ENGINE: 'pc-engine',
});

const DEFAULT_CONFIG = Object.freeze({
  appId: 'jp.co.geroneko.game.editor.desktop',
  productName: 'GameEditor',
  displayName: 'Game Editor',
  defaultCoreId: CORE_IDS.MEGA_DRIVE,
  allowedCoreIds: [CORE_IDS.MEGA_DRIVE, CORE_IDS.PC_ENGINE],
  pluginsRoot: 'plugins',
  templatesRoot: 'template',
  projectsRootName: 'projects',
  toolsRootName: 'tools',
});

function normalizeCoreId(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === CORE_IDS.PC_ENGINE || raw === 'pce' || raw === 'pcengine' || raw === 'pc-engine-core') {
    return CORE_IDS.PC_ENGINE;
  }
  return CORE_IDS.MEGA_DRIVE;
}

function normalizeAllowedCoreIds(value, fallback = DEFAULT_CONFIG.allowedCoreIds) {
  const source = Array.isArray(value) && value.length > 0 ? value : fallback;
  const allowed = Array.from(new Set(source.map(normalizeCoreId)));
  return allowed.length > 0 ? allowed : [CORE_IDS.MEGA_DRIVE];
}

function resolveMaybeRelative(appRoot, value, fallbackName) {
  const raw = String(value || fallbackName || '').trim();
  if (!raw) return '';
  return path.isAbsolute(raw) ? raw : path.join(appRoot, raw);
}

function normalizeAppConfig(raw = {}) {
  const appRoot = path.resolve(raw.appRoot || raw.rootDir || process.cwd());
  const allowedCoreIds = normalizeAllowedCoreIds(raw.allowedCoreIds);
  const defaultCoreId = allowedCoreIds.includes(normalizeCoreId(raw.defaultCoreId))
    ? normalizeCoreId(raw.defaultCoreId)
    : allowedCoreIds[0];
  return {
    ...DEFAULT_CONFIG,
    ...raw,
    appRoot,
    defaultCoreId,
    allowedCoreIds,
    pluginsRoot: resolveMaybeRelative(appRoot, raw.pluginsRoot, DEFAULT_CONFIG.pluginsRoot),
    templatesRoot: resolveMaybeRelative(appRoot, raw.templatesRoot, DEFAULT_CONFIG.templatesRoot),
    projectsRootName: String(raw.projectsRootName || DEFAULT_CONFIG.projectsRootName),
    toolsRootName: String(raw.toolsRootName || DEFAULT_CONFIG.toolsRootName),
    migration: raw.migration && typeof raw.migration === 'object' ? { ...raw.migration } : {},
  };
}

function loadAppConfig(raw = {}) {
  const config = normalizeAppConfig(raw);
  global.__GAME_EDITOR_APP_CONFIG__ = config;
  return config;
}

function getCurrentAppConfig() {
  if (global.__GAME_EDITOR_APP_CONFIG__) return global.__GAME_EDITOR_APP_CONFIG__;
  return loadAppConfig(DEFAULT_CONFIG);
}

function getDefaultCoreId() {
  return getCurrentAppConfig().defaultCoreId;
}

function isCoreAllowed(coreId) {
  return getCurrentAppConfig().allowedCoreIds.includes(normalizeCoreId(coreId));
}

function normalizeCoreIdForApp(value) {
  const normalized = normalizeCoreId(value || getDefaultCoreId());
  return isCoreAllowed(normalized) ? normalized : getDefaultCoreId();
}

function filterCoresForApp(cores) {
  const allowed = new Set(getCurrentAppConfig().allowedCoreIds);
  return (Array.isArray(cores) ? cores : []).filter((core) => allowed.has(normalizeCoreId(core?.id || core)));
}

function pluginAllowedForApp(supportedCores) {
  const cores = Array.isArray(supportedCores) && supportedCores.length > 0
    ? supportedCores.map((core) => String(core || '').trim()).filter(Boolean)
    : [CORE_IDS.MEGA_DRIVE];
  if (cores.includes('*')) return true;
  return getCurrentAppConfig().allowedCoreIds.some((core) => cores.includes(core));
}

function applyPortableMode(electronApp, appRoot = getCurrentAppConfig().appRoot) {
  let markerExists = false;
  let dataDir;

  if (electronApp.isPackaged) {
    const exeDir = path.dirname(electronApp.getPath('exe'));
    markerExists = fs.existsSync(path.join(exeDir, 'portable'));
    dataDir = path.join(exeDir, 'data');
  } else {
    markerExists = fs.existsSync(path.join(appRoot, '.portable'));
    dataDir = path.join(appRoot, 'data');
  }

  if (markerExists) {
    electronApp.setPath('userData', dataDir);
    electronApp.setPath('logs', path.join(dataDir, 'logs'));
  }
}

function readJsonIfExists(filePath) {
  try {
    if (fs.existsSync(filePath)) return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (_) {}
  return null;
}

function isPceProjectConfig(config) {
  if (!config || typeof config !== 'object') return false;
  return normalizeCoreId(config.coreId || config.platform) === CORE_IDS.PC_ENGINE;
}

function copyDirNonDestructive(src, dest) {
  if (fs.existsSync(dest)) return false;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const name of fs.readdirSync(src)) {
      copyDirNonDestructive(path.join(src, name), path.join(dest, name));
    }
    return true;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  return true;
}

function findPceProjectDirs(sourceRoot) {
  const resolved = path.resolve(sourceRoot || '');
  if (!resolved || !fs.existsSync(resolved)) return [];
  const directConfig = readJsonIfExists(path.join(resolved, 'project.json'));
  if (isPceProjectConfig(directConfig)) return [resolved];
  return fs.readdirSync(resolved, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(resolved, entry.name))
    .filter((candidate) => isPceProjectConfig(readJsonIfExists(path.join(candidate, 'project.json'))));
}

function migratePceProjectsIfNeeded(electronApp) {
  const config = getCurrentAppConfig();
  if (!config.allowedCoreIds.includes(CORE_IDS.PC_ENGINE)) {
    return { ok: true, skipped: true, reason: 'pc-engine-disabled', copied: [], skippedProjects: [] };
  }

  const userData = electronApp.getPath('userData');
  const markerPath = path.join(userData, '.pce-project-migration.json');
  if (fs.existsSync(markerPath)) {
    return { ok: true, skipped: true, reason: 'already-ran', copied: [], skippedProjects: [] };
  }

  const targetRoot = path.join(userData, config.projectsRootName || 'projects');
  fs.mkdirSync(targetRoot, { recursive: true });
  const copied = [];
  const skippedProjects = [];
  const sourceRoots = Array.isArray(config.migration?.pceProjectSourceRoots)
    ? config.migration.pceProjectSourceRoots
    : [];

  for (const sourceRoot of sourceRoots) {
    for (const projectDir of findPceProjectDirs(sourceRoot)) {
      const dest = path.join(targetRoot, path.basename(projectDir));
      if (fs.existsSync(dest)) {
        skippedProjects.push({ source: projectDir, target: dest, reason: 'exists' });
        continue;
      }
      copyDirNonDestructive(projectDir, dest);
      copied.push({ source: projectDir, target: dest });
    }
  }

  fs.writeFileSync(markerPath, JSON.stringify({ migratedAt: new Date().toISOString(), copied, skippedProjects }, null, 2), 'utf-8');
  return { ok: true, copied, skippedProjects };
}

function createGameEditorApp(config, launcher) {
  const normalized = loadAppConfig(config);
  if (typeof launcher === 'function') return launcher(normalized);
  return normalized;
}

module.exports = {
  CORE_IDS,
  applyPortableMode,
  createGameEditorApp,
  filterCoresForApp,
  getCurrentAppConfig,
  getDefaultCoreId,
  isCoreAllowed,
  loadAppConfig,
  migratePceProjectsIfNeeded,
  normalizeAppConfig,
  normalizeCoreId,
  normalizeCoreIdForApp,
  pluginAllowedForApp,
};
