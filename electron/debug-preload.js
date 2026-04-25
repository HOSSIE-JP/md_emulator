const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronDebug', {
  getWasmSnapshot: (options) => ipcRenderer.invoke('debug:getWasmSnapshot', options || {}),
});
