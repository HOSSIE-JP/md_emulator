const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  openRomDialog: () => ipcRenderer.invoke('dialog:openRomFile'),
  readRomFile: (filePath) => ipcRenderer.invoke('fs:readRomFile', filePath),
  startApiServer: (options) => ipcRenderer.invoke('api:startServer', options),
  stopApiServer: () => ipcRenderer.invoke('api:stopServer'),
  isApiServerRunning: () => ipcRenderer.invoke('api:isRunning'),
  openDebugWindow: (options) => ipcRenderer.invoke('window:openDebug', options),
  onRomSelected: (callback) => {
    ipcRenderer.on('rom-selected', (_event, payload) => callback(payload));
  },
  onApiLog: (callback) => {
    ipcRenderer.on('api-log', (_event, payload) => callback(payload));
  },
  onApiExit: (callback) => {
    ipcRenderer.on('api-exit', (_event, payload) => callback(payload));
  },
});
