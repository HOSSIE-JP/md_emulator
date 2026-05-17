'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { app } = require('electron');
const assetManager = require('./pce-asset-manager');
const setupManager = require('./pce-setup-manager');

const DEFAULT_PROJECT_NAME = 'sample_pce_game';
const TEMPLATE_PROJECT_PREFIX = 'template_';
const DEFAULT_TOOLCHAIN = 'cc65';

function ensureDirSync(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function getProjectsRootDir() {
  return path.join(app.getPath('userData'), 'projects');
}

function getTemplatesRootDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'template');
  }
  return path.join(__dirname, 'template');
}

function getDefaultProjectDir() {
  return path.join(getProjectsRootDir(), DEFAULT_PROJECT_NAME);
}

function getStatePath() {
  return path.join(app.getPath('userData'), 'editor-state.json');
}

function readEditorState() {
  try {
    const statePath = getStatePath();
    if (fs.existsSync(statePath)) return JSON.parse(fs.readFileSync(statePath, 'utf-8'));
  } catch (_) {}
  return {};
}

function writeEditorState(nextState) {
  ensureDirSync(path.dirname(getStatePath()));
  fs.writeFileSync(getStatePath(), JSON.stringify(nextState, null, 2), 'utf-8');
}

function getProjectConfigPath(projectDir) {
  return path.join(path.resolve(projectDir), 'project.json');
}

function hasProjectConfig(projectDir) {
  return fs.existsSync(getProjectConfigPath(projectDir));
}

function normalizeToolchain(value) {
  return value === 'llvm-mos' ? 'llvm-mos' : 'cc65';
}

function normalizeProjectConfig(config = {}) {
  const romName = String(config.romName || config.title || 'pce_sample').trim() || 'pce_sample';
  const pluginRoles = config.pluginRoles && typeof config.pluginRoles === 'object'
    ? { ...config.pluginRoles }
    : {};
  return {
    coreId: 'pc-engine',
    platform: 'pce',
    title: String(config.title || romName).trim() || romName,
    author: String(config.author || 'AUTHOR').trim() || 'AUTHOR',
    serial: String(config.serial || 'PCE0000000000').trim() || 'PCE0000000000',
    region: String(config.region || 'JUE').trim() || 'JUE',
    romName,
    toolchain: normalizeToolchain(config.toolchain || DEFAULT_TOOLCHAIN),
    pluginRoles: {
      builder: 'pce-sample-builder',
      testplay: 'pce-standard-emulator',
      ...pluginRoles,
    },
    pluginSettings: config.pluginSettings && typeof config.pluginSettings === 'object'
      ? { ...config.pluginSettings }
      : {},
    generatedAt: config.generatedAt || new Date().toISOString(),
  };
}

function loadProjectConfigFromDir(projectDir) {
  const cfgPath = getProjectConfigPath(projectDir);
  if (!fs.existsSync(cfgPath)) return normalizeProjectConfig();
  try {
    return normalizeProjectConfig(JSON.parse(fs.readFileSync(cfgPath, 'utf-8')));
  } catch (_) {
    return normalizeProjectConfig();
  }
}

function loadProjectConfig() {
  return loadProjectConfigFromDir(getProjectDir());
}

function saveProjectConfig(patch = {}) {
  const projectDir = getProjectDir();
  ensureDirSync(projectDir);
  const current = loadProjectConfigFromDir(projectDir);
  const next = normalizeProjectConfig({
    ...current,
    ...patch,
    pluginRoles: {
      ...(current.pluginRoles || {}),
      ...(patch.pluginRoles || {}),
    },
    pluginSettings: {
      ...(current.pluginSettings || {}),
      ...(patch.pluginSettings || {}),
    },
  });
  fs.writeFileSync(getProjectConfigPath(projectDir), JSON.stringify(next, null, 2), 'utf-8');
  return next;
}

function getPluginRoles() {
  return loadProjectConfig().pluginRoles || {};
}

function getPluginRole(roleId) {
  return getPluginRoles()[roleId] || null;
}

function setPluginRole(roleId, pluginId) {
  const roles = { ...getPluginRoles() };
  if (pluginId) roles[roleId] = pluginId;
  else delete roles[roleId];
  return saveProjectConfig({ pluginRoles: roles });
}

function ensureProjectsRootDir() {
  const root = getProjectsRootDir();
  ensureDirSync(root);
  return root;
}

function getProjectDir() {
  const state = readEditorState();
  if (state.currentProjectDir && fs.existsSync(state.currentProjectDir) && hasProjectConfig(state.currentProjectDir)) {
    return path.resolve(state.currentProjectDir);
  }
  const defaultProjectDir = getDefaultProjectDir();
  if (fs.existsSync(defaultProjectDir) && hasProjectConfig(defaultProjectDir)) {
    return defaultProjectDir;
  }
  return defaultProjectDir;
}

function setProjectDir(projectDir) {
  const resolved = path.resolve(projectDir);
  const state = readEditorState();
  writeEditorState({
    ...state,
    currentProjectDir: resolved,
  });
  return resolved;
}

function normalizeProjectName(projectName) {
  const normalizedName = String(projectName || '').trim();
  if (!normalizedName) throw new Error('project name is empty');
  if (normalizedName === '.' || normalizedName === '..' || normalizedName.includes('..') || /[\\/:*?"<>|]/.test(normalizedName)) {
    throw new Error(`invalid project name: ${normalizedName}`);
  }
  return normalizedName;
}

function ensureProjectStructure(projectDir, config = {}) {
  ensureDirSync(projectDir);
  ensureDirSync(path.join(projectDir, 'src'));
  ensureDirSync(path.join(projectDir, 'src', 'generated'));
  ensureDirSync(path.join(projectDir, 'assets'));
  ensureDirSync(path.join(projectDir, 'out'));
  const cfgPath = getProjectConfigPath(projectDir);
  if (!fs.existsSync(cfgPath)) {
    fs.writeFileSync(cfgPath, JSON.stringify(normalizeProjectConfig(config), null, 2), 'utf-8');
  }
  assetManager.ensureAssetFile(projectDir);
  return { projectDir, configPath: cfgPath };
}

function copyTemplateProject(templateDir, targetDir) {
  ensureDirSync(targetDir);
  fs.readdirSync(templateDir, { withFileTypes: true }).forEach((entry) => {
    if (entry.name === 'out') return;
    const source = path.join(templateDir, entry.name);
    const target = path.join(targetDir, entry.name);
    if (entry.isDirectory()) {
      copyTemplateProject(source, target);
    } else if (entry.isFile()) {
      ensureDirSync(path.dirname(target));
      fs.copyFileSync(source, target);
    }
  });
}

function resolveTemplateProjectDir(templateId) {
  const normalizedId = normalizeProjectName(templateId || 'template_pce_sample');
  if (!normalizedId.startsWith(TEMPLATE_PROJECT_PREFIX)) {
    throw new Error(`invalid template project: ${normalizedId}`);
  }
  const templateDir = path.join(getTemplatesRootDir(), normalizedId);
  if (!fs.existsSync(templateDir) || !hasProjectConfig(templateDir)) {
    throw new Error(`template project not found: ${normalizedId}`);
  }
  return templateDir;
}

function createProjectFromTemplate(projectDir, templateId = 'template_pce_sample', config = {}) {
  const resolved = path.resolve(projectDir);
  if (fs.existsSync(resolved) && fs.readdirSync(resolved).length > 0) {
    throw new Error(`project directory already exists and is not empty: ${resolved}`);
  }
  const templateDir = resolveTemplateProjectDir(templateId);
  const templateConfig = loadProjectConfigFromDir(templateDir);
  copyTemplateProject(templateDir, resolved);
  const nextConfig = normalizeProjectConfig({ ...templateConfig, ...config });
  fs.writeFileSync(getProjectConfigPath(resolved), JSON.stringify(nextConfig, null, 2), 'utf-8');
  ensureProjectStructure(resolved, nextConfig);
  setProjectDir(resolved);
  return { projectDir: resolved, config: nextConfig };
}

function createProjectInRoot(projectName = DEFAULT_PROJECT_NAME, config = {}, options = {}) {
  const normalizedName = normalizeProjectName(projectName);
  const projectDir = path.join(ensureProjectsRootDir(), normalizedName);
  return createProjectFromTemplate(projectDir, options.templateId || 'template_pce_sample', config);
}

function ensureDefaultProject() {
  const projectDir = getDefaultProjectDir();
  if (!fs.existsSync(projectDir) || !hasProjectConfig(projectDir)) {
    return createProjectFromTemplate(projectDir, 'template_pce_sample', {});
  }
  setProjectDir(projectDir);
  return { projectDir, config: loadProjectConfigFromDir(projectDir) };
}

function listProjectTemplates() {
  const root = getTemplatesRootDir();
  if (!fs.existsSync(root)) return [];
  return fs.readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith(TEMPLATE_PROJECT_PREFIX))
    .filter((entry) => hasProjectConfig(path.join(root, entry.name)))
    .map((entry) => {
      const projectDir = path.join(root, entry.name);
      const cfg = loadProjectConfigFromDir(projectDir);
      return {
        templateId: entry.name,
        projectDir,
        title: cfg.title,
        toolchain: cfg.toolchain,
      };
    });
}

function listProjects() {
  const root = ensureProjectsRootDir();
  const currentProjectDir = path.resolve(getProjectDir());
  const projects = fs.readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .filter((entry) => hasProjectConfig(path.join(root, entry.name)))
    .map((entry) => {
      const projectDir = path.join(root, entry.name);
      const cfg = loadProjectConfigFromDir(projectDir);
      return {
        projectDir,
        projectName: entry.name,
        title: cfg.title,
        toolchain: cfg.toolchain,
        current: path.resolve(projectDir) === currentProjectDir,
      };
    });
  return { projectsRootDir: root, currentProjectDir, projects, templates: listProjectTemplates() };
}

function openProject(projectDir) {
  const resolved = path.resolve(projectDir);
  if (!fs.existsSync(resolved) || !hasProjectConfig(resolved)) {
    throw new Error(`project.json not found: ${resolved}`);
  }
  ensureProjectStructure(resolved, loadProjectConfigFromDir(resolved));
  setProjectDir(resolved);
  return getProjectInfo();
}

function getProjectInfo() {
  const projectDir = getProjectDir();
  const cfg = loadProjectConfigFromDir(projectDir);
  return {
    projectDir,
    projectName: path.basename(projectDir),
    title: cfg.title,
    romName: cfg.romName,
    toolchain: cfg.toolchain,
    projectsRootDir: ensureProjectsRootDir(),
  };
}

function sanitizeRomName(value) {
  const name = String(value || 'pce_sample').replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '');
  return name || 'pce_sample';
}

function postprocessCc65PceRom(inputPath, outputPath) {
  const data = fs.readFileSync(inputPath);
  if (data.length < 8192 || data.length % 8192 !== 0) {
    fs.copyFileSync(inputPath, outputPath);
    return { inputSize: data.length, outputSize: data.length, rearranged: false };
  }
  const bankSize = 8192;
  const lastBank = data.subarray(data.length - bankSize);
  const rest = data.subarray(0, data.length - bankSize);
  const output = Buffer.concat([lastBank, rest]);
  fs.writeFileSync(outputPath, output);
  return { inputSize: data.length, outputSize: output.length, rearranged: true };
}

function resolveCc65Home(toolPath) {
  if (!toolPath) return null;
  const binDir = path.dirname(path.resolve(toolPath));
  const candidates = [
    path.resolve(binDir, '..', 'share', 'cc65'),
    path.resolve(binDir, '..'),
    path.resolve(binDir, '..', '..', 'share', 'cc65'),
  ];
  return candidates.find((candidate) => (
    fs.existsSync(path.join(candidate, 'include', 'conio.h')) &&
    fs.existsSync(path.join(candidate, 'include', 'pce.h')) &&
    fs.existsSync(path.join(candidate, 'lib', 'pce.lib')) &&
    fs.existsSync(path.join(candidate, 'cfg', 'pce.cfg'))
  )) || null;
}

function buildSpawnEnv(toolPath, toolchain = DEFAULT_TOOLCHAIN) {
  const env = { ...process.env };
  const binDir = toolPath ? path.dirname(toolPath) : '';
  if (binDir) env.PATH = [binDir, env.PATH || ''].filter(Boolean).join(path.delimiter);
  if (toolchain === 'cc65') {
    const cc65Home = resolveCc65Home(toolPath);
    if (cc65Home) env.CC65_HOME = cc65Home;
  }
  return env;
}

function collectSourceFiles(projectDir) {
  const sourceFiles = [
    path.join(projectDir, 'src', 'main.c'),
    path.join(projectDir, 'src', 'generated', 'assets.c'),
  ];
  return sourceFiles.filter((filePath) => fs.existsSync(filePath));
}

function buildCommandForProject(projectDir, config = {}, toolPath = null) {
  const toolchain = normalizeToolchain(config.toolchain);
  const outDir = path.join(projectDir, 'out');
  const romBase = sanitizeRomName(config.romName || config.title);
  ensureDirSync(outDir);
  const sources = collectSourceFiles(projectDir);
  if (toolchain === 'llvm-mos') {
    const command = toolPath || 'mos-pce-clang';
    const romPath = path.join(outDir, `${romBase}.pce`);
    return {
      toolchain,
      command,
      args: ['-Os', '-o', romPath, ...sources],
      cwd: projectDir,
      env: buildSpawnEnv(command, toolchain),
      romPath,
    };
  }
  const command = toolPath || 'cl65';
  const binPath = path.join(outDir, `${romBase}.bin`);
  const romPath = path.join(outDir, `${romBase}.pce`);
  return {
    toolchain,
    command,
    args: ['-t', 'pce', '-O', '-o', binPath, ...sources],
    cwd: projectDir,
    env: buildSpawnEnv(command, toolchain),
    binPath,
    romPath,
  };
}

function buildProject(onLog, options = {}) {
  return new Promise((resolve) => {
    const projectDir = getProjectDir();
    ensureProjectStructure(projectDir, loadProjectConfigFromDir(projectDir));
    const config = normalizeProjectConfig({ ...loadProjectConfigFromDir(projectDir), ...options.config });
    const log = (message, level = 'info') => onLog?.(String(message), level);
    let generated;
    try {
      generated = assetManager.generateAssetSources(projectDir);
    } catch (err) {
      resolve({ success: false, error: `asset generation failed: ${err.message || err}` });
      return;
    }

    const toolPath = setupManager.getToolchainPath(config.toolchain);
    if (!toolPath && !options.allowMissingToolchain) {
      resolve({ success: false, error: `${config.toolchain} toolchain is not configured. Setup を実行してください。` });
      return;
    }

    const commandInfo = buildCommandForProject(projectDir, config, toolPath);
    log(`Generated assets: ${generated.assetCount} assets`);
    log(`Build command: ${commandInfo.command} ${commandInfo.args.join(' ')}`);

    if (options.dryRun) {
      resolve({ success: true, dryRun: true, commandInfo, generated });
      return;
    }

    const proc = spawn(commandInfo.command, commandInfo.args, {
      cwd: commandInfo.cwd,
      env: commandInfo.env,
      windowsHide: true,
    });

    proc.stdout.on('data', (data) => data.toString().split(/\r?\n/).filter(Boolean).forEach((line) => log(line, 'info')));
    proc.stderr.on('data', (data) => data.toString().split(/\r?\n/).filter(Boolean).forEach((line) => log(line, 'error')));
    proc.on('error', (err) => resolve({ success: false, error: err.message || String(err), commandInfo }));
    proc.on('exit', (code) => {
      if (code !== 0) {
        resolve({ success: false, error: `build failed (exit code: ${code})`, commandInfo });
        return;
      }
      try {
        let romInfo = null;
        if (commandInfo.toolchain === 'cc65') {
          romInfo = postprocessCc65PceRom(commandInfo.binPath, commandInfo.romPath);
        }
        const romSize = fs.existsSync(commandInfo.romPath) ? fs.statSync(commandInfo.romPath).size : 0;
        resolve({ success: true, romPath: commandInfo.romPath, romSize, commandInfo, romInfo });
      } catch (err) {
        resolve({ success: false, error: err.message || String(err), commandInfo });
      }
    });
  });
}

function getLastRomPath() {
  const config = loadProjectConfig();
  const romPath = path.join(getProjectDir(), 'out', `${sanitizeRomName(config.romName || config.title)}.pce`);
  return fs.existsSync(romPath) ? romPath : null;
}

function loadCurrentSource() {
  const srcPath = path.join(getProjectDir(), 'src', 'main.c');
  if (fs.existsSync(srcPath)) {
    return fs.readFileSync(srcPath, 'utf-8');
  }
  return null;
}

module.exports = {
  DEFAULT_PROJECT_NAME,
  DEFAULT_TOOLCHAIN,
  buildCommandForProject,
  buildProject,
  createProjectFromTemplate,
  createProjectInRoot,
  ensureDefaultProject,
  ensureProjectStructure,
  getDefaultProjectDir,
  getLastRomPath,
  getPluginRole,
  getPluginRoles,
  getProjectConfigPath,
  getProjectDir,
  getProjectInfo,
  getProjectsRootDir,
  getStatePath,
  getTemplatesRootDir,
  hasProjectConfig,
  listProjects,
  listProjectTemplates,
  loadCurrentSource,
  loadProjectConfig,
  loadProjectConfigFromDir,
  normalizeProjectConfig,
  normalizeProjectName,
  normalizeToolchain,
  openProject,
  postprocessCc65PceRom,
  resolveCc65Home,
  saveProjectConfig,
  setPluginRole,
  setProjectDir,
};
