'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronTestPlay', {
  readRomFile: (filePath) => ipcRenderer.invoke('fs:readRomFile', filePath),
  openDebugWindow: (options) => ipcRenderer.invoke('window:openDebug', options),
});
