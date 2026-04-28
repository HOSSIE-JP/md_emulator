'use strict';

const Module = require('module');

function loadWithMockedElectron(modulePath, appOverrides = {}) {
  const originalLoad = Module._load;
  const mockApp = {
    isPackaged: false,
    getPath(name) {
      if (Object.prototype.hasOwnProperty.call(appOverrides.paths || {}, name)) {
        return appOverrides.paths[name];
      }
      return appOverrides.userData || '';
    },
    getAppPath() {
      return appOverrides.appPath || '';
    },
    getName() {
      return appOverrides.name || 'md-game-editor-test';
    },
    getVersion() {
      return appOverrides.version || '0.0.0-test';
    },
    setPath() {},
    whenReady() {
      return Promise.resolve();
    },
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
    delete require.cache[require.resolve(modulePath)];
    return require(modulePath);
  } finally {
    Module._load = originalLoad;
  }
}

module.exports = { loadWithMockedElectron };
