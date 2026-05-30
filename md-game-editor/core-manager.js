'use strict';

const fs = require('fs');
const path = require('path');

const mdBuildSystem = require('./build-system');
const mdSetupManager = require('./setup-manager');
const mdRescompManager = require('./rescomp-manager');
const pceBuildSystem = require('./pce-build-system');
const pceSetupManager = require('./pce-setup-manager');
const pceAssetManager = require('./pce-asset-manager');

const CORE_IDS = Object.freeze({
  MEGA_DRIVE: 'mega-drive',
  PC_ENGINE: 'pc-engine',
});

const CORES = Object.freeze([
  {
    id: CORE_IDS.MEGA_DRIVE,
    pluginId: 'mega-drive-core',
    name: 'Mega Drive',
    shortName: 'MD',
    platform: 'md',
    description: 'SGDK を使う Mega Drive / Genesis プロジェクト',
  },
  {
    id: CORE_IDS.PC_ENGINE,
    pluginId: 'pc-engine-core',
    name: 'PC Engine',
    shortName: 'PCE',
    platform: 'pce',
    description: 'llvm-mos を標準に HuCard / 実験的 PCE-CD を扱う PC Engine プロジェクト',
  },
]);

function normalizeCoreId(value) {
  const raw = String(value || '').trim();
  if (raw === CORE_IDS.PC_ENGINE || raw === 'pce' || raw === 'pcengine') return CORE_IDS.PC_ENGINE;
  return CORE_IDS.MEGA_DRIVE;
}

function detectCoreIdFromConfig(config = {}) {
  if (config && typeof config === 'object') {
    if (config.coreId) return normalizeCoreId(config.coreId);
    if (String(config.platform || '').trim().toLowerCase() === 'pce') return CORE_IDS.PC_ENGINE;
  }
  return CORE_IDS.MEGA_DRIVE;
}

function readProjectConfig(projectDir) {
  try {
    const cfgPath = path.join(path.resolve(projectDir), 'project.json');
    if (fs.existsSync(cfgPath)) {
      return JSON.parse(fs.readFileSync(cfgPath, 'utf-8')) || {};
    }
  } catch (_) {}
  return {};
}

function getCoreIdForProjectDir(projectDir) {
  return detectCoreIdFromConfig(readProjectConfig(projectDir));
}

function getBuildSystemForCore(coreId) {
  return normalizeCoreId(coreId) === CORE_IDS.PC_ENGINE ? pceBuildSystem : mdBuildSystem;
}

function getSetupManagerForCore(coreId) {
  return normalizeCoreId(coreId) === CORE_IDS.PC_ENGINE ? pceSetupManager : mdSetupManager;
}

function getActiveProjectDir() {
  return mdBuildSystem.getProjectDir();
}

function getActiveCoreId() {
  return getCoreIdForProjectDir(getActiveProjectDir());
}

function getActiveBuildSystem() {
  return getBuildSystemForCore(getActiveCoreId());
}

function withCoreId(config = {}, fallbackCoreId = CORE_IDS.MEGA_DRIVE) {
  const hasExplicitCore = Boolean(config?.coreId || config?.platform);
  const coreId = hasExplicitCore ? detectCoreIdFromConfig(config) : normalizeCoreId(fallbackCoreId);
  return { ...(config || {}), coreId };
}

function withInferredCoreInfo(info = {}, projectDir = info.projectDir) {
  const coreId = projectDir ? getCoreIdForProjectDir(projectDir) : detectCoreIdFromConfig(info);
  const core = getCore(coreId);
  return { ...info, coreId, core };
}

function getCore(coreId) {
  const normalized = normalizeCoreId(coreId);
  return CORES.find((core) => core.id === normalized) || CORES[0];
}

function listCores() {
  return CORES.map((core) => ({ ...core }));
}

function routeCoreForNewProject(config = {}, templateId = '') {
  if (config?.coreId || config?.platform) return detectCoreIdFromConfig(config);
  if (String(templateId || '').startsWith('template_pce_')) return CORE_IDS.PC_ENGINE;
  return CORE_IDS.MEGA_DRIVE;
}

function normalizeListedProject(project) {
  const projectDir = project?.projectDir || '';
  const coreId = project?.coreId || (projectDir ? getCoreIdForProjectDir(projectDir) : detectCoreIdFromConfig(project));
  return {
    ...project,
    coreId,
    coreName: getCore(coreId).name,
  };
}

function listProjects() {
  const mdList = mdBuildSystem.listProjects();
  const pceList = pceBuildSystem.listProjects();
  const currentProjectDir = path.resolve(getProjectDir());
  const byDir = new Map();

  [...(mdList.projects || []), ...(pceList.projects || [])].forEach((project) => {
    const item = normalizeListedProject(project);
    byDir.set(path.resolve(item.projectDir), {
      ...item,
      current: path.resolve(item.projectDir) === currentProjectDir,
    });
  });

  const projects = Array.from(byDir.values())
    .sort((left, right) => String(left.projectName).localeCompare(String(right.projectName), 'ja'));
  const templates = [
    ...(mdList.templates || []).map(normalizeListedProject),
    ...(pceList.templates || []).map(normalizeListedProject),
  ].sort((left, right) => String(left.templateId || left.projectName).localeCompare(String(right.templateId || right.projectName), 'ja'));

  return {
    projectsRootDir: mdList.projectsRootDir,
    pceProjectsRootDir: pceList.projectsRootDir,
    currentProjectDir,
    projects,
    recentProjects: (mdList.recentProjects || []).map(normalizeListedProject),
    templates,
    cores: listCores(),
    activeCoreId: getActiveCoreId(),
  };
}

function getProjectStartupState() {
  const state = mdBuildSystem.getProjectStartupState();
  return {
    ...state,
    cores: listCores(),
    activeCoreId: state.savedProjectExists ? getCoreIdForProjectDir(state.savedProjectDir) : CORE_IDS.MEGA_DRIVE,
  };
}

function getProjectDir() {
  return mdBuildSystem.getProjectDir();
}

function setProjectDir(projectDir) {
  const coreId = getCoreIdForProjectDir(projectDir);
  return getBuildSystemForCore(coreId).setProjectDir(projectDir);
}

function getProjectInfo() {
  const projectDir = getProjectDir();
  return withInferredCoreInfo(getBuildSystemForCore(getCoreIdForProjectDir(projectDir)).getProjectInfo(), projectDir);
}

function openProject(projectDir) {
  const coreId = getCoreIdForProjectDir(projectDir);
  return withInferredCoreInfo(getBuildSystemForCore(coreId).openProject(projectDir), projectDir);
}

function openProjectByName(projectName) {
  const normalized = String(projectName || '').trim();
  const candidates = [
    path.join(mdBuildSystem.getProjectsRootDir(), normalized),
    path.join(pceBuildSystem.getProjectsRootDir(), normalized),
  ];
  const found = candidates.find((candidate) => fs.existsSync(path.join(candidate, 'project.json')));
  if (!found) return openProject(candidates[0]);
  return openProject(found);
}

function createProject(projectDir, config = {}, sourceCode) {
  const coreId = detectCoreIdFromConfig(config);
  const nextConfig = withCoreId(config, coreId);
  if (coreId === CORE_IDS.PC_ENGINE) {
    return pceBuildSystem.createProjectFromTemplate(projectDir, 'template_pce_sample', nextConfig);
  }
  return mdBuildSystem.createProject(projectDir, nextConfig, sourceCode);
}

function createProjectInRoot(projectName, config = {}, sourceCode) {
  const coreId = detectCoreIdFromConfig(config);
  const root = coreId === CORE_IDS.PC_ENGINE ? pceBuildSystem.getProjectsRootDir() : mdBuildSystem.getProjectsRootDir();
  return createProjectInParent(root, projectName, config, sourceCode);
}

function createProjectInParent(parentDir, projectName, config = {}, sourceCode = null, options = {}) {
  const coreId = routeCoreForNewProject(config, options?.templateId);
  const nextConfig = withCoreId(config, coreId);
  if (coreId === CORE_IDS.PC_ENGINE) {
    const mdDefaultRoot = path.resolve(mdBuildSystem.getProjectsRootDir());
    const requestedParent = parentDir ? path.resolve(parentDir) : '';
    const parent = (!requestedParent || requestedParent === mdDefaultRoot)
      ? pceBuildSystem.getProjectsRootDir()
      : requestedParent;
    const normalizedName = pceBuildSystem.normalizeProjectName(projectName);
    const templateId = String(options?.templateId || 'template_pce_sample').trim() || 'template_pce_sample';
    return pceBuildSystem.createProjectFromTemplate(path.join(parent, normalizedName), templateId, nextConfig);
  }
  return mdBuildSystem.createProjectInParent(parentDir, projectName, nextConfig, sourceCode, options);
}

function createProjectFromTemplate(projectDir, templateId, config = {}) {
  const coreId = routeCoreForNewProject(config, templateId);
  const nextConfig = withCoreId(config, coreId);
  if (coreId === CORE_IDS.PC_ENGINE) {
    return pceBuildSystem.createProjectFromTemplate(projectDir, templateId || 'template_pce_sample', nextConfig);
  }
  return mdBuildSystem.createProjectFromTemplate(projectDir, templateId, nextConfig);
}

function loadProjectConfig() {
  const projectDir = getProjectDir();
  const coreId = getCoreIdForProjectDir(projectDir);
  return withCoreId(getBuildSystemForCore(coreId).loadProjectConfig(), coreId);
}

function loadProjectConfigFromDir(projectDir) {
  const coreId = getCoreIdForProjectDir(projectDir);
  return withCoreId(getBuildSystemForCore(coreId).loadProjectConfigFromDir(projectDir), coreId);
}

function saveProjectConfig(patch = {}) {
  const coreId = getActiveCoreId();
  return withCoreId(getBuildSystemForCore(coreId).saveProjectConfig(withCoreId(patch, coreId)), coreId);
}

function generateProject(sourceCode, config = {}) {
  const coreId = detectCoreIdFromConfig(config);
  if (coreId === CORE_IDS.PC_ENGINE) {
    return createProject(pceBuildSystem.getDefaultProjectDir(), config, sourceCode);
  }
  return mdBuildSystem.generateProject(sourceCode, withCoreId(config, coreId));
}

function generateProjectStructureOnly(config = {}) {
  const coreId = getActiveCoreId();
  if (coreId === CORE_IDS.PC_ENGINE) {
    return pceBuildSystem.ensureProjectStructure(getProjectDir(), withCoreId({ ...loadProjectConfig(), ...config }, coreId));
  }
  return mdBuildSystem.generateProjectStructureOnly(withCoreId(config, coreId));
}

function loadCurrentSource() {
  return getActiveBuildSystem().loadCurrentSource();
}

function getLastRomPath() {
  return getActiveBuildSystem().getLastRomPath();
}

function getSampleSourceCode() {
  if (getActiveCoreId() === CORE_IDS.PC_ENGINE) {
    const samplePath = path.join(pceBuildSystem.getTemplatesRootDir(), 'template_pce_sample', 'src', 'main.c');
    return fs.existsSync(samplePath) ? fs.readFileSync(samplePath, 'utf-8') : '';
  }
  return mdBuildSystem.getSampleSourceCode();
}

function getPluginRoles() {
  return getActiveBuildSystem().getPluginRoles();
}

function getPluginRole(roleId) {
  return getActiveBuildSystem().getPluginRole(roleId);
}

function setPluginRole(roleId, id) {
  return getActiveBuildSystem().setPluginRole(roleId, id);
}

function buildProject(...args) {
  const coreId = getActiveCoreId();
  if (coreId === CORE_IDS.PC_ENGINE) return pceBuildSystem.buildProject(...args);
  return mdBuildSystem.buildProject(...args);
}

function collectProjectAssets(projectDir = getProjectDir()) {
  const coreId = getCoreIdForProjectDir(projectDir);
  if (coreId === CORE_IDS.PC_ENGINE) {
    return pceAssetManager.listAssets(projectDir).assets;
  }
  return mdRescompManager.listResDefinitions(projectDir);
}

module.exports = {
  CORE_IDS,
  collectProjectAssets,
  createProject,
  createProjectFromTemplate,
  createProjectInParent,
  createProjectInRoot,
  detectCoreIdFromConfig,
  generateProject,
  generateProjectStructureOnly,
  getActiveBuildSystem,
  getActiveCoreId,
  getBuildSystemForCore,
  getCore,
  getCoreIdForProjectDir,
  getDefaultProjectDir: mdBuildSystem.getDefaultProjectDir,
  getLastRomPath,
  getPceSetupManager: () => pceSetupManager,
  getMdSetupManager: () => mdSetupManager,
  getPluginRole,
  getPluginRoles,
  getProjectDir,
  getProjectInfo,
  getProjectsRootDir: mdBuildSystem.getProjectsRootDir,
  getProjectStartupState,
  getSampleSourceCode,
  getSetupManagerForCore,
  getTemplatesRootDir: mdBuildSystem.getTemplatesRootDir,
  listCores,
  listProjects,
  loadCurrentSource,
  loadProjectConfig,
  loadProjectConfigFromDir,
  normalizeCoreId,
  openProject,
  openProjectByName,
  saveProjectConfig,
  setPluginRole,
  setProjectDir,
  buildProject,
};
