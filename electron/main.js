const path = require('path');
const fs = require('fs');
const net = require('net');
const { shell } = require('electron');
const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron');
const { spawn } = require('child_process');
const electronPackageJson = require('./package.json');

// ── アプリビルドメタ読み込み ──────────────────────────────────────────────
// npm start / prepare:dist 時に scripts/inject-build-meta.js が生成する。
function readAppBuildMeta() {
  const metaPath = path.join(__dirname, 'build-meta.json');
  try {
    if (fs.existsSync(metaPath)) {
      return JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
    }
  } catch (_) {}
  return { buildNumber: 'dev', buildAt: null };
}

const appBuildMeta = readAppBuildMeta();

// ── Portable mode detection ────────────────────────────────────────────────
// Must run before any app.getPath() call (including those inside require'd modules).
// Packaged: place a file named "portable" next to the .exe / .app to activate.
// Dev:      place a file named ".portable" in the electron/ source directory.
(function applyPortableMode() {
  let markerExists = false;
  let dataDir;

  if (app.isPackaged) {
    const exeDir = path.dirname(app.getPath('exe'));
    markerExists = fs.existsSync(path.join(exeDir, 'portable'));
    dataDir = path.join(exeDir, 'data');
  } else {
    markerExists = fs.existsSync(path.join(__dirname, '.portable'));
    dataDir = path.join(__dirname, 'data');
  }

  if (markerExists) {
    app.setPath('userData', dataDir);
    app.setPath('logs', path.join(dataDir, 'logs'));
  }
})();

const setupManager = require('./setup-manager');
const buildSystem = require('./build-system');
const rescompManager = require('./rescomp-manager');
const pluginManager = require('./plugin-manager');

let mainWindow = null;
let debugWindow = null;
let setupWindow = null;
let testPlayWindow = null;
let testPlaySettingsWindow = null;
let apiServerProcess = null;
let apiServerPort = null;

function getRepoRoot() {
  return path.resolve(__dirname, '..');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    backgroundColor: '#101217',
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
  });
}

function openDebugWindow(options = {}) {
  const mode = options.mode || 'api';
  const port = options.apiPort || apiServerPort || 8080;

  if (debugWindow && !debugWindow.isDestroyed()) {
    debugWindow.focus();
    return { opened: true, reused: true };
  }

  debugWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    backgroundColor: '#101217',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'debug-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const debugFile = mode === 'wasm'
    ? path.join(__dirname, 'renderer', 'debug-wasm.html')
    : path.join(getRepoRoot(), 'frontend', 'debug.html');
  let didFinishLoad = false;

  if (!fs.existsSync(debugFile)) {
    const html = `
      <html><body style="background:#101217;color:#e6edf3;font-family:monospace;padding:16px">
      <h2>Debug Window Load Failed</h2>
      <p>electron debug page was not found.</p>
      <p>Path: ${debugFile}</p>
      </body></html>
    `;
    debugWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    return { opened: true, reused: false, missingFile: true };
  }

  debugWindow.webContents.on('did-finish-load', () => {
    didFinishLoad = true;
    const script = `
      (function() {
        var params = new URLSearchParams(window.location.search);
        params.set('mode', ${JSON.stringify(mode)});
        params.set('apiPort', ${JSON.stringify(String(port))});
        history.replaceState(null, '', window.location.pathname + '?' + params.toString());

        var input = document.getElementById('apiBase');
        if (input) {
          input.value = 'http://127.0.0.1:${port}';
        }
        var refresh = document.getElementById('btnRefresh');
        if (refresh) {
          refresh.click();
        }
      })();
    `;
    debugWindow.webContents.executeJavaScript(script).catch(() => {});
  });

  debugWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (didFinishLoad || !isMainFrame) {
      return;
    }
    const html = `
      <html><body style="background:#101217;color:#e6edf3;font-family:monospace;padding:16px">
      <h2>Debug Window Load Failed</h2>
      <p>URL: ${validatedURL || debugFile}</p>
      <p>Code: ${errorCode}</p>
      <p>Message: ${errorDescription}</p>
      <p>File exists: ${fs.existsSync(debugFile)}</p>
      </body></html>
    `;
    debugWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  });

  debugWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  debugWindow.loadFile(debugFile);

  debugWindow.on('closed', () => {
    debugWindow = null;
  });

  return { opened: true, reused: false };
}

function sendToRenderer(channel, payload) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  mainWindow.webContents.send(channel, payload);
}

function sendToSetupWindow(channel, payload) {
  if (!setupWindow || setupWindow.isDestroyed()) {
    return;
  }
  setupWindow.webContents.send(channel, payload);
}

function broadcastTestPlaySettings(settings) {
  [testPlayWindow, debugWindow, testPlaySettingsWindow].forEach((win) => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('testplay:settings-changed', settings);
    }
  });
}

function collectProjectAssets(projectDir) {
  let allAssets = [];
  try {
    const defs = rescompManager.listResDefinitions(projectDir);
    (defs.files || []).forEach((f) => {
      (f.entries || []).forEach((e) => allAssets.push(e));
    });
  } catch (_) {}
  return allAssets;
}

function createPluginLogger(pluginId) {
  const emit = (level, message) => {
    const payload = {
      pluginId,
      source: `plugin:${pluginId}`,
      level: level || 'info',
      text: String(message || ''),
    };
    sendToRenderer('plugin-log', payload);
    sendToRenderer('build-log', {
      text: `[${pluginId}] ${payload.text}`,
      level: payload.level,
    });
  };

  return {
    info: (message) => emit('info', message),
    warn: (message) => emit('warn', message),
    error: (message) => emit('error', message),
    debug: (message) => emit('debug', message),
    log: (message) => emit('info', message),
  };
}

async function invokePluginHookSafe(pluginId, hookName, payload, context = {}) {
  if (!pluginId) return { ok: true, skipped: true };
  const result = await pluginManager.invokeHook(pluginId, hookName, payload, context);
  if (!result.ok) {
    const msg = `[Plugin:${pluginId}] hook ${hookName} failed: ${result.error || 'unknown error'}`;
    sendToRenderer('build-log', { text: msg, level: 'error' });
  }
  return result;
}

function getProjectSrcRoot() {
  return path.join(buildSystem.getProjectDir(), 'src');
}

function resolveUnderSrc(relativePath = '') {
  const srcRoot = path.resolve(getProjectSrcRoot());
  const cleaned = String(relativePath || '').replace(/^[/\\]+/, '');
  const absPath = path.resolve(srcRoot, cleaned);
  if (absPath !== srcRoot && !absPath.startsWith(`${srcRoot}${path.sep}`)) {
    throw new Error(`src 配下のみアクセス可能です: ${relativePath}`);
  }
  return { srcRoot, absPath };
}

function readSrcTree(absDir, srcRoot) {
  const entries = fs.readdirSync(absDir, { withFileTypes: true })
    .sort((a, b) => {
      if (a.isDirectory() && !b.isDirectory()) return -1;
      if (!a.isDirectory() && b.isDirectory()) return 1;
      return a.name.localeCompare(b.name, 'ja');
    });

  return entries.map((entry) => {
    const fullPath = path.join(absDir, entry.name);
    const relPath = path.relative(srcRoot, fullPath).replace(/\\/g, '/');
    if (entry.isDirectory()) {
      return {
        type: 'directory',
        name: entry.name,
        path: relPath,
        children: readSrcTree(fullPath, srcRoot),
      };
    }
    return {
      type: 'file',
      name: entry.name,
      path: relPath,
      size: fs.statSync(fullPath).size,
    };
  });
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Setup',
          click: () => {
            sendToRenderer('menu:openSetup');
          },
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [{ role: 'reload' }, { role: 'forceReload' }, { role: 'toggleDevTools' }],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About MD Game Editor',
          click: () => {
            sendToRenderer('menu:openAbout');
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function readEmbeddedWasmInfo() {
  const pkgPath = path.join(__dirname, 'pkg', 'package.json');
  const buildMetaPath = path.join(__dirname, 'pkg', 'build_meta.js');
  let packageVersion = 'unknown';
  let buildVersion = 'unknown';

  try {
    if (fs.existsSync(pkgPath)) {
      const pkgJson = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
      packageVersion = String(pkgJson.version || 'unknown');
    }
  } catch (_err) {
  }

  try {
    if (fs.existsSync(buildMetaPath)) {
      const meta = fs.readFileSync(buildMetaPath, 'utf-8');
      const m = meta.match(/__BUILD_META_VERSION\s*=\s*"([^"]+)"/);
      if (m && m[1]) {
        buildVersion = m[1];
      }
    }
  } catch (_err) {
  }

  return {
    packageVersion,
    buildVersion,
  };
}

function stopApiServer() {
  if (!apiServerProcess) {
    return Promise.resolve(false);
  }

  const proc = apiServerProcess;

  const waitForExit = new Promise((resolve) => {
    proc.once('exit', () => resolve(true));
  });

  if (process.platform === 'win32') {
    const killer = spawn('taskkill', ['/pid', String(proc.pid), '/t', '/f'], {
      windowsHide: true,
      stdio: 'ignore',
    });
    killer.on('exit', () => {});
  } else {
    try {
      process.kill(-proc.pid, 'SIGTERM');
    } catch (_err) {
      try {
        proc.kill('SIGTERM');
      } catch (__err) {
      }
    }

    setTimeout(() => {
      try {
        process.kill(-proc.pid, 'SIGKILL');
      } catch (_err) {
      }
    }, 1500);
  }

  apiServerProcess = null;
  apiServerPort = null;
  return waitForExit;
}

function resolveApiLaunch() {
  const repoRoot = getRepoRoot();
  const isWin = process.platform === 'win32';

  if (app.isPackaged) {
    const binName = isWin ? 'md-api.exe' : 'md-api';
    const packagedBin = path.join(process.resourcesPath, 'bin', binName);
    if (!fs.existsSync(packagedBin)) {
      throw new Error(`md-api binary not found: ${packagedBin}`);
    }

    return {
      command: packagedBin,
      args: [],
      cwd: process.resourcesPath,
    };
  }

  return {
    command: isWin ? 'cargo.exe' : 'cargo',
    args: ['run', '-p', 'md-api'],
    cwd: repoRoot,
  };
}

function canBindPort(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

async function findAvailablePort(preferredPort, maxOffset = 20) {
  for (let offset = 0; offset <= maxOffset; offset += 1) {
    const port = preferredPort + offset;
    if (await canBindPort(port)) {
      return port;
    }
  }
  return null;
}

async function startApiServer(port) {
  if (apiServerProcess) {
    return { alreadyRunning: true };
  }

  const preferredPort = port || 8080;
  const launchPort = await findAvailablePort(preferredPort);
  if (launchPort == null) {
    throw new Error(`no available port found from ${preferredPort} to ${preferredPort + 20}`);
  }

  const launch = resolveApiLaunch();
  const env = { ...process.env, MD_API_PORT: String(launchPort) };

  apiServerProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    env,
    detached: process.platform !== 'win32',
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  apiServerPort = launchPort;

  apiServerProcess.stdout.on('data', (chunk) => {
    sendToRenderer('api-log', { level: 'info', message: chunk.toString() });
  });

  apiServerProcess.stderr.on('data', (chunk) => {
    sendToRenderer('api-log', { level: 'error', message: chunk.toString() });
  });

  apiServerProcess.on('exit', (code, signal) => {
    sendToRenderer('api-exit', { code, signal });
    apiServerProcess = null;
  });

  return {
    started: true,
    port: launchPort,
    fallbackUsed: launchPort !== preferredPort,
    requestedPort: preferredPort,
  };
}

ipcMain.handle('dialog:openRomFile', async () => {
  if (!mainWindow) {
    return { canceled: true, filePath: null };
  }

  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Mega Drive ROM', extensions: ['bin', 'md', 'gen', 'smd', 'sms', 'zip'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true, filePath: null };
  }

  return { canceled: false, filePath: result.filePaths[0] };
});

ipcMain.handle('fs:readRomFile', async (_event, filePath) => {
  const data = fs.readFileSync(filePath);
  return new Uint8Array(data);
});

ipcMain.handle('fs:openPathInExplorer', async (_event, targetPath, options = {}) => {
  try {
    if (!targetPath) {
      return { ok: false, error: 'path is empty' };
    }
    const normalized = path.resolve(targetPath);
    const finalTarget = options.parentOnly ? path.dirname(normalized) : normalized;
    if (!fs.existsSync(finalTarget)) {
      return { ok: false, error: `path not found: ${finalTarget}` };
    }
    const error = await shell.openPath(finalTarget);
    if (error) {
      return { ok: false, error };
    }
    return { ok: true, path: finalTarget };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('fs:saveRomAs', async (_event, sourcePath) => {
  try {
    if (!sourcePath || !fs.existsSync(sourcePath)) {
      return { ok: false, error: 'source ROM not found' };
    }
    const owner = (mainWindow && !mainWindow.isDestroyed()) ? mainWindow : undefined;
    const suggestedName = path.basename(sourcePath);
    const result = await dialog.showSaveDialog(owner, {
      title: 'ビルド済み ROM を保存',
      defaultPath: suggestedName,
      filters: [
        { name: 'Mega Drive ROM', extensions: ['bin', 'md', 'gen', 'smd', 'sms'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    if (result.canceled || !result.filePath) {
      return { ok: false, canceled: true };
    }
    fs.copyFileSync(sourcePath, result.filePath);
    return { ok: true, path: result.filePath };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:getRoot', async () => {
  try {
    const srcRoot = getProjectSrcRoot();
    fs.mkdirSync(srcRoot, { recursive: true });
    return { ok: true, root: srcRoot };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:list', async (_event, payload) => {
  try {
    const { srcRoot, absPath } = resolveUnderSrc(payload?.path || '');
    if (!fs.existsSync(absPath)) {
      return { ok: false, error: `path not found: ${payload?.path || ''}` };
    }
    const stat = fs.statSync(absPath);
    if (!stat.isDirectory()) {
      return { ok: false, error: 'directory path is required' };
    }
    return {
      ok: true,
      root: srcRoot,
      path: path.relative(srcRoot, absPath).replace(/\\/g, '/'),
      entries: readSrcTree(absPath, srcRoot),
    };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:read', async (_event, payload) => {
  try {
    const { absPath } = resolveUnderSrc(payload?.path || '');
    if (!fs.existsSync(absPath)) {
      return { ok: false, error: `file not found: ${payload?.path || ''}` };
    }
    if (!fs.statSync(absPath).isFile()) {
      return { ok: false, error: 'file path is required' };
    }
    return { ok: true, content: fs.readFileSync(absPath, 'utf-8') };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:write', async (_event, payload) => {
  try {
    const { absPath } = resolveUnderSrc(payload?.path || '');
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
    fs.writeFileSync(absPath, String(payload?.content ?? ''), 'utf-8');
    return { ok: true, path: payload?.path || '' };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:create', async (_event, payload) => {
  try {
    const targetType = String(payload?.type || 'file');
    const { absPath } = resolveUnderSrc(payload?.path || '');
    if (fs.existsSync(absPath)) {
      return { ok: false, error: `already exists: ${payload?.path || ''}` };
    }

    if (targetType === 'directory') {
      fs.mkdirSync(absPath, { recursive: true });
    } else {
      fs.mkdirSync(path.dirname(absPath), { recursive: true });
      fs.writeFileSync(absPath, String(payload?.content ?? ''), 'utf-8');
    }
    return { ok: true, path: payload?.path || '', type: targetType };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:delete', async (_event, payload) => {
  try {
    const { absPath, srcRoot } = resolveUnderSrc(payload?.path || '');
    if (absPath === srcRoot) {
      return { ok: false, error: 'src root は削除できません' };
    }
    if (!fs.existsSync(absPath)) {
      return { ok: false, error: `not found: ${payload?.path || ''}` };
    }
    fs.rmSync(absPath, { recursive: true, force: true });
    return { ok: true, path: payload?.path || '' };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:listDefinitions', async () => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const data = rescompManager.listResDefinitions(projectDir);
    return { ok: true, ...data };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:createFile', async (_event, relativePath) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.createResFile(projectDir, relativePath);
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:reorderEntries', async (_event, payload) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.reorderResEntries(projectDir, payload?.file, payload?.orderedLineNumbers || []);
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:addEntry', async (_event, payload) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.addResEntry(projectDir, payload?.file, payload?.entry || {});
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:updateEntry', async (_event, payload) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.updateResEntry(projectDir, payload?.file, payload?.lineNumber, payload?.entry || {});
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:deleteEntry', async (_event, payload) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.deleteResEntry(projectDir, payload?.file, payload?.lineNumber);
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:openDirectory', async () => {
  try {
    const resRoot = path.join(buildSystem.getProjectDir(), 'res');
    fs.mkdirSync(resRoot, { recursive: true });
    const error = await shell.openPath(resRoot);
    if (error) {
      return { ok: false, error };
    }
    return { ok: true, path: resRoot };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:pickAssetSource', async () => {
  const owner = (mainWindow && !mainWindow.isDestroyed()) ? mainWindow : undefined;
  const result = await dialog.showOpenDialog(owner, {
    properties: ['openFile'],
    filters: [
      { name: 'Assets', extensions: ['png', 'bmp', 'pal', 'tsx', 'tmx', 'vgm', 'xgm', 'wav'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const sourcePath = result.filePaths[0];
  return {
    canceled: false,
    sourcePath,
    fileName: path.basename(sourcePath),
    ext: path.extname(sourcePath).toLowerCase(),
  };
});

ipcMain.handle('res:readFileAsDataUrl', async (_event, sourcePath) => {
  try {
    if (!sourcePath || !fs.existsSync(sourcePath)) {
      return { ok: false, error: 'source file not found' };
    }
    const ext = path.extname(sourcePath).toLowerCase();
    const mime = ext === '.png'
      ? 'image/png'
      : ext === '.bmp'
        ? 'image/bmp'
        : 'application/octet-stream';
    const data = fs.readFileSync(sourcePath).toString('base64');
    return { ok: true, dataUrl: `data:${mime};base64,${data}` };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('res:writeAssetFile', async (_event, payload) => {
  try {
    const projectDir = buildSystem.getProjectDir();
    const result = rescompManager.writeAssetIntoRes(projectDir, payload || {});
    return { ok: true, ...result };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('api:startServer', async (_event, options) => {
  return startApiServer(options?.port ?? 8080);
});

ipcMain.handle('api:stopServer', async () => {
  return { stopped: await stopApiServer() };
});

ipcMain.handle('api:isRunning', async () => {
  return { running: !!apiServerProcess, port: apiServerPort };
});

ipcMain.handle('window:openDebug', async (_event, options) => {
  return openDebugWindow(options || {});
});

ipcMain.handle('debug:getWasmSnapshot', async (_event, options) => {
  // testPlayWindow (または mainWindow) から debug bridge を読む
  const targetWin = (testPlayWindow && !testPlayWindow.isDestroyed()) ? testPlayWindow
    : (mainWindow && !mainWindow.isDestroyed()) ? mainWindow
    : null;

  if (!targetWin) {
    return { ok: false, error: 'no available window' };
  }

  const palette = Number(options?.palette ?? 0);
  const script = `
    (async function () {
      if (!window.__mdDebugBridge || !window.__mdDebugBridge.getWasmDebugSnapshot) {
        return { ok: false, error: 'WASM debug bridge is not ready' };
      }
      return await window.__mdDebugBridge.getWasmDebugSnapshot(${Number.isFinite(palette) ? palette : 0});
    })();
  `;

  try {
    const result = await targetWin.webContents.executeJavaScript(script, true);
    return result;
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
  }
});

// ---- Plugin handlers ----
ipcMain.handle('plugins:list', () => {
  return pluginManager.listPlugins();
});

ipcMain.handle('plugins:setEnabled', (_event, { id, enabled }) => {
  const result = pluginManager.setEnabledWithDependencies(id, Boolean(enabled));
  if (!result?.ok) {
    return { ok: false, error: result?.error || 'plugin enable failed' };
  }
  return result;
});

ipcMain.handle('plugins:openFolder', async () => {
  const pluginsDir = path.join(__dirname, 'plugins');
  try {
    if (!fs.existsSync(pluginsDir)) fs.mkdirSync(pluginsDir, { recursive: true });
    const error = await shell.openPath(pluginsDir);
    return error ? { ok: false, error } : { ok: true, path: pluginsDir };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('plugins:runGenerator', async (_event, { id }) => {
  const projectDir = buildSystem.getProjectDir();
  const allAssets = collectProjectAssets(projectDir);
  const genResult = await pluginManager.runGenerator(id, allAssets, {
    projectDir,
    logger: createPluginLogger(id),
  });
  if (!genResult.ok) return genResult;

  // src/main.c に書き込む
  const srcPath = path.join(projectDir, 'src', 'main.c');
  try {
    fs.mkdirSync(path.dirname(srcPath), { recursive: true });
    fs.writeFileSync(srcPath, genResult.sourceCode, 'utf-8');
  } catch (err) {
    return { ok: false, error: `main.c の書き込みに失敗: ${err.message}` };
  }
  return { ok: true, srcPath };
});

ipcMain.handle('testplay:getSettings', async () => {
  return setupManager.getTestPlaySettings();
});

ipcMain.handle('testplay:getDefaultSettings', async () => {
  return setupManager.getDefaultTestPlaySettings();
});

ipcMain.handle('testplay:saveSettings', async (_event, settings) => {
  const saved = setupManager.saveTestPlaySettings(settings || {});
  broadcastTestPlaySettings(saved);
  return saved;
});

ipcMain.handle('window:openTestPlaySettings', async () => {
  if (testPlaySettingsWindow && !testPlaySettingsWindow.isDestroyed()) {
    testPlaySettingsWindow.focus();
    return { opened: true, reused: true };
  }
  testPlaySettingsWindow = new BrowserWindow({
    width: 840,
    height: 760,
    title: 'Test Play Settings - MD Game Editor',
    backgroundColor: '#0f1117',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'testplay-settings-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  testPlaySettingsWindow.loadFile(path.join(__dirname, 'renderer', 'testplay-settings.html'));
  testPlaySettingsWindow.on('closed', () => { testPlaySettingsWindow = null; });
  return { opened: true, reused: false };
});

// ---- Setup window ----
ipcMain.handle('window:openSetup', async () => {
  if (setupWindow && !setupWindow.isDestroyed()) {
    setupWindow.focus();
    return { opened: true, reused: true };
  }
  setupWindow = new BrowserWindow({
    width: 720,
    height: 640,
    title: 'Setup - MD Game Editor',
    backgroundColor: '#0f1117',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'setup-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  setupWindow.loadFile(path.join(__dirname, 'renderer', 'setup.html'));
  setupWindow.on('closed', () => { setupWindow = null; });
  return { opened: true, reused: false };
});

ipcMain.handle('setup:getStatus', async () => {
  return setupManager.getStatus();
});

ipcMain.handle('setup:listSgdkVersions', async () => {
  return setupManager.listSgdkReleases(30);
});

ipcMain.handle('setup:downloadSgdk', async (_event, tag) => {
  return setupManager.downloadSgdk(tag, (progress) => {
    sendToSetupWindow('setup-progress', progress);
  });
});

ipcMain.handle('setup:downloadJava', async () => {
  return setupManager.downloadJava((progress) => {
    sendToSetupWindow('setup-progress', progress);
  });
});

ipcMain.handle('setup:setSgdkPath', async (_event, p) => {
  return setupManager.setSgdkPath(p);
});

ipcMain.handle('setup:listMarsdevVersions', async () => {
  return setupManager.listMarsdevReleases(30);
});

ipcMain.handle('setup:downloadMarsdev', async (_event, tag) => {
  return setupManager.downloadMarsdev(tag, (progress) => {
    sendToSetupWindow('setup-progress', progress);
  });
});

ipcMain.handle('setup:setMarsdevPath', async (_event, p) => {
  return setupManager.setMarsdevPath(p);
});

// ---- Test play window ----
ipcMain.handle('window:openTestPlay', async (_event, romPath) => {
  let emulatorPluginId = buildSystem.getEmulatorPlugin();
  if (!emulatorPluginId) {
    const fallback = pluginManager.listPlugins().find(
      (p) => p.enabled && Array.isArray(p.pluginTypes) && p.pluginTypes.includes('emulator'),
    );
    if (fallback) {
      emulatorPluginId = fallback.id;
      try { buildSystem.setEmulatorPlugin(emulatorPluginId); } catch (_) {}
    }
  }
  if (!emulatorPluginId) {
    return { opened: false, error: '有効な Emulator プラグインが未設定です' };
  }
  if (!pluginManager.isPluginEnabled(emulatorPluginId)) {
    return { opened: false, error: `Emulator プラグイン "${emulatorPluginId}" は無効です` };
  }
  const emulatorMeta = pluginManager.listPlugins().find((p) => p.id === emulatorPluginId);
  const isEmulatorType = Boolean(
    emulatorMeta
    && Array.isArray(emulatorMeta.pluginTypes)
    && emulatorMeta.pluginTypes.includes('emulator'),
  );
  if (!isEmulatorType) {
    return { opened: false, error: `Emulator プラグイン "${emulatorPluginId}" は emulator タイプではありません` };
  }

  if (emulatorPluginId) {
    const hookResult = await invokePluginHookSafe(
      emulatorPluginId,
      'onTestPlay',
      {
        romPath: romPath || null,
        projectDir: buildSystem.getProjectDir(),
      },
      {
        projectDir: buildSystem.getProjectDir(),
        logger: createPluginLogger(emulatorPluginId),
      }
    );

    if (hookResult.ok && hookResult.result && hookResult.result.handled) {
      return { opened: true, reused: false, handledByPlugin: emulatorPluginId };
    }
    if (!hookResult.ok) {
      return { opened: false, error: hookResult.error || 'Emulator フック実行に失敗しました' };
    }
  }

  if (testPlayWindow && !testPlayWindow.isDestroyed()) {
    testPlayWindow.focus();
    return { opened: true, reused: true };
  }
  testPlayWindow = new BrowserWindow({
    width: 800,
    height: 720,
    title: 'Test Play - MD Game Editor',
    backgroundColor: '#0f1117',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'testplay-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  const romQuery = romPath ? `?romPath=${encodeURIComponent(romPath)}` : '';
  testPlayWindow.loadFile(path.join(__dirname, 'renderer', 'testplay.html'), { search: romQuery });
  testPlayWindow.on('closed', () => { testPlayWindow = null; });
  return { opened: true, reused: false };
});

// ---- Build IPC ----
ipcMain.handle('build:generateProject', async (_event, sourceCode, config) => {
  try {
    const result = await buildSystem.generateProject(sourceCode, config);
    return { ok: true, projectDir: result.projectDir };
  } catch (err) {
    return { ok: false, error: err.message || String(err) };
  }
});

// src/main.c を上書きせずプロジェクト構造だけ整備する (プラグインビルド用)
ipcMain.handle('build:generateStructureOnly', async (_event, config) => {
  try {
    const result = buildSystem.generateProjectStructureOnly(config);
    return { ok: true, projectDir: result.projectDir };
  } catch (err) {
    return { ok: false, error: err.message || String(err) };
  }
});

ipcMain.handle('build:run', async () => {
  try {
    const toolchainPath = setupManager.getToolchainDir();
    const javaPath = setupManager.getJavaExePath();
    const projectDir = buildSystem.getProjectDir();
    let builderPluginId = buildSystem.getBuilderPlugin();
    if (!toolchainPath) {
      return { success: false, error: 'ツールチェーンが設定されていません。Setup を実行してください。' };
    }
    // project.json に未保存の場合、有効な build プラグインをフォールバック検索
    if (!builderPluginId) {
      const fallback = pluginManager.listPlugins().find(
        (p) => p.enabled && Array.isArray(p.pluginTypes) && p.pluginTypes.includes('build'),
      );
      if (fallback) {
        builderPluginId = fallback.id;
        try { buildSystem.setBuilderPlugin(builderPluginId); } catch (_) {}
      }
    }
    if (!builderPluginId) {
      return { success: false, error: '有効な Build プラグインが未設定です。Plugins 画面で有効化してください。' };
    }
    if (!pluginManager.isPluginEnabled(builderPluginId)) {
      return { success: false, error: `Build プラグイン "${builderPluginId}" は無効です` };
    }
    const builderMeta = pluginManager.listPlugins().find((p) => p.id === builderPluginId);
    const builderIsBuild = Boolean(
      builderMeta
      && Array.isArray(builderMeta.pluginTypes)
      && builderMeta.pluginTypes.includes('build'),
    );
    if (!builderIsBuild) {
      return { success: false, error: `Build プラグイン "${builderPluginId}" は build タイプではありません` };
    }

    const pluginContext = {
      projectDir,
      assets: collectProjectAssets(projectDir),
    };

    if (builderPluginId) {
      await invokePluginHookSafe(builderPluginId, 'onBuildStart', {
        projectDir,
        toolchainPath,
      }, {
        ...pluginContext,
        logger: createPluginLogger(builderPluginId),
      });
    }

    const result = await buildSystem.buildProject(toolchainPath, javaPath, (line, level) => {
      sendToRenderer('build-log', { text: line, level: level || 'info' });

      if (builderPluginId) {
        void pluginManager.invokeHook(builderPluginId, 'onBuildLog', {
          line,
          level: level || 'info',
        }, {
          ...pluginContext,
          logger: createPluginLogger(builderPluginId),
        }).catch(() => {});
      }
    });

    if (builderPluginId) {
      if (result.success) {
        await invokePluginHookSafe(builderPluginId, 'onBuildEnd', result, {
          ...pluginContext,
          logger: createPluginLogger(builderPluginId),
        });
      } else {
        await invokePluginHookSafe(builderPluginId, 'onBuildError', {
          error: result.error || 'build failed',
          result,
        }, {
          ...pluginContext,
          logger: createPluginLogger(builderPluginId),
        });
      }
    }

    sendToRenderer('build-end', result);
    return result;
  } catch (err) {
    const r = { success: false, error: err.message || String(err) };
    sendToRenderer('build-end', r);
    return r;
  }
});

ipcMain.handle('build:getRomPath', async () => {
  return buildSystem.getLastRomPath();
});

ipcMain.handle('build:getProjectConfig', async () => {
  return buildSystem.loadProjectConfig();
});

ipcMain.handle('build:getBuilderPlugin', async () => {
  return { id: buildSystem.getBuilderPlugin() };
});

ipcMain.handle('build:setBuilderPlugin', async (_event, { id }) => {
  buildSystem.setBuilderPlugin(id || null);
  return { ok: true };
});

ipcMain.handle('build:getEmulatorPlugin', async () => {
  return { id: buildSystem.getEmulatorPlugin() };
});

ipcMain.handle('build:setEmulatorPlugin', async (_event, { id }) => {
  buildSystem.setEmulatorPlugin(id || null);
  return { ok: true };
});

ipcMain.handle('build:getCurrentSource', async () => {
  return buildSystem.loadCurrentSource();
});

ipcMain.handle('build:getSampleCode', async () => {
  const samplePath = buildSystem.getSampleSourceCode();
  return samplePath || null;
});

ipcMain.handle('app:getInfo', async () => {
  const wasm = readEmbeddedWasmInfo();
  return {
    appName: app.getName(),
    appVersion: app.getVersion(),
    buildNumber: appBuildMeta.buildNumber,
    buildAt: appBuildMeta.buildAt,
    appDescription: electronPackageJson.description || '',
    appPath: app.getAppPath(),
    platform: process.platform,
    arch: process.arch,
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
    nodeVersion: process.versions.node,
    embeddedWasm: wasm,
  };
});

ipcMain.handle('project:getCurrent', async () => {
  try {
    return { ok: true, ...buildSystem.getProjectInfo() };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('project:list', async () => {
  try {
    return { ok: true, ...buildSystem.listProjects() };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('project:openExisting', async (_event, payload) => {
  try {
    const projectName = String(payload?.projectName || '').trim();
    if (!projectName) {
      return { ok: false, error: 'project name is empty' };
    }
    const info = buildSystem.openProjectByName(projectName);
    return { ok: true, ...info };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('project:createNew', async (_event, payload) => {
  try {
    const projectName = String(payload?.projectName || '').trim();
    if (!projectName) {
      return { ok: false, error: 'project name is empty' };
    }

    const created = buildSystem.createProjectInRoot(projectName, payload?.config || {}, payload?.sourceCode || null);
    return {
      ok: true,
      projectDir: created.projectDir,
      projectName: path.basename(created.projectDir),
      title: payload?.config?.title || payload?.projectName,
      defaultProjectDir: buildSystem.getDefaultProjectDir(),
      projectsRootDir: buildSystem.getProjectsRootDir(),
    };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

app.whenReady().then(() => {
  createMenu();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopApiServer();
  if (debugWindow && !debugWindow.isDestroyed()) {
    debugWindow.close();
    debugWindow = null;
  }
  app.quit();
});
