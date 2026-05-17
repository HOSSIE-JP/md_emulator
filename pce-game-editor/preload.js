'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pceAPI', {
  appGetInfo: () => ipcRenderer.invoke('app:getInfo'),
  quitApp: () => ipcRenderer.invoke('app:quit'),

  getStartupState: () => ipcRenderer.invoke('project:getStartupState'),
  getCurrentProject: () => ipcRenderer.invoke('project:getCurrent'),
  listProjects: () => ipcRenderer.invoke('project:list'),
  createSampleProject: (payload) => ipcRenderer.invoke('project:createSample', payload || {}),
  openProject: (payload) => ipcRenderer.invoke('project:open', payload || {}),
  getProjectConfig: () => ipcRenderer.invoke('project:getConfig'),
  saveProjectConfig: (patch) => ipcRenderer.invoke('project:saveConfig', patch || {}),

  getSetupStatus: () => ipcRenderer.invoke('setup:getStatus'),
  getSetupCatalog: () => ipcRenderer.invoke('setup:getCatalog'),
  listSetupVersions: (kind) => ipcRenderer.invoke('setup:listVersions', { kind }),
  setToolPath: (kind, value) => ipcRenderer.invoke('setup:setToolPath', { kind, value }),
  downloadTool: (payload) => ipcRenderer.invoke('setup:downloadTool', payload || {}),
  onSetupProgress: (callback) => ipcRenderer.on('setup-progress', (_event, payload) => callback(payload)),

  listAssets: () => ipcRenderer.invoke('assets:list'),
  upsertAsset: (asset) => ipcRenderer.invoke('assets:upsert', asset || {}),
  deleteAsset: (id) => ipcRenderer.invoke('assets:delete', { id }),

  getCodeRoot: () => ipcRenderer.invoke('codefs:getRoot'),
  listCodeTree: (payload) => ipcRenderer.invoke('codefs:list', payload || {}),
  readCodeFile: (payload) => ipcRenderer.invoke('codefs:read', payload || {}),
  writeCodeFile: (payload) => ipcRenderer.invoke('codefs:write', payload || {}),
  createCodeEntry: (payload) => ipcRenderer.invoke('codefs:create', payload || {}),
  deleteCodeEntry: (payload) => ipcRenderer.invoke('codefs:delete', payload || {}),
  renameCodeEntry: (payload) => ipcRenderer.invoke('codefs:rename', payload || {}),

  listPlugins: () => ipcRenderer.invoke('plugins:list'),
  getPluginRendererAssets: (id) => ipcRenderer.invoke('plugins:getRendererAssets', { id }),
  invokePluginHook: (id, hook, payload) => ipcRenderer.invoke('plugins:invokeHook', { id, hook, payload }),
  getPluginRoles: () => ipcRenderer.invoke('plugins:getRoles'),
  getPluginRole: (roleId) => ipcRenderer.invoke('plugins:getRole', { roleId }),
  setPluginRole: (roleId, id) => ipcRenderer.invoke('plugins:setRole', { roleId, id }),
  setPluginEnabled: (id, enabled) => ipcRenderer.invoke('plugins:setEnabled', { id, enabled }),
  openPluginsFolder: () => ipcRenderer.invoke('plugins:openFolder'),

  runBuild: (options) => ipcRenderer.invoke('build:run', options || {}),
  getRomPath: () => ipcRenderer.invoke('build:getRomPath'),
  openTestPlay: (romPath) => ipcRenderer.invoke('testplay:open', { romPath }),
  openSetupWindow: () => ipcRenderer.invoke('window:openSetup'),
  openPath: (targetPath) => ipcRenderer.invoke('fs:openPath', { targetPath }),
  pickFile: (options) => ipcRenderer.invoke('dialog:pickFile', options || {}),

  onBuildLog: (callback) => ipcRenderer.on('build-log', (_event, payload) => callback(payload)),
  onBuildEnd: (callback) => ipcRenderer.on('build-end', (_event, payload) => callback(payload)),
  onPluginLog: (callback) => ipcRenderer.on('plugin-log', (_event, payload) => callback(payload)),
});
