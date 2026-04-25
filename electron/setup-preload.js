'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronSetup', {
  getStatus: () => ipcRenderer.invoke('setup:getStatus'),
  listSgdkVersions: () => ipcRenderer.invoke('setup:listSgdkVersions'),
  downloadSgdk: (tag) => ipcRenderer.invoke('setup:downloadSgdk', tag),
  setSgdkPath: (p) => ipcRenderer.invoke('setup:setSgdkPath', p),
  listMarsdevVersions: () => ipcRenderer.invoke('setup:listMarsdevVersions'),
  downloadMarsdev: (tag) => ipcRenderer.invoke('setup:downloadMarsdev', tag),
  setMarsdevPath: (p) => ipcRenderer.invoke('setup:setMarsdevPath', p),
  downloadJava: () => ipcRenderer.invoke('setup:downloadJava'),

  onProgress: (callback) => {
    ipcRenderer.on('setup-progress', (_event, payload) => callback(payload));
  },
});
