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
    openExternalUrl(url);
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

function getCodeRoot() {
  return buildSystem.getProjectDir();
}

function isPathInside(parentPath, childPath) {
  const rel = path.relative(parentPath, childPath);
  return rel === '' || (!!rel && !rel.startsWith('..') && !path.isAbsolute(rel));
}

function findExistingAncestor(targetPath) {
  let current = path.resolve(targetPath);
  while (!fs.existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return current;
}

function openExternalUrl(url) {
  try {
    const parsed = new URL(String(url || ''));
    if (!['http:', 'https:', 'mailto:'].includes(parsed.protocol)) {
      return;
    }
    shell.openExternal(parsed.toString());
  } catch (_err) {
  }
}

function resolveUnderCodeRoot(relativePath = '') {
  const codeRoot = path.resolve(getCodeRoot());
  const cleaned = String(relativePath || '').replace(/^[/\\]+/, '');
  const absPath = path.resolve(codeRoot, cleaned);
  if (!isPathInside(codeRoot, absPath)) {
    throw new Error(`project 配下のみアクセス可能です: ${relativePath}`);
  }
  const realCodeRoot = fs.existsSync(codeRoot) ? fs.realpathSync(codeRoot) : codeRoot;
  const realCheckPath = fs.existsSync(absPath)
    ? fs.realpathSync(absPath)
    : fs.realpathSync(findExistingAncestor(path.dirname(absPath)));
  if (!isPathInside(realCodeRoot, realCheckPath)) {
    throw new Error(`project path escapes project: ${relativePath}`);
  }
  return { codeRoot, absPath };
}

function readCodeTree(absDir, codeRoot) {
  const entries = fs.readdirSync(absDir, { withFileTypes: true })
    .sort((a, b) => {
      if (a.isDirectory() && !b.isDirectory()) return -1;
      if (!a.isDirectory() && b.isDirectory()) return 1;
      return a.name.localeCompare(b.name, 'ja');
    });

  return entries.map((entry) => {
    const fullPath = path.join(absDir, entry.name);
    const relPath = path.relative(codeRoot, fullPath).replace(/\\/g, '/');
    if (entry.isDirectory()) {
      return {
        type: 'directory',
        name: entry.name,
        path: relPath,
        children: readCodeTree(fullPath, codeRoot),
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
          label: 'Open Projects',
          accelerator: process.platform === 'darwin' ? 'Cmd+O' : 'Ctrl+O',
          click: () => {
            sendToRenderer('menu:openProjects');
          },
        },
        { type: 'separator' },
        {
          label: 'Setup',
          click: () => {
            sendToRenderer('menu:openSetup');
          },
        },
        { type: 'separator' },
        {
          label: 'Export ROM',
          accelerator: process.platform === 'darwin' ? 'Cmd+Shift+E' : 'Ctrl+Shift+E',
          click: async () => {
            const result = await handleExportRom();
            if (result.ok) {
              sendToRenderer('build-log', { text: `ROM をエクスポートしました: ${result.path}`, level: 'info' });
            } else if (!result.canceled) {
              sendToRenderer('build-log', { text: `Export ROM 失敗: ${result.error}`, level: 'error' });
            }
          },
        },
        {
          label: 'Export HTML',
          click: async () => {
            const result = await handleExportHtml();
            if (result.ok) {
              sendToRenderer('build-log', { text: `HTML をエクスポートしました: ${result.path}`, level: 'info' });
              shell.openPath(path.dirname(result.path)).catch(() => {});
            } else if (!result.canceled) {
              sendToRenderer('build-log', { text: `Export HTML 失敗: ${result.error}`, level: 'error' });
            }
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
    const codeRoot = getCodeRoot();
    fs.mkdirSync(codeRoot, { recursive: true });
    return { ok: true, root: codeRoot };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:list', async (_event, payload) => {
  try {
    const { codeRoot, absPath } = resolveUnderCodeRoot(payload?.path || '');
    if (!fs.existsSync(absPath)) {
      return { ok: false, error: `path not found: ${payload?.path || ''}` };
    }
    const stat = fs.statSync(absPath);
    if (!stat.isDirectory()) {
      return { ok: false, error: 'directory path is required' };
    }
    return {
      ok: true,
      root: codeRoot,
      path: path.relative(codeRoot, absPath).replace(/\\/g, '/'),
      entries: readCodeTree(absPath, codeRoot),
    };
  } catch (err) {
    return { ok: false, error: String(err?.message || err) };
  }
});

ipcMain.handle('codefs:read', async (_event, payload) => {
  try {
    const { absPath } = resolveUnderCodeRoot(payload?.path || '');
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
    const { absPath } = resolveUnderCodeRoot(payload?.path || '');
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
    const { absPath } = resolveUnderCodeRoot(payload?.path || '');
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
    const { absPath, codeRoot } = resolveUnderCodeRoot(payload?.path || '');
    if (absPath === codeRoot) {
      return { ok: false, error: 'project root は削除できません' };
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
  // パッケージ版では組み込み plugins/ は読み取り専用のため、
  // 書き込み可能なユーザーデータフォルダを開く
  const userDir = pluginManager.getUserPluginsDir();
  try {
    if (!fs.existsSync(userDir)) fs.mkdirSync(userDir, { recursive: true });
    const error = await shell.openPath(userDir);
    return error ? { ok: false, error } : { ok: true, path: userDir };
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

// ── ビルド共通ロジック ──────────────────────────────────────────────────────

async function runBuildFull() {
  try {
    const toolchainPath = setupManager.getToolchainDir();
    const javaPath = setupManager.getJavaExePath();
    const projectDir = buildSystem.getProjectDir();
    let builderPluginId = buildSystem.getBuilderPlugin();
    if (!toolchainPath) {
      return { success: false, error: 'ツールチェーンが設定されていません。Setup を実行してください。' };
    }
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
}

// ── Export HTML ジェネレータ ────────────────────────────────────────────────

function parseRomHeaderInfo(romBytes, romLabel) {
  const safeAscii = (start, len) => {
    if (romBytes.length <= start) return '';
    const end = Math.min(romBytes.length, start + len);
    return romBytes
      .subarray(start, end)
      .toString('ascii')
      .replace(/\0/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  };

  const readU16BE = (offset) => {
    if (offset + 1 >= romBytes.length) return null;
    return romBytes.readUInt16BE(offset);
  };

  const readU32BE = (offset) => {
    if (offset + 3 >= romBytes.length) return null;
    return romBytes.readUInt32BE(offset);
  };

  const checksum = readU16BE(0x18E);
  const romStart = readU32BE(0x1A0);
  const romEnd = readU32BE(0x1A4);

  return {
    fileName: romLabel,
    fileSize: romBytes.length,
    consoleName: safeAscii(0x100, 16),
    domesticTitle: safeAscii(0x120, 48),
    overseasTitle: safeAscii(0x150, 48),
    serial: safeAscii(0x180, 14),
    ioSupport: safeAscii(0x190, 16),
    region: safeAscii(0x1F0, 3),
    checksum: checksum == null ? 'N/A' : `0x${checksum.toString(16).padStart(4, '0').toUpperCase()}`,
    romRange: (romStart == null || romEnd == null)
      ? 'N/A'
      : `0x${romStart.toString(16).padStart(8, '0').toUpperCase()} - 0x${romEnd.toString(16).padStart(8, '0').toUpperCase()}`,
  };
}

function generateExportHtml({
  romBase64,
  romLabel,
  wasmJsText,
  wasmBase64,
  playerJsText,
  romInfo,
  appVersion,
  appBuildNumber,
  appBuildAt,
}) {
  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function escJs(s) {
    return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  // ── md_wasm.js パッチ: ES module exports 除去 + 内部変数名衝突を解消 ──
  let wasmJs = wasmJsText;
  wasmJs = wasmJs.replace('export class EmulatorHandle {', 'class EmulatorHandle {');
  wasmJs = wasmJs.replace('let wasmModule, wasm;', 'let __wbgInternalModule, wasm;');
  wasmJs = wasmJs.replace('    wasmModule = module;', '    __wbgInternalModule = module;');
  wasmJs = wasmJs.replace('export { initSync, __wbg_init as default };', '// [exports removed for standalone build]');

  // ── wasm-player.js パッチ: dynamic import を廃止し WASM を ArrayBuffer で直接初期化 ──
  let playerJs = playerJsText;
  playerJs = playerJs.replace(
    '    wasmModule = await import(`./pkg/md_wasm.js?v=${cacheBust}`);',
    '    wasmModule = { EmulatorHandle, default: __wbg_init };',
  );
  playerJs = playerJs.replace(
    '    await wasmModule.default(`./pkg/md_wasm_bg.wasm?v=${cacheBust}`);',
    '    { const _wb = atob(window.__WASM_B64), _wa = new Uint8Array(_wb.length);' +
    ' for (let _wi = 0; _wi < _wb.length; _wi++) _wa[_wi] = _wb.charCodeAt(_wi);' +
    ' await __wbg_init(_wa.buffer); }',
  );

  const romInfoLiteral = JSON.stringify(romInfo || {}).replace(/<\/script>/gi, '<\\/script>');
  const appVersionLiteral = escJs(appVersion || 'unknown');
  const appBuildNumberLiteral = escJs(appBuildNumber || 'dev');
  const appBuildAtLiteral = escJs(appBuildAt || 'N/A');

  const standaloneUiPatch = `
(() => {
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  const fmtBytes = (n) => {
    const num = Number(n || 0);
    if (!Number.isFinite(num)) return '0 bytes';
    if (num >= 1024 * 1024) return (num / (1024 * 1024)).toFixed(2) + ' MB (' + num + ' bytes)';
    if (num >= 1024) return (num / 1024).toFixed(2) + ' KB (' + num + ' bytes)';
    return num + ' bytes';
  };

  window.__ROM_INFO = ${romInfoLiteral};
  const romInfo = window.__ROM_INFO || {};

  setText('romFileName', romInfo.fileName || 'unknown');
  setText('romFileSize', fmtBytes(romInfo.fileSize));
  setText('romConsoleName', romInfo.consoleName || 'N/A');
  setText('romDomesticTitle', romInfo.domesticTitle || 'N/A');
  setText('romOverseasTitle', romInfo.overseasTitle || 'N/A');
  setText('romSerial', romInfo.serial || 'N/A');
  setText('romRegion', romInfo.region || 'N/A');
  setText('romChecksum', romInfo.checksum || 'N/A');
  setText('romRange', romInfo.romRange || 'N/A');
  setText('romIoSupport', romInfo.ioSupport || 'N/A');

  const appVersion = "${appVersionLiteral}";
  const appBuildNumber = "${appBuildNumberLiteral}";
  const appBuildAt = "${appBuildAtLiteral}";
  setText('helpVersionApp', 'MD Emulator v' + appVersion + ' / build ' + appBuildNumber);
  setText('helpVersionBuildAt', appBuildAt);

  const updateWasmVersion = () => {
    let wasmVersion = 'unknown';
    try {
      if (typeof EmulatorHandle !== 'undefined' && EmulatorHandle && EmulatorHandle.build_version) {
        wasmVersion = EmulatorHandle.build_version();
      }
    } catch (_) {}
    setText('helpVersionWasm', wasmVersion);
  };

  let versionRetry = 0;
  const versionTimer = setInterval(() => {
    versionRetry += 1;
    updateWasmVersion();
    if (versionRetry > 30) clearInterval(versionTimer);
  }, 200);
  updateWasmVersion();

  const runBtn = document.getElementById('toggleRun');
  let autoPlayRetries = 0;
  const autoPlayTimer = setInterval(() => {
    autoPlayRetries += 1;
    if (runBtn && !runBtn.disabled && String(runBtn.textContent || '').includes('▶')) {
      runBtn.click();
    }
    if (runBtn && String(runBtn.textContent || '').includes('⏸')) {
      clearInterval(autoPlayTimer);
    } else if (autoPlayRetries > 40) {
      clearInterval(autoPlayTimer);
    }
  }, 120);

  const dlRom = document.getElementById('downloadRom');
  if (dlRom) {
    dlRom.addEventListener('click', () => {
      try {
        const b64 = (window.__AUTOSTART_ROM_B64 && window.__AUTOSTART_ROM_B64.data) || '';
        const label = (window.__AUTOSTART_ROM_B64 && window.__AUTOSTART_ROM_B64.label) || (romInfo.fileName || 'game.bin');
        const bstr = atob(b64);
        const bytes = new Uint8Array(bstr.length);
        for (let i = 0; i < bstr.length; i++) bytes[i] = bstr.charCodeAt(i);
        const blob = new Blob([bytes], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = label;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (err) {
        const st = document.getElementById('status');
        if (st) st.textContent = 'ROM download failed: ' + err;
      }
    });
  }

  const helpModal = document.getElementById('helpModal');
  const helpBtn = document.getElementById('helpBtn');
  const helpClose = document.getElementById('helpClose');
  const helpBackdrop = document.getElementById('helpBackdrop');

  const closeHelp = () => {
    if (!helpModal) return;
    helpModal.classList.add('hidden');
    document.body.classList.remove('modal-open');
  };

  if (helpBtn) {
    helpBtn.addEventListener('click', () => {
      if (!helpModal) return;
      helpModal.classList.remove('hidden');
      document.body.classList.add('modal-open');
    });
  }
  if (helpClose) helpClose.addEventListener('click', closeHelp);
  if (helpBackdrop) helpBackdrop.addEventListener('click', closeHelp);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeHelp();
  });
})();`;

  // </script> が HTML を壊さないようエスケープ
  const scriptEscape = (s) => s.replace(/<\/script>/gi, '<\\/script>');
  const combinedScript = scriptEscape(wasmJs + '\n\n' + playerJs + '\n\n' + standaloneUiPatch);

  return `<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MD Emulator</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; background: #050a17; color: #ebf3ff;
      font-family: system-ui, "Segoe UI", sans-serif; }
    body { display: flex; flex-direction: column; align-items: center; }
    body.modal-open { overflow: hidden; }
    header { width: 100%; max-width: 640px; padding: 10px 14px;
      display: flex; align-items: center; gap: 10px;
      border-bottom: 1px solid #1a2a42; }
    h1 { font-size: 15px; font-weight: 600; flex: 1;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    main { width: 100%; max-width: 640px; padding: 8px; flex: 1;
      display: flex; flex-direction: column; gap: 8px; }
    .screen-stage { width: 100%; aspect-ratio: 320 / 224; background: #000;
      border-radius: 8px; overflow: hidden; border: 1px solid #1a2a42; }
    .screen-stage:fullscreen { width: 100vw; height: 100vh; border-radius: 0;
      display: flex; align-items: center; justify-content: center; }
    canvas#screen { width: 100%; height: 100%; object-fit: contain;
      image-rendering: pixelated; display: block; }
    .controls { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    button { background: #163154; border: 1px solid #2a3f5e; color: #ebf3ff;
      border-radius: 8px; padding: 7px 12px; cursor: pointer; font-size: 13px; }
    button:hover { background: #1d3e68; }
    button:disabled { opacity: 0.4; cursor: not-allowed; }
    .spacer { flex: 1; }
    #status { font-size: 12px; color: #4bc8ff; min-height: 18px; }
    #buildVersion, #gamepadStatus, #devPanel, #installPwa { display: none; }
    input[type="file"] { display: none; }
    #dropZone { display: contents; }
    .rom-panel {
      margin-top: 8px;
      border: 1px solid #1a2a42;
      background: #0b1528;
      border-radius: 8px;
      padding: 10px;
      display: grid;
      gap: 6px;
      font-size: 12px;
    }
    .rom-panel h2 { font-size: 13px; font-weight: 700; margin-bottom: 2px; }
    .info-grid {
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 4px 10px;
      align-items: baseline;
    }
    .info-grid dt { color: #8cb4de; }
    .info-grid dd { word-break: break-all; }
    .footer-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 4px;
    }
    .modal {
      position: fixed;
      inset: 0;
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .modal.hidden { display: none; }
    .modal-backdrop {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.62);
    }
    .modal-card {
      position: relative;
      width: min(640px, calc(100vw - 24px));
      max-height: calc(100vh - 24px);
      overflow: auto;
      background: #0b1528;
      border: 1px solid #2a3f5e;
      border-radius: 10px;
      padding: 14px;
    }
    .modal-card h3 { font-size: 16px; margin-bottom: 8px; }
    .modal-card h4 { font-size: 13px; margin: 10px 0 6px; color: #8cb4de; }
    .help-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .help-table th, .help-table td {
      border: 1px solid #1f3250;
      padding: 6px;
      text-align: left;
    }
    .help-actions { display: flex; justify-content: flex-end; margin-top: 10px; }
    @media (max-width: 480px) {
      .info-grid { grid-template-columns: 1fr; }
      .footer-actions { justify-content: stretch; }
      .footer-actions button { flex: 1; }
    }
  </style>
  <script>
    window.__AUTOSTART_ROM_B64 = { data: "${romBase64}", label: "${escJs(romLabel)}" };
    window.__WASM_B64 = "${wasmBase64}";
  </script>
</head>
<body>
  <header>
    <h1>MD Emulator</h1>
    <span id="buildVersion"></span>
  </header>
  <main>
    <div id="dropZone">
      <div class="screen-stage">
        <canvas id="screen" width="320" height="224"></canvas>
      </div>
    </div>
    <div id="status">読み込み中...</div>
    <div id="gamepadStatus"></div>
    <div class="controls">
      <button id="toggleRun" title="再生 / 一時停止" disabled>&#9654;</button>
      <button id="reset" title="リセット" disabled>&#8634;</button>
      <button id="toggleAudio" title="ミュート切替" disabled>&#128266;</button>
      <span class="spacer"></span>
      <button id="fullscreen" title="フルスクリーン">&#x26F6;</button>
    </div>
    <input type="file" id="romFile" accept=".bin,.md,.gen,.smd">
    <button id="loadRom" style="display:none">Load ROM</button>
    <select id="bundledRom" style="display:none"></select>
    <button id="loadBundled" style="display:none">Load Bundled</button>
    <div id="meta" style="display:none"></div>
    <section class="rom-panel">
      <h2>ROM Information</h2>
      <dl class="info-grid">
        <dt>File Name</dt><dd id="romFileName">-</dd>
        <dt>File Size</dt><dd id="romFileSize">-</dd>
        <dt>Console</dt><dd id="romConsoleName">-</dd>
        <dt>Domestic Title</dt><dd id="romDomesticTitle">-</dd>
        <dt>Overseas Title</dt><dd id="romOverseasTitle">-</dd>
        <dt>Serial</dt><dd id="romSerial">-</dd>
        <dt>Region</dt><dd id="romRegion">-</dd>
        <dt>Checksum</dt><dd id="romChecksum">-</dd>
        <dt>ROM Range</dt><dd id="romRange">-</dd>
        <dt>I/O Support</dt><dd id="romIoSupport">-</dd>
      </dl>
      <div class="footer-actions">
        <button id="downloadRom" title="ROM をダウンロード">Download ROM</button>
        <button id="helpBtn" title="ヘルプを表示">Help</button>
      </div>
    </section>
    <div id="installPwa"></div>
    <div id="fsOverlay"></div>
    <div id="devPanel"></div>
  </main>

  <div id="helpModal" class="modal hidden" aria-hidden="true">
    <div id="helpBackdrop" class="modal-backdrop"></div>
    <section class="modal-card" role="dialog" aria-modal="true" aria-label="Help">
      <h3>MD Emulator Help</h3>

      <h4>Keyboard Controller Mapping</h4>
      <table class="help-table">
        <thead>
          <tr><th>Controller</th><th>Keyboard</th></tr>
        </thead>
        <tbody>
          <tr><td>Up / Down / Left / Right</td><td>Arrow Keys or W / S / A / D</td></tr>
          <tr><td>Button A</td><td>U</td></tr>
          <tr><td>Button B</td><td>J</td></tr>
          <tr><td>Button C</td><td>K</td></tr>
          <tr><td>Start</td><td>Enter</td></tr>
        </tbody>
      </table>

      <h4>Version Information</h4>
      <table class="help-table">
        <tbody>
          <tr><th>App</th><td id="helpVersionApp">-</td></tr>
          <tr><th>Build At</th><td id="helpVersionBuildAt">-</td></tr>
          <tr><th>WASM</th><td id="helpVersionWasm">-</td></tr>
        </tbody>
      </table>

      <div class="help-actions">
        <button id="helpClose">Close</button>
      </div>
    </section>
  </div>

  <script type="module">
${combinedScript}
  </script>
</body>
</html>`;
}

// ── Export ハンドラ ─────────────────────────────────────────────────────────

async function handleExportRom() {
  const buildResult = await runBuildFull();
  if (!buildResult.success) {
    return { ok: false, error: buildResult.error || 'ビルドに失敗しました' };
  }

  const romPath = buildSystem.getLastRomPath();
  if (!romPath || !fs.existsSync(romPath)) {
    return { ok: false, error: 'ビルド成功しましたが ROM ファイルが見つかりません' };
  }

  const owner = (mainWindow && !mainWindow.isDestroyed()) ? mainWindow : undefined;
  let suggested = path.basename(romPath);
  try {
    const cfg = buildSystem.loadProjectConfig();
    if (cfg?.name) suggested = `${cfg.name.replace(/[^a-zA-Z0-9._-]/g, '_')}.bin`;
  } catch (_) {}

  const result = await dialog.showSaveDialog(owner, {
    title: 'ROM をエクスポート',
    defaultPath: suggested,
    filters: [
      { name: 'Mega Drive ROM', extensions: ['bin', 'md', 'gen'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });

  if (result.canceled || !result.filePath) return { ok: false, canceled: true };
  fs.copyFileSync(romPath, result.filePath);
  return { ok: true, path: result.filePath };
}

async function handleExportHtml() {
  const buildResult = await runBuildFull();
  if (!buildResult.success) {
    return { ok: false, error: buildResult.error || 'ビルドに失敗しました' };
  }

  const romPath = buildSystem.getLastRomPath();
  if (!romPath || !fs.existsSync(romPath)) {
    return { ok: false, error: 'ビルド成功しましたが ROM ファイルが見つかりません' };
  }

  // ソースファイルパスを確認
  const pkgDir = path.join(__dirname, 'pkg');
  const wasmJsPath = path.join(pkgDir, 'md_wasm.js');
  const wasmBinPath = path.join(pkgDir, 'md_wasm_bg.wasm');
  const playerJsPath = path.join(__dirname, 'wasm-player.js');

  for (const [label, p] of [['md_wasm.js', wasmJsPath], ['md_wasm_bg.wasm', wasmBinPath], ['wasm-player.js', playerJsPath]]) {
    if (!fs.existsSync(p)) {
      return { ok: false, error: `${label} が見つかりません。npm run copy-pkg を実行してください。` };
    }
  }

  const wasmJsText = fs.readFileSync(wasmJsPath, 'utf-8');
  const wasmBase64 = fs.readFileSync(wasmBinPath).toString('base64');
  const playerJsText = fs.readFileSync(playerJsPath, 'utf-8');
  const romBytes = fs.readFileSync(romPath);
  const romBase64 = romBytes.toString('base64');
  const romLabel = path.basename(romPath);
  const romInfo = parseRomHeaderInfo(romBytes, romLabel);

  // 保存先 HTML ファイルを選択（シングルファイル・サーバー不要）
  const owner = (mainWindow && !mainWindow.isDestroyed()) ? mainWindow : undefined;
  let suggested = romLabel.replace(/\.(bin|md|gen|smd)$/i, '') + '.html';
  try {
    const cfg = buildSystem.loadProjectConfig();
    if (cfg?.name) suggested = `${cfg.name.replace(/[^a-zA-Z0-9._-]/g, '_')}.html`;
  } catch (_) {}

  const saveResult = await dialog.showSaveDialog(owner, {
    title: 'HTML をエクスポート（スタンドアロン・サーバー不要）',
    defaultPath: suggested,
    filters: [{ name: 'HTML ファイル', extensions: ['html'] }],
  });
  if (saveResult.canceled || !saveResult.filePath) return { ok: false, canceled: true };

  const html = generateExportHtml({
    romBase64,
    romLabel,
    wasmJsText,
    wasmBase64,
    playerJsText,
    romInfo,
    appVersion: electronPackageJson.version,
    appBuildNumber: appBuildMeta.buildNumber,
    appBuildAt: appBuildMeta.buildAt,
  });
  fs.writeFileSync(saveResult.filePath, html, 'utf-8');

  return { ok: true, path: saveResult.filePath };
}

ipcMain.handle('build:run', async () => {
  return runBuildFull();
});

ipcMain.handle('export:rom', async () => {
  return handleExportRom();
});

ipcMain.handle('export:html', async () => {
  return handleExportHtml();
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
