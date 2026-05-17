'use strict';

const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { app, BrowserWindow, dialog, ipcMain, Menu, shell } = require('electron');
const { applyPortableMode } = require('./portable-paths');
const { resolveUnderRoot } = require('./pce-file-safety');

const dataDir = applyPortableMode(app, { dirname: __dirname });

const buildSystem = require('./pce-build-system');
const setupManager = require('./pce-setup-manager');
const assetManager = require('./pce-asset-manager');
const pluginManager = require('./plugin-manager');
const packageJson = require('./package.json');

let mainWindow = null;
let testPlayWindow = null;
let currentTestPlayContext = null;
let isQuitting = false;

function sendToRenderer(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function createPluginLogger(pluginId) {
  return {
    info: (message) => sendToRenderer('plugin-log', { pluginId, level: 'info', message: String(message || '') }),
    warn: (message) => sendToRenderer('plugin-log', { pluginId, level: 'warn', message: String(message || '') }),
    error: (message) => sendToRenderer('plugin-log', { pluginId, level: 'error', message: String(message || '') }),
    debug: (message) => sendToRenderer('plugin-log', { pluginId, level: 'debug', message: String(message || '') }),
  };
}

function pluginSupportsRole(plugin, roleId) {
  return Array.isArray(plugin?.roles) && plugin.roles.some((role) => role?.id === roleId);
}

function resolvePluginForRole(roleId) {
  let pluginId = buildSystem.getPluginRole(roleId);
  const plugins = pluginManager.listPlugins();
  const selected = plugins.find((plugin) => plugin.id === pluginId && plugin.enabled && pluginSupportsRole(plugin, roleId));
  if (selected) return selected.id;

  const fallback = plugins
    .filter((plugin) => plugin.enabled && pluginSupportsRole(plugin, roleId))
    .sort((a, b) => {
      const roleA = a.roles.find((role) => role.id === roleId);
      const roleB = b.roles.find((role) => role.id === roleId);
      const orderA = Number(roleA?.order ?? 1000);
      const orderB = Number(roleB?.order ?? 1000);
      if (orderA !== orderB) return orderA - orderB;
      return String(a.name || a.id).localeCompare(String(b.name || b.id), 'ja');
    })[0];
  if (fallback) {
    buildSystem.setPluginRole(roleId, fallback.id);
    return fallback.id;
  }
  return '';
}

function resolvePluginAssetPath(pluginId, relativePath) {
  const pluginDir = pluginManager.getPluginDirectory(pluginId);
  if (!pluginDir) throw new Error(`plugin directory not found: ${pluginId}`);
  const root = path.resolve(pluginDir);
  const target = path.resolve(root, String(relativePath || ''));
  const rel = path.relative(root, target);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) {
    throw new Error(`invalid plugin asset path: ${relativePath}`);
  }
  if (!fs.existsSync(target)) {
    throw new Error(`plugin asset not found: ${relativePath}`);
  }
  return target;
}

function getCodeRoot() {
  return buildSystem.getProjectDir();
}

function readCodeTree(absDir, codeRoot) {
  return fs.readdirSync(absDir, { withFileTypes: true })
    .filter((entry) => !['out', '.git', 'node_modules'].includes(entry.name))
    .sort((a, b) => {
      if (a.isDirectory() && !b.isDirectory()) return -1;
      if (!a.isDirectory() && b.isDirectory()) return 1;
      return a.name.localeCompare(b.name, 'ja');
    })
    .map((entry) => {
      const fullPath = path.join(absDir, entry.name);
      const relPath = path.relative(codeRoot, fullPath).replace(/\\/g, '/');
      if (entry.isDirectory()) {
        return { type: 'directory', name: entry.name, path: relPath, children: readCodeTree(fullPath, codeRoot) };
      }
      return { type: 'file', name: entry.name, path: relPath, size: fs.statSync(fullPath).size };
    });
}

function resolveUnderProject(relativePath = '') {
  return resolveUnderRoot(getCodeRoot(), relativePath, 'project');
}

function ensureMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) return mainWindow;
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 620,
    backgroundColor: '#111318',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  mainWindow.on('closed', () => {
    mainWindow = null;
    if (!isQuitting && process.platform !== 'darwin') app.quit();
  });
  return mainWindow;
}

function openSetupWindow() {
  ensureMainWindow();
  mainWindow.webContents.send('plugin-log', { pluginId: 'setup', level: 'info', message: 'Setup パネルを開いてください。' });
  return { ok: true };
}

function findPceEmulatorCore(dataDir) {
  const coresDir = path.join(dataDir, 'cores');
  if (!fs.existsSync(coresDir)) return null;
  return fs.readdirSync(coresDir).find((fileName) => /^mednafen_pce.*-wasm\.data$/i.test(fileName)) || null;
}

function resolveEmulatorJsRuntime(emulatorJsDir) {
  const root = path.resolve(emulatorJsDir || '');
  const directLoader = path.join(root, 'loader.js');
  const nestedDataDir = path.join(root, 'data');
  const nestedLoader = path.join(nestedDataDir, 'loader.js');

  if (fs.existsSync(directLoader)) {
    return {
      rootDir: path.dirname(root),
      dataDir: root,
      loaderPath: directLoader,
      coreAsset: findPceEmulatorCore(root),
    };
  }
  if (fs.existsSync(nestedLoader)) {
    return {
      rootDir: root,
      dataDir: nestedDataDir,
      loaderPath: nestedLoader,
      coreAsset: findPceEmulatorCore(nestedDataDir),
    };
  }
  return { rootDir: root, dataDir: nestedDataDir, loaderPath: nestedLoader, coreAsset: null };
}

function makeTestPlayContext(options = {}) {
  const romPath = options.romPath || null;
  if (!romPath || !fs.existsSync(romPath)) {
    return {
      ok: false,
      error: 'ROM が未生成です。Build を成功させてから Test Play を実行してください。',
      needsBuild: true,
    };
  }

  const emulatorJsDir = setupManager.getEmulatorJsDir();
  if (!emulatorJsDir) {
    return {
      ok: false,
      error: 'EmulatorJS / mednafen_pce core is not configured. Setup で取得またはパス指定してください。',
      needsSetup: true,
    };
  }

  const runtime = resolveEmulatorJsRuntime(emulatorJsDir);
  if (!fs.existsSync(runtime.loaderPath)) {
    return {
      ok: false,
      error: `EmulatorJS loader.js が見つかりません: ${runtime.loaderPath}`,
      needsSetup: true,
    };
  }
  if (!runtime.coreAsset) {
    return {
      ok: false,
      error: `EmulatorJS mednafen_pce core が見つかりません: ${path.join(runtime.dataDir, 'cores')}`,
      needsSetup: true,
    };
  }

  const romStat = fs.statSync(romPath);
  return {
    ok: true,
    context: {
      romPath,
      romUrl: pathToFileURL(romPath).href,
      romMtimeMs: romStat.mtimeMs,
      romSize: romStat.size,
      gameId: `${path.basename(romPath)}-${romStat.mtimeMs}-${romStat.size}`,
      emulatorJsDir: runtime.rootDir,
      emulatorJsUrl: pathToFileURL(runtime.rootDir).href.replace(/\/?$/, '/'),
      emulatorJsDataDir: runtime.dataDir,
      emulatorJsDataUrl: pathToFileURL(runtime.dataDir).href.replace(/\/?$/, '/'),
      emulatorJsLoaderUrl: pathToFileURL(runtime.loaderPath).href,
      core: 'pce',
      coreAsset: runtime.coreAsset,
    },
  };
}

async function openWasmTestPlayWindow(options = {}) {
  const pluginId = String(options.pluginId || 'pce-standard-emulator');
  const contextResult = makeTestPlayContext(options);
  if (!contextResult.ok) return { opened: false, ...contextResult };
  currentTestPlayContext = contextResult.context;

  const htmlPath = resolvePluginAssetPath(pluginId, 'testplay.html');
  const preloadPath = resolvePluginAssetPath(pluginId, 'testplay-preload.js');

  if (testPlayWindow && !testPlayWindow.isDestroyed()) {
    testPlayWindow.loadFile(htmlPath);
    testPlayWindow.focus();
    return { opened: true, reused: true };
  }

  testPlayWindow = new BrowserWindow({
    width: 980,
    height: 740,
    title: 'PCE Test Play',
    backgroundColor: '#0f1117',
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  testPlayWindow.loadFile(htmlPath);
  testPlayWindow.on('closed', () => {
    testPlayWindow = null;
    currentTestPlayContext = null;
  });
  return { opened: true, reused: false };
}

function createTestPlayHostApi(pluginId) {
  return {
    openWasmWindow: (options = {}) => openWasmTestPlayWindow({ ...options, pluginId: options.pluginId || pluginId }),
    getEmulatorStatus: () => setupManager.getStatus().emulatorJs,
  };
}

async function invokePluginHookSafe(pluginId, hook, payload, context = {}) {
  const result = await pluginManager.invokeHook(pluginId, hook, payload, context);
  if (result && result.ok === false) {
    createPluginLogger(pluginId).error(result.error || `${hook} failed`);
  }
  return result;
}

async function runBuildFull(options = {}) {
  const projectDir = buildSystem.getProjectDir();
  const builderPluginId = resolvePluginForRole('builder');
  if (!builderPluginId) {
    return { success: false, error: '有効な Build プラグインが未設定です。' };
  }

  const pluginContext = {
    projectDir,
    assets: assetManager.listAssets(projectDir).assets,
    logger: createPluginLogger(builderPluginId),
  };
  await invokePluginHookSafe(builderPluginId, 'onBuildStart', { projectDir }, pluginContext);
  const result = await buildSystem.buildProject((text, level) => {
    sendToRenderer('build-log', { text, level });
    void pluginManager.invokeHook(builderPluginId, 'onBuildLog', { text, level }, pluginContext).catch(() => {});
  }, options);

  if (result.success) {
    await invokePluginHookSafe(builderPluginId, 'onBuildEnd', result, pluginContext);
  } else {
    await invokePluginHookSafe(builderPluginId, 'onBuildError', { error: result.error, result }, pluginContext);
  }
  sendToRenderer('build-end', result);
  return result;
}

function pickFile(options = {}) {
  const owner = mainWindow && !mainWindow.isDestroyed() ? mainWindow : undefined;
  return dialog.showOpenDialog(owner, {
    properties: options.properties || ['openFile'],
    filters: options.filters || [{ name: 'All Files', extensions: ['*'] }],
  }).then((result) => {
    if (result.canceled || result.filePaths.length === 0) return { canceled: true, filePath: null };
    return { canceled: false, filePath: result.filePaths[0], filePaths: result.filePaths };
  });
}

function registerIpcHandlers() {
  ipcMain.handle('app:getInfo', async () => ({
    name: 'PCE Game Editor',
    version: packageJson.version,
    dataDir,
  }));

  ipcMain.handle('app:quit', async () => {
    isQuitting = true;
    app.quit();
    return { ok: true };
  });

  ipcMain.handle('project:getStartupState', async () => {
    const ensured = buildSystem.ensureDefaultProject();
    return { ok: true, ...ensured, current: buildSystem.getProjectInfo(), list: buildSystem.listProjects() };
  });
  ipcMain.handle('project:getCurrent', async () => ({ ok: true, ...buildSystem.getProjectInfo() }));
  ipcMain.handle('project:list', async () => ({ ok: true, ...buildSystem.listProjects() }));
  ipcMain.handle('project:createSample', async (_event, payload = {}) => {
    try {
      const result = buildSystem.createProjectInRoot(payload.projectName || undefined, payload.config || {}, {
        templateId: payload.templateId || 'template_pce_sample',
      });
      return { ok: true, ...result };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('project:open', async (_event, payload = {}) => {
    try {
      return { ok: true, ...buildSystem.openProject(payload.projectDir) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('project:getConfig', async () => ({ ok: true, config: buildSystem.loadProjectConfig() }));
  ipcMain.handle('project:saveConfig', async (_event, patch = {}) => {
    try {
      return { ok: true, config: buildSystem.saveProjectConfig(patch) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  ipcMain.handle('setup:getStatus', async () => ({ ok: true, ...setupManager.getStatus() }));
  ipcMain.handle('setup:getCatalog', async () => setupManager.getDownloadCatalog());
  ipcMain.handle('setup:listVersions', async (_event, { kind } = {}) => {
    try {
      return await setupManager.listToolVersions(kind);
    } catch (err) {
      return { ok: false, kind, errors: [String(err?.message || err)], versions: [] };
    }
  });
  ipcMain.handle('setup:setToolPath', async (_event, { kind, value } = {}) => {
    try {
      const settings = setupManager.setToolPath(kind, value);
      return { ok: true, settings, status: setupManager.getStatus() };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('setup:downloadTool', async (_event, payload = {}) => setupManager.downloadTool(payload, (progress) => {
    sendToRenderer('setup-progress', progress);
  }));

  ipcMain.handle('assets:list', async () => {
    try {
      return { ok: true, ...assetManager.listAssets(buildSystem.getProjectDir()) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('assets:upsert', async (_event, asset = {}) => {
    try {
      return { ok: true, document: assetManager.upsertAsset(buildSystem.getProjectDir(), asset) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('assets:delete', async (_event, { id } = {}) => {
    try {
      return { ok: true, document: assetManager.deleteAsset(buildSystem.getProjectDir(), id) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  ipcMain.handle('codefs:getRoot', async () => ({ ok: true, root: getCodeRoot() }));
  ipcMain.handle('codefs:list', async (_event, payload = {}) => {
    try {
      const { root, absPath, relativePath } = resolveUnderProject(payload.path || '');
      if (!fs.existsSync(absPath) || !fs.statSync(absPath).isDirectory()) {
        return { ok: false, error: 'directory path is required' };
      }
      return { ok: true, root, path: relativePath, entries: readCodeTree(absPath, root) };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('codefs:read', async (_event, payload = {}) => {
    try {
      const { absPath } = resolveUnderProject(payload.path || '');
      if (!fs.existsSync(absPath) || !fs.statSync(absPath).isFile()) {
        return { ok: false, error: 'file path is required' };
      }
      return { ok: true, path: payload.path || '', content: fs.readFileSync(absPath, 'utf-8'), encoding: 'utf-8' };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('codefs:write', async (_event, payload = {}) => {
    try {
      const { absPath } = resolveUnderProject(payload.path || '');
      fs.mkdirSync(path.dirname(absPath), { recursive: true });
      fs.writeFileSync(absPath, String(payload.content ?? ''), 'utf-8');
      return { ok: true, path: payload.path || '' };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('codefs:create', async (_event, payload = {}) => {
    try {
      const { absPath } = resolveUnderProject(payload.path || '');
      if (fs.existsSync(absPath)) return { ok: false, error: 'already exists' };
      if (payload.type === 'directory') fs.mkdirSync(absPath, { recursive: true });
      else {
        fs.mkdirSync(path.dirname(absPath), { recursive: true });
        fs.writeFileSync(absPath, String(payload.content ?? ''), 'utf-8');
      }
      return { ok: true, path: payload.path || '' };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('codefs:delete', async (_event, payload = {}) => {
    try {
      const { root, absPath } = resolveUnderProject(payload.path || '');
      if (absPath === root) return { ok: false, error: 'project root は削除できません' };
      fs.rmSync(absPath, { recursive: true, force: true });
      return { ok: true, path: payload.path || '' };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });
  ipcMain.handle('codefs:rename', async (_event, payload = {}) => {
    try {
      const from = resolveUnderProject(payload.fromPath || '');
      const to = resolveUnderProject(payload.toPath || '');
      if (from.absPath === from.root) return { ok: false, error: 'project root はリネームできません' };
      if (fs.existsSync(to.absPath)) return { ok: false, error: 'already exists' };
      fs.mkdirSync(path.dirname(to.absPath), { recursive: true });
      fs.renameSync(from.absPath, to.absPath);
      return { ok: true, fromPath: payload.fromPath, toPath: payload.toPath };
    } catch (err) {
      return { ok: false, error: String(err?.message || err) };
    }
  });

  ipcMain.handle('plugins:list', async () => pluginManager.listPlugins());
  ipcMain.handle('plugins:getRendererAssets', async (_event, { id } = {}) => pluginManager.getRendererAssets(id));
  ipcMain.handle('plugins:setEnabled', async (_event, { id, enabled } = {}) => pluginManager.setEnabledWithDependencies(id, enabled));
  ipcMain.handle('plugins:openFolder', async () => {
    const dir = pluginManager.getUserPluginsDir();
    fs.mkdirSync(dir, { recursive: true });
    const error = await shell.openPath(dir);
    return error ? { ok: false, error } : { ok: true, path: dir };
  });
  ipcMain.handle('plugins:invokeHook', async (_event, { id, hook, payload } = {}) => {
    return pluginManager.invokeRendererHook(id, hook, payload || {}, {
      projectDir: buildSystem.getProjectDir(),
      logger: createPluginLogger(id),
    });
  });
  ipcMain.handle('plugins:getRoles', async () => ({ ok: true, roles: buildSystem.getPluginRoles() }));
  ipcMain.handle('plugins:getRole', async (_event, { roleId } = {}) => ({ ok: true, roleId, id: buildSystem.getPluginRole(roleId) }));
  ipcMain.handle('plugins:setRole', async (_event, { roleId, id } = {}) => {
    const result = pluginManager.setExclusiveRoleSelection(roleId, id || null);
    if (!result.ok) return result;
    buildSystem.setPluginRole(roleId, id || null);
    return result;
  });

  ipcMain.handle('build:run', async (_event, options = {}) => runBuildFull(options));
  ipcMain.handle('build:getRomPath', async () => ({ ok: true, romPath: buildSystem.getLastRomPath() }));
  ipcMain.handle('testplay:open', async (_event, { romPath } = {}) => {
    const emulatorPluginId = resolvePluginForRole('testplay');
    if (!emulatorPluginId) return { ok: false, error: '有効な Test Play プラグインが未設定です。' };
    const result = await pluginManager.invokeHook(emulatorPluginId, 'onTestPlay', {
      romPath: romPath || buildSystem.getLastRomPath(),
    }, {
      projectDir: buildSystem.getProjectDir(),
      testPlay: createTestPlayHostApi(emulatorPluginId),
      logger: createPluginLogger(emulatorPluginId),
    });
    return result?.ok === false ? result : { ok: true, ...result };
  });
  ipcMain.handle('testplay:getContext', async () => ({ ok: true, context: currentTestPlayContext }));

  ipcMain.handle('window:openSetup', async () => openSetupWindow());
  ipcMain.handle('fs:openPath', async (_event, { targetPath } = {}) => {
    if (!targetPath || !fs.existsSync(targetPath)) return { ok: false, error: 'path not found' };
    const error = await shell.openPath(targetPath);
    return error ? { ok: false, error } : { ok: true, path: targetPath };
  });
  ipcMain.handle('dialog:pickFile', async (_event, options = {}) => pickFile(options));
}

function main() {
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return;
  }
  registerIpcHandlers();
  app.whenReady().then(() => {
    Menu.setApplicationMenu(Menu.buildFromTemplate([]));
    buildSystem.ensureDefaultProject();
    setupManager.ensureEmulatorPlaceholder();
    ensureMainWindow();
  });
  app.on('activate', () => ensureMainWindow());
  app.on('before-quit', () => { isQuitting = true; });
}

function shouldAutoStart({
  versions = process.versions,
  mainModule = require.main,
  currentModule = module,
} = {}) {
  return Boolean(versions?.electron) || mainModule === currentModule;
}

if (shouldAutoStart()) {
  main();
}

module.exports = {
  createTestPlayHostApi,
  dataDir,
  findPceEmulatorCore,
  main,
  makeTestPlayContext,
  openWasmTestPlayWindow,
  registerIpcHandlers,
  resolveEmulatorJsRuntime,
  resolvePluginAssetPath,
  runBuildFull,
  shouldAutoStart,
};
