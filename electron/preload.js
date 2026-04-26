const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // --- 既存 ---
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
  // --- エディタ追加 ---
  openSetupWindow: () => ipcRenderer.invoke('window:openSetup'),
  openTestPlayWindow: (romPath) => ipcRenderer.invoke('window:openTestPlay', romPath),
  generateProject: (sourceCode, config) => ipcRenderer.invoke('build:generateProject', sourceCode, config),
  runBuild: () => ipcRenderer.invoke('build:run'),
  getRomPath: () => ipcRenderer.invoke('build:getRomPath'),
  openPathInExplorer: (targetPath, options) => ipcRenderer.invoke('fs:openPathInExplorer', targetPath, options || {}),
  saveRomAs: (sourcePath) => ipcRenderer.invoke('fs:saveRomAs', sourcePath),
  getProjectConfig: () => ipcRenderer.invoke('build:getProjectConfig'),
  generateSample: () => ipcRenderer.invoke('build:getSampleCode'),
  onBuildLog: (callback) => {
    ipcRenderer.on('build-log', (_event, payload) => callback(payload));
  },
  onBuildEnd: (callback) => {
    ipcRenderer.on('build-end', (_event, payload) => callback(payload));
  },
  onMenuOpenSetup: (callback) => {
    ipcRenderer.on('menu:openSetup', (_event) => callback());
  },
});
