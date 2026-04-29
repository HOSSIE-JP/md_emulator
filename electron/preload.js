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
  generateStructureOnly: (config) => ipcRenderer.invoke('build:generateStructureOnly', config),
  runBuild: () => ipcRenderer.invoke('build:run'),
  getRomPath: () => ipcRenderer.invoke('build:getRomPath'),
  getAppInfo: () => ipcRenderer.invoke('app:getInfo'),
  openPathInExplorer: (targetPath, options) => ipcRenderer.invoke('fs:openPathInExplorer', targetPath, options || {}),
  saveRomAs: (sourcePath) => ipcRenderer.invoke('fs:saveRomAs', sourcePath),
  getProjectConfig: () => ipcRenderer.invoke('build:getProjectConfig'),
  getCurrentSource: () => ipcRenderer.invoke('build:getCurrentSource'),
  generateSample: () => ipcRenderer.invoke('build:getSampleCode'),
  onBuildLog: (callback) => {
    ipcRenderer.on('build-log', (_event, payload) => callback(payload));
  },
  onBuildEnd: (callback) => {
    ipcRenderer.on('build-end', (_event, payload) => callback(payload));
  },
  onPluginLog: (callback) => {
    ipcRenderer.on('plugin-log', (_event, payload) => callback(payload));
  },
  onMenuOpenSetup: (callback) => {
    ipcRenderer.on('menu:openSetup', (_event) => callback());
  },
  onMenuOpenProjects: (callback) => {
    ipcRenderer.on('menu:openProjects', (_event) => callback());
  },
  onMenuOpenAbout: (callback) => {
    ipcRenderer.on('menu:openAbout', (_event) => callback());
  },
  listResDefinitions: () => ipcRenderer.invoke('res:listDefinitions'),
  createResFile: (relativePath) => ipcRenderer.invoke('res:createFile', relativePath),
  addResEntry: (payload) => ipcRenderer.invoke('res:addEntry', payload),
  updateResEntry: (payload) => ipcRenderer.invoke('res:updateEntry', payload),
  deleteResEntry: (payload) => ipcRenderer.invoke('res:deleteEntry', payload),
  openResDirectory: () => ipcRenderer.invoke('res:openDirectory'),
  reorderResEntries: (payload) => ipcRenderer.invoke('res:reorderEntries', payload),
  pickFile: (options) => ipcRenderer.invoke('dialog:pickFile', options || {}),
  pickAssetSource: () => ipcRenderer.invoke('res:pickAssetSource'),
  readFileAsDataUrl: (sourcePath) => ipcRenderer.invoke('res:readFileAsDataUrl', sourcePath),
  readTempFileAsDataUrl: (sourcePath, options) => ipcRenderer.invoke('res:readTempFileAsDataUrl', sourcePath, options || {}),
  deleteTempFile: (sourcePath) => ipcRenderer.invoke('res:deleteTempFile', sourcePath),
  writeAssetFile: (payload) => ipcRenderer.invoke('res:writeAssetFile', payload),
  getCurrentProject: () => ipcRenderer.invoke('project:getCurrent'),
  listProjects: () => ipcRenderer.invoke('project:list'),
  openExistingProject: (payload) => ipcRenderer.invoke('project:openExisting', payload),
  createNewProject: (payload) => ipcRenderer.invoke('project:createNew', payload),
  // --- コードエディタ向け (プロジェクト配下) ---
  getCodeRoot: () => ipcRenderer.invoke('codefs:getRoot'),
  listCodeTree: (payload) => ipcRenderer.invoke('codefs:list', payload),
  readCodeFile: (payload) => ipcRenderer.invoke('codefs:read', payload),
  writeCodeFile: (payload) => ipcRenderer.invoke('codefs:write', payload),
  createCodeEntry: (payload) => ipcRenderer.invoke('codefs:create', payload),
  deleteCodeEntry: (payload) => ipcRenderer.invoke('codefs:delete', payload),
  // --- プラグイン ---
  listPlugins: () => ipcRenderer.invoke('plugins:list'),
  getPluginRendererAssets: (id) => ipcRenderer.invoke('plugins:getRendererAssets', { id }),
  invokePluginHook: (id, hook, payload) => ipcRenderer.invoke('plugins:invokeHook', { id, hook, payload }),
  getPluginRoles: () => ipcRenderer.invoke('plugins:getRoles'),
  getPluginRole: (roleId) => ipcRenderer.invoke('plugins:getRole', { roleId }),
  setPluginRole: (roleId, id) => ipcRenderer.invoke('plugins:setRole', { roleId, id }),
  setPluginEnabled: (id, enabled) => ipcRenderer.invoke('plugins:setEnabled', { id, enabled }),
  runPluginGenerator: (id) => ipcRenderer.invoke('plugins:runGenerator', { id }),
  openPluginsFolder: () => ipcRenderer.invoke('plugins:openFolder'),
  // --- エクスポート ---
  exportRom: () => ipcRenderer.invoke('export:rom'),
  exportHtml: () => ipcRenderer.invoke('export:html'),
});
