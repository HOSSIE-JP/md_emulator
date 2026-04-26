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

function getProjectDir() {
  return path.join(app.getPath('userData'), 'project');
}

function ensureDirSync(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
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
  ensureDirSync(path.join(projectDir, 'src'));
  ensureDirSync(path.join(projectDir, 'res'));
  ensureDirSync(path.join(projectDir, 'out'));

  // main.c
  fs.writeFileSync(path.join(projectDir, 'src', 'main.c'), sourceCode, 'utf-8');

  // res/resources.res (空でも SGDK は通る)
  const resPath = path.join(projectDir, 'res', 'resources.res');
  if (!fs.existsSync(resPath)) {
    fs.writeFileSync(resPath, '', 'utf-8');
  }

  // メタ情報を保存（必要な場合に使用）
  const meta = {
    title: config.title || config.romName || 'MY GAME',
    author: config.author || 'AUTHOR',
    serial: config.serial || 'GM 00000000-00',
    region: 'JUE',
    generatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(projectDir, 'project.json'), JSON.stringify(meta, null, 2), 'utf-8');

  return { projectDir, srcPath: path.join(projectDir, 'src', 'main.c') };
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
      args = ['-f', makefileGen.replace(/\//g, '\\'), `GDK=${sgdkPosix}`, `GDK_WIN=${sgdkWin}`, 'release'];
    } else {
      command = resolveMakeCommand(buildPaths.sgdkPath, false);
      args = ['-f', makefileGen, `GDK=${buildPaths.sgdkPath}`, 'release'];
    }

    log(`ビルドを開始: ${command} ${args.join(' ')}`);
    log(`プロジェクトDir: ${projectDir}`);
    if (buildPaths.projectDir !== projectDir || buildPaths.sgdkPath !== toolchainPath) {
      log(`ビルド用エイリアスを使用: project=${buildPaths.projectDir}, gdk=${buildPaths.sgdkPath}`);
    }

    const proc = spawn(command, args, {
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
        if (line.trim()) log(line, 'error');
      });
    });

    proc.on('exit', (code) => {
      if (code === 0) {
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
        const msg = `ビルド失敗 (exit code: ${code})`;
        log(msg, 'error');
        resolve({ success: false, error: msg });
      }
    });

    proc.on('error', (err) => {
      const msg = `ビルドプロセスの起動に失敗: ${err.message}`;
      log(msg, 'error');
      resolve({ success: false, error: msg });
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

function loadProjectConfig() {
  const cfgPath = path.join(getProjectDir(), 'project.json');
  if (fs.existsSync(cfgPath)) {
    try { return JSON.parse(fs.readFileSync(cfgPath, 'utf-8')); }
    catch { return {}; }
  }
  return {};
}

module.exports = {
  getProjectDir,
  generateProject,
  buildProject,
  loadCurrentSource,
  getLastRomPath,
  loadProjectConfig,
};
