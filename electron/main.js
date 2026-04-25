const path = require('path');
const fs = require('fs');
const net = require('net');
const { shell } = require('electron');
const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron');
const { spawn } = require('child_process');

let mainWindow = null;
let debugWindow = null;
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

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Open ROM...',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            if (!mainWindow) {
              return;
            }
            const result = await dialog.showOpenDialog(mainWindow, {
              properties: ['openFile'],
              filters: [
                { name: 'Mega Drive ROM', extensions: ['bin', 'md', 'gen', 'smd', 'sms', 'zip'] },
                { name: 'All Files', extensions: ['*'] },
              ],
            });
            if (!result.canceled && result.filePaths.length > 0) {
              sendToRenderer('rom-selected', { filePath: result.filePaths[0] });
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
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
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
  if (!mainWindow || mainWindow.isDestroyed()) {
    return { ok: false, error: 'main window is not available' };
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
    const result = await mainWindow.webContents.executeJavaScript(script, true);
    return result;
  } catch (error) {
    return { ok: false, error: String(error?.message || error) };
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
