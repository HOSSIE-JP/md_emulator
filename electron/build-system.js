'use strict';

/**
 * build-system.js
 * SGDK を使ったメガドライブゲームのビルドシステム
 * Main process 専用モジュール
 */

const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { app } = require('electron');
const setupManager = require('./setup-manager');

function getProjectsRootDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'projects');
  }
  return path.join(__dirname, 'projects');
}

function getLegacySampleProjectDir() {
  return path.join(__dirname, 'sample');
}

function getDefaultProjectDir() {
  return path.join(getProjectsRootDir(), 'sample');
}

function getStatePath() {
  return path.join(app.getPath('userData'), 'editor-state.json');
}

function readEditorState() {
  const statePath = getStatePath();
  if (!fs.existsSync(statePath)) {
    return {};
  }
  try {
    return JSON.parse(fs.readFileSync(statePath, 'utf-8'));
  } catch (_err) {
    return {};
  }
}

function writeEditorState(nextState) {
  const statePath = getStatePath();
  ensureDirSync(path.dirname(statePath));
  fs.writeFileSync(statePath, JSON.stringify(nextState, null, 2), 'utf-8');
}

function getProjectDir() {
  const state = readEditorState();
  if (state.currentProjectDir && fs.existsSync(state.currentProjectDir)) {
    return state.currentProjectDir;
  }

  const defaultProjectDir = getDefaultProjectDir();
  if (fs.existsSync(defaultProjectDir)) {
    return defaultProjectDir;
  }

  const legacySampleDir = getLegacySampleProjectDir();
  if (fs.existsSync(legacySampleDir)) {
    return legacySampleDir;
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

function ensureDirSync(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function ensureProjectsRootDir() {
  const root = getProjectsRootDir();
  ensureDirSync(root);
  return root;
}

function toAsciiPrintable(value) {
  return String(value || '').replace(/[^\x20-\x7E]/g, ' ');
}

function fitFixed(value, length) {
  const s = toAsciiPrintable(value);
  if (s.length >= length) {
    return s.slice(0, length);
  }
  return s.padEnd(length, ' ');
}

function buildRomHeaderSource(config = {}) {
  const title = fitFixed(config.title || config.romName || 'MY GAME', 48);
  const serial = fitFixed(config.serial || 'GM 00000000-00', 14);
  const region = fitFixed(config.region || 'JUE', 16);
  const author = fitFixed(config.author || 'AUTHOR', 10);
  const copyright = fitFixed(`(C)${author}`, 16);
  const memo = fitFixed(`${title.slice(0, 32)} PROGRAM`, 40);

  return `#include "genesis.h"

__attribute__((externally_visible))
const ROMHeader rom_header = {
#if (ENABLE_BANK_SWITCH != 0)
    "SEGA SSF        ",
#elif (MODULE_MEGAWIFI != 0)
    "SEGA MEGAWIFI   ",
#else
    "SEGA MEGA DRIVE ",
#endif
    "${copyright}",
    "${title}",
    "${title}",
    "${serial}",
    0x000,
    "JD              ",
    0x00000000,
#if (ENABLE_BANK_SWITCH != 0)
    0x003FFFFF,
#else
    0x000FFFFF,
#endif
    0xE0FF0000,
    0xE0FFFFFF,
    "RA",
    0xF820,
    0x00200000,
    0x0020FFFF,
    "            ",
    "${memo}",
    "${region}"
};
`;
}

function getSampleSourcePath() {
  const currentRootSample = path.join(getProjectsRootDir(), 'sample', 'src', 'main.c');
  if (fs.existsSync(currentRootSample)) {
    return currentRootSample;
  }
  return path.join(getLegacySampleProjectDir(), 'src', 'main.c');
}

function getSampleSourceCode() {
  const samplePath = getSampleSourcePath();
  if (fs.existsSync(samplePath)) {
    return fs.readFileSync(samplePath, 'utf-8');
  }
  return 'int main(void) { return 0; }\n';
}

function ensureProjectStructure(projectDir, config = {}, options = {}) {
  ensureDirSync(projectDir);
  ensureDirSync(path.join(projectDir, 'src'));
  ensureDirSync(path.join(projectDir, 'src', 'boot'));
  ensureDirSync(path.join(projectDir, 'res'));
  ensureDirSync(path.join(projectDir, 'out'));

  const srcPath = path.join(projectDir, 'src', 'main.c');
  const resPath = path.join(projectDir, 'res', 'resources.res');
  const romHeadPath = path.join(projectDir, 'src', 'boot', 'rom_head.c');

  if (options.overwriteSource || !fs.existsSync(srcPath)) {
    fs.writeFileSync(srcPath, options.sourceCode || getSampleSourceCode(), 'utf-8');
  }

  if (!fs.existsSync(resPath)) {
    fs.writeFileSync(resPath, '', 'utf-8');
  }

  if (options.overwriteRomHeader || !fs.existsSync(romHeadPath)) {
    fs.writeFileSync(romHeadPath, buildRomHeaderSource(config), 'utf-8');
  }

  const meta = {
    title: config.title || config.romName || 'MY GAME',
    author: config.author || 'AUTHOR',
    serial: config.serial || 'GM 00000000-00',
    region: config.region || 'JUE',
    generatedAt: new Date().toISOString(),
  };
  const cfgPath = path.join(projectDir, 'project.json');
  if (options.overwriteConfig || !fs.existsSync(cfgPath)) {
    let existing = {};
    if (fs.existsSync(cfgPath)) {
      try {
        existing = JSON.parse(fs.readFileSync(cfgPath, 'utf-8')) || {};
      } catch (_) {
        existing = {};
      }
    }
    const merged = Object.assign({}, existing, meta);
    fs.writeFileSync(cfgPath, JSON.stringify(merged, null, 2), 'utf-8');
  }

  return { projectDir, srcPath, resPath, romHeadPath, configPath: cfgPath };
}

function getProjectInfo() {
  const projectDir = getProjectDir();
  const config = loadProjectConfig();
  return {
    projectDir,
    projectName: path.basename(projectDir),
    title: config.title || config.romName || 'MY GAME',
    defaultProjectDir: getDefaultProjectDir(),
    projectsRootDir: ensureProjectsRootDir(),
  };
}

function listProjects() {
  const root = ensureProjectsRootDir();
  const currentProjectDir = path.resolve(getProjectDir());
  const projects = fs.readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const projectDir = path.join(root, entry.name);
      const config = loadProjectConfigFromDir(projectDir);
      return {
        projectDir,
        projectName: entry.name,
        title: config.title || config.romName || entry.name,
        current: path.resolve(projectDir) === currentProjectDir,
      };
    })
    .sort((left, right) => left.projectName.localeCompare(right.projectName, 'ja'));

  return {
    projectsRootDir: root,
    currentProjectDir,
    projects,
  };
}

function createProject(projectDir, config = {}, sourceCode) {
  const resolved = path.resolve(projectDir);
  if (fs.existsSync(resolved)) {
    const children = fs.readdirSync(resolved);
    if (children.length > 0) {
      throw new Error(`project directory already exists and is not empty: ${resolved}`);
    }
  }

  const result = ensureProjectStructure(resolved, config, {
    sourceCode: sourceCode || getSampleSourceCode(),
    overwriteSource: true,
    overwriteRomHeader: true,
    overwriteConfig: true,
  });
  setProjectDir(resolved);
  return result;
}

function createProjectInRoot(projectName, config = {}, sourceCode) {
  const normalizedName = String(projectName || '').trim();
  if (!normalizedName) {
    throw new Error('project name is empty');
  }
  if (normalizedName.includes('..') || /[\\/:*?"<>|]/.test(normalizedName)) {
    throw new Error(`invalid project name: ${normalizedName}`);
  }

  const projectDir = path.join(ensureProjectsRootDir(), normalizedName);
  return createProject(projectDir, config, sourceCode);
}

function openProject(projectDir) {
  const resolved = path.resolve(projectDir);
  if (!fs.existsSync(resolved)) {
    throw new Error(`project directory not found: ${resolved}`);
  }

  const cfg = loadProjectConfigFromDir(resolved);
  ensureProjectStructure(resolved, cfg, {
    overwriteSource: false,
    overwriteRomHeader: false,
    overwriteConfig: false,
  });
  setProjectDir(resolved);
  return getProjectInfo();
}

function openProjectByName(projectName) {
  const normalizedName = String(projectName || '').trim();
  if (!normalizedName) {
    throw new Error('project name is empty');
  }
  return openProject(path.join(ensureProjectsRootDir(), normalizedName));
}

function getBuildRuntimeDir() {
  return path.join(app.getPath('home'), '.md-game-editor-runtime');
}

function ensurePathAlias(targetPath, aliasPath) {
  const resolvedTarget = path.resolve(targetPath);
  ensureDirSync(path.dirname(aliasPath));

  if (fs.existsSync(aliasPath)) {
    try {
      const resolvedAlias = fs.realpathSync(aliasPath);
      if (resolvedAlias === resolvedTarget) {
        return aliasPath;
      }
    } catch (_err) {
      // recreate below
    }
    fs.rmSync(aliasPath, { recursive: true, force: true });
  }

  fs.symlinkSync(
    resolvedTarget,
    aliasPath,
    process.platform === 'win32' ? 'junction' : 'dir'
  );
  return aliasPath;
}

function createBuildPaths(projectDir, sgdkPath) {
  const runtimeDir = getBuildRuntimeDir();
  ensureDirSync(runtimeDir);

  if (!/\s/.test(projectDir) && !/\s/.test(sgdkPath)) {
    return { projectDir, sgdkPath };
  }

  return {
    projectDir: ensurePathAlias(projectDir, path.join(runtimeDir, 'project')),
    sgdkPath: ensurePathAlias(sgdkPath, path.join(runtimeDir, 'sgdk')),
  };
}

function resolveMakeCommand(toolchainPath, isWin) {
  if (!toolchainPath) return 'make';

  // Detect if this is Marsdev or SGDK by checking for marsdev-specific binaries
  const isMarsdev = toolchainPath.includes('marsdev');

  let candidates;
  if (isMarsdev || !isWin) {
    // Marsdev or Unix-like: native binaries (no .exe)
    candidates = [
      path.join(toolchainPath, 'bin', 'make'),
      path.join(toolchainPath, 'make'),
    ];
  } else {
    // Windows SGDK: .exe binaries
    candidates = [
      path.join(toolchainPath, 'bin', 'make', 'make.exe'),
      path.join(toolchainPath, 'bin', 'make.exe'),
    ];
  }

  for (const p of candidates) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return 'make';
}

// -------------------------------------------------------------- generation --

/**
 * SGDK プロジェクトのファイル構成を生成する
 * @param {string} sourceCode - main.c のソースコード
 * @param {object} config     - { title, author, serial, region }
 */
function generateProject(sourceCode, config = {}) {
  const projectDir = getProjectDir();
  const result = ensureProjectStructure(projectDir, config, {
    sourceCode,
    overwriteSource: true,
    overwriteRomHeader: true,
    overwriteConfig: true,
  });
  return { projectDir, srcPath: result.srcPath };
}

/**
 * src/main.c を上書きせずプロジェクト構造 (Makefile, rom_header.s 等) だけ整備する。
 * プラグイン生成済みソースをそのままビルドするときに使う。
 * @param {object} config - { title, author, serial, region }
 */
function generateProjectStructureOnly(config = {}) {
  const projectDir = getProjectDir();
  const result = ensureProjectStructure(projectDir, config, {
    overwriteSource: false,
    overwriteRomHeader: true,
    overwriteConfig: true,
  });
  return { projectDir, srcPath: result.srcPath };
}

// ------------------------------------------------------------------- build --

/**
 * SGDK ビルドを実行する
 * @param {string} sgdkPath     - SGDK のルートディレクトリ
 * @param {string} javaPath     - java 実行ファイルのパス（または 'java'）
 * @param {function} onLog      - (line: string, level: 'info'|'error') => void
 * @returns {Promise<{success, romPath, romSize, error}>}
 */
function buildProject(sgdkPath, javaPath, onLog) {
  return new Promise((resolve) => {
    const projectDir = getProjectDir();
    const log = (msg, level = 'info') => onLog && onLog(msg, level);

    // If no sgdkPath provided, auto-detect the active toolchain
    let toolchainPath = sgdkPath;
    if (!toolchainPath) {
      toolchainPath = setupManager.getToolchainDir();
    }

    if (!toolchainPath || !fs.existsSync(toolchainPath)) {
      const msg = `ツールチェーンが見つかりません: ${toolchainPath || '(未設定)'}. SGDK または Marsdev をセットアップしてください。`;
      log(msg, 'error');
      resolve({ success: false, error: msg });
      return;
    }

    let buildPaths = { projectDir, sgdkPath: toolchainPath };
    try {
      buildPaths = createBuildPaths(projectDir, toolchainPath);
    } catch (err) {
      log(`ビルド用エイリアスの作成に失敗したため元のパスを使用します: ${err.message}`, 'error');
    }

    // macOS + Marsdev: dyld エラーを避けるため、実行前に gettext 参照の整合性を確認・補正する。
    if (process.platform === 'darwin') {
      let isMarsdevBuild = false;
      try {
        const marsdevPath = setupManager.getMarsdevPath();
        if (marsdevPath) {
          const realBuildPath = fs.realpathSync(buildPaths.sgdkPath);
          const realMarsdevPath = fs.realpathSync(marsdevPath);
          isMarsdevBuild = realBuildPath === realMarsdevPath;
        }
      } catch (_err) {
        // realpath 失敗時は Marsdev 判定不可としてスキップ
      }

      if (isMarsdevBuild) {
        const fix = setupManager.fixMarsdevMacosGettext(buildPaths.sgdkPath);
        if (!fix.ok) {
          const msg = `Marsdev 実行前チェックに失敗: ${fix.error}`;
          log(msg, 'error');
          resolve({ success: false, error: msg });
          return;
        }
        if (fix.patched > 0) {
          log(`Marsdev の macOS ライブラリ参照を自動修正しました (${fix.patched} files)`);
        }
      }
    }

    const makefileGen = path.join(buildPaths.sgdkPath, 'makefile.gen');
    if (!fs.existsSync(makefileGen)) {
      const msg = `makefile.gen が見つかりません: ${makefileGen}`;
      log(msg, 'error');
      resolve({ success: false, error: msg });
      return;
    }

    const outDir = path.join(projectDir, 'out');
    ensureDirSync(outDir);

    const isWin = process.platform === 'win32';
    let command, args, spawnEnv;

    // ツールチェーン内のバイナリをPATHに追加
    spawnEnv = { ...process.env };
    const pathParts = [
      path.join(buildPaths.sgdkPath, 'bin'),
      spawnEnv.PATH || '',
    ];
    if (isWin) {
      pathParts.splice(1, 0, path.join(buildPaths.sgdkPath, 'bin', 'gcc', 'bin'));
    }
    spawnEnv.PATH = pathParts.filter(Boolean).join(path.delimiter);

    // 環境変数に java パスを追加
    if (javaPath && javaPath !== 'java') {
      spawnEnv.JAVA_HOME = path.dirname(path.dirname(javaPath));
      spawnEnv.PATH = `${path.dirname(javaPath)}${path.delimiter}${spawnEnv.PATH}`;
    }

    if (isWin) {
      command = resolveMakeCommand(buildPaths.sgdkPath, true);
      // `makefile.gen` runs many tools through sh, so GDK must use POSIX-style separators on Windows.
      const sgdkPosix = buildPaths.sgdkPath.replace(/\\/g, '/');
      const sgdkWin = buildPaths.sgdkPath.replace(/\//g, '\\');
      args = ['-f', makefileGen.replace(/\//g, '\\'), `GDK=${sgdkPosix}`, `GDK_WIN=${sgdkWin}`];
    } else {
      command = resolveMakeCommand(buildPaths.sgdkPath, false);
      args = ['-f', makefileGen, `GDK=${buildPaths.sgdkPath}`];
    }

    log(`プロジェクトDir: ${projectDir}`);
    if (buildPaths.projectDir !== projectDir || buildPaths.sgdkPath !== toolchainPath) {
      log(`ビルド用エイリアスを使用: project=${buildPaths.projectDir}, gdk=${buildPaths.sgdkPath}`);
    }

    function runMakeTarget(target, onExit) {
      const targetArgs = [...args, target];
      log(`${target.toUpperCase()} を開始: ${command} ${targetArgs.join(' ')}`);

      const proc = spawn(command, targetArgs, {
        cwd: buildPaths.projectDir,
        env: spawnEnv,
        windowsHide: true,
      });

      proc.stdout.on('data', (data) => {
        data.toString().split('\n').forEach((line) => {
          if (line.trim()) log(line, 'info');
        });
      });

      proc.stderr.on('data', (data) => {
        data.toString().split('\n').forEach((line) => {
          if (!line.trim()) return;
          // SGDK / make が内部的に無視する行はエラー表示しない
          // 例: make[1]: [<tmp>.o] Error 127 (ignored)
          if (/Error\s+\d+\s+\(ignored\)/i.test(line)) {
            log(line, 'info');
            return;
          }
          log(line, 'error');
        });
      });

      proc.on('error', (err) => {
        const msg = `${target.toUpperCase()} プロセスの起動に失敗: ${err.message}`;
        log(msg, 'error');
        resolve({ success: false, error: msg });
      });

      proc.on('exit', (code) => {
        onExit(code);
      });
    }

    runMakeTarget('clean', (cleanCode) => {
      if (cleanCode !== 0) {
        const msg = `CLEAN 失敗 (exit code: ${cleanCode})`;
        log(msg, 'error');
        resolve({ success: false, error: msg });
        return;
      }

      runMakeTarget('release', (releaseCode) => {
        if (releaseCode === 0) {
          const romCandidates = [
            path.join(outDir, 'rom.bin'),
            path.join(buildPaths.projectDir, 'out', 'rom.bin'),
          ];
          const romPath = romCandidates.find((p) => fs.existsSync(p));
          let romSize = null;
          if (romPath) {
            romSize = fs.statSync(romPath).size;
            log(`ビルド成功! ROM: ${romPath} (${(romSize / 1024).toFixed(1)} KB)`);
            resolve({ success: true, romPath, romSize });
          } else {
            const msg = 'ビルドは成功しましたが rom.bin が見つかりません';
            log(msg, 'error');
            resolve({ success: false, error: msg });
          }
        } else {
          const msg = `ビルド失敗 (exit code: ${releaseCode})`;
          log(msg, 'error');
          resolve({ success: false, error: msg });
        }
      });
    });
  });
}

// ---------------------------------------------------------- source loading --

function loadCurrentSource() {
  const srcPath = path.join(getProjectDir(), 'src', 'main.c');
  if (fs.existsSync(srcPath)) {
    return fs.readFileSync(srcPath, 'utf-8');
  }
  return null;
}

function getLastRomPath() {
  const romPath = path.join(getProjectDir(), 'out', 'rom.bin');
  return fs.existsSync(romPath) ? romPath : null;
}

function loadProjectConfigFromDir(projectDir) {
  const cfgPath = path.join(projectDir, 'project.json');
  if (fs.existsSync(cfgPath)) {
    try { return JSON.parse(fs.readFileSync(cfgPath, 'utf-8')); }
    catch { return {}; }
  }
  return {};
}

function loadProjectConfig() {
  return loadProjectConfigFromDir(getProjectDir());
}

function saveProjectConfig(patch) {
  const projectDir = getProjectDir();
  ensureDirSync(projectDir);
  const cfgPath = path.join(projectDir, 'project.json');
  const current = loadProjectConfig();
  const merged = Object.assign({}, current, patch);
  fs.writeFileSync(cfgPath, JSON.stringify(merged, null, 2), 'utf-8');
  return merged;
}

/** プロジェクト毎のビルダープラグイン ID を取得 (未設定なら null) */
function getBuilderPlugin() {
  const cfg = loadProjectConfig();
  return cfg.builderPlugin || null;
}

/** プロジェクト毎のビルダープラグイン ID を保存 */
function setBuilderPlugin(id) {
  saveProjectConfig({ builderPlugin: id || null });
}

/** プロジェクト毎のエミュレータープラグイン ID を取得 (未設定なら null) */
function getEmulatorPlugin() {
  const cfg = loadProjectConfig();
  return cfg.emulatorPlugin || null;
}

/** プロジェクト毎のエミュレータープラグイン ID を保存 */
function setEmulatorPlugin(id) {
  saveProjectConfig({ emulatorPlugin: id || null });
}

module.exports = {
  getDefaultProjectDir,
  getProjectDir,
  setProjectDir,
  getProjectInfo,
  getProjectsRootDir,
  listProjects,
  createProject,
  createProjectInRoot,
  openProject,
  openProjectByName,
  generateProject,
  generateProjectStructureOnly,
  buildProject,
  loadCurrentSource,
  getLastRomPath,
  loadProjectConfig,
  saveProjectConfig,
  getBuilderPlugin,
  setBuilderPlugin,
  getEmulatorPlugin,
  setEmulatorPlugin,
  getSampleSourceCode,
};
