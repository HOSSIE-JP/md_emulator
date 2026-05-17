'use strict';

const Module = require('module');
const path = require('path');

function clearAppModuleCache() {
  const appRoot = path.resolve(__dirname, '..', '..');
  Object.keys(require.cache).forEach((id) => {
    if (id.startsWith(appRoot) && !id.includes(`${path.sep}tests${path.sep}`)) {
      delete require.cache[id];
    }
  });
}

function loadWithMockedElectron(modulePath, appOverrides = {}) {
  const originalLoad = Module._load;
  const paths = appOverrides.paths || {};
  const mockApp = {
    isPackaged: false,
    getPath(name) {
      if (Object.prototype.hasOwnProperty.call(paths, name)) return paths[name];
      if (name === 'userData') return appOverrides.userData || '';
      if (name === 'logs') return appOverrides.logs || '';
      if (name === 'exe') return appOverrides.exePath || '/tmp/PCEGameEditor';
      return appOverrides.userData || '';
    },
    setPath() {},
    getName() { return 'pce-game-editor-test'; },
    getVersion() { return '0.0.0-test'; },
    requestSingleInstanceLock() { return true; },
    whenReady() { return Promise.resolve(); },
    on() {},
    quit() {},
    ...appOverrides.app,
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === 'electron') {
      return {
        app: mockApp,
        BrowserWindow: class {},
        dialog: {},
        ipcMain: { handle() {} },
        Menu: { buildFromTemplate(template) { return template; }, setApplicationMenu() {} },
        shell: { openPath: async () => '', openExternal: async () => {} },
      };
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    clearAppModuleCache();
    delete require.cache[require.resolve(modulePath)];
    return require(modulePath);
  } finally {
    Module._load = originalLoad;
  }
}

function loadPreloadWithMockedElectron(modulePath) {
  const originalLoad = Module._load;
  const exposed = {};
  const invocations = [];

  const ipcRenderer = {
    invoke(channel, ...args) {
      invocations.push({ channel, args });
      return Promise.resolve({ channel, args });
    },
    on() {},
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === 'electron') {
      return {
        contextBridge: {
          exposeInMainWorld(name, api) {
            exposed[name] = api;
          },
        },
        ipcRenderer,
      };
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    clearAppModuleCache();
    delete require.cache[require.resolve(modulePath)];
    require(modulePath);
    return { exposed, invocations };
  } finally {
    Module._load = originalLoad;
  }
}

module.exports = { loadPreloadWithMockedElectron, loadWithMockedElectron };
