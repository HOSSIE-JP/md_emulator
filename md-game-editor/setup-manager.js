'use strict';

/**
 * setup-manager.js
 * SGDK / Java の存在確認・自動ダウンロード・セットアップ管理
 * Main process 専用モジュール
 */

const path = require('path');
const fs = require('fs');
const https = require('https');
const { execSync } = require('child_process');
const { app } = require('electron');

const SGDK_OWNER = 'Stephane-D';
const SGDK_REPO = 'SGDK';
const MARSDEV_OWNER = 'andwn';
const MARSDEV_REPO = 'marsdev';

// ------------------------------------------------------------------ paths --

function getToolsDir() {
  return path.join(app.getPath('userData'), 'tools');
}

function getSgdkBaseDir() {
  return path.join(getToolsDir(), 'sgdk');
}

function getJreBaseDir() {
  return path.join(getToolsDir(), 'jre');
}

function getMarsdevBaseDir() {
  return path.join(getToolsDir(), 'marsdev');
}

function getSettingsPath() {
  return path.join(getToolsDir(), 'settings.json');
}

const TESTPLAY_ACTIONS = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'A', 'B', 'C', 'START'];
const TESTPLAY_VRAM_LAYOUTS = ['256x512', '512x256', '128x1024', '1024x128'];
const DEFAULT_TESTPLAY_SETTINGS = Object.freeze({
  keyboard: Object.freeze({
    UP: 'ArrowUp',
    DOWN: 'ArrowDown',
    LEFT: 'ArrowLeft',
    RIGHT: 'ArrowRight',
    A: 'KeyA',
    B: 'KeyZ',
    C: 'KeyX',
    START: 'Enter',
  }),
  gamepad: Object.freeze({
    UP: 'button:12',
    DOWN: 'button:13',
    LEFT: 'button:14',
    RIGHT: 'button:15',
    A: 'button:2',
    B: 'button:0',
    C: 'button:1',
    START: 'button:9',
  }),
  gamepadDeadzone: 0.5,
  debug: Object.freeze({
    autoRefresh: true,
    vramTileLayout: '256x512',
  }),
});

function cloneDefaultTestPlaySettings() {
  return {
    keyboard: { ...DEFAULT_TESTPLAY_SETTINGS.keyboard },
    gamepad: { ...DEFAULT_TESTPLAY_SETTINGS.gamepad },
    gamepadDeadzone: DEFAULT_TESTPLAY_SETTINGS.gamepadDeadzone,
    debug: { ...DEFAULT_TESTPLAY_SETTINGS.debug },
  };
}

function normalizeBindingMap(candidate, fallback) {
  const result = { ...fallback };
  if (!candidate || typeof candidate !== 'object') {
    return result;
  }
  for (const action of TESTPLAY_ACTIONS) {
    const value = candidate[action];
    if (typeof value === 'string' && value.trim()) {
      result[action] = value.trim();
    }
  }
  return result;
}

function normalizeTestPlaySettings(candidate = {}) {
  const normalized = cloneDefaultTestPlaySettings();
  if (!candidate || typeof candidate !== 'object') {
    return normalized;
  }

  normalized.keyboard = normalizeBindingMap(candidate.keyboard, DEFAULT_TESTPLAY_SETTINGS.keyboard);
  normalized.gamepad = normalizeBindingMap(candidate.gamepad, DEFAULT_TESTPLAY_SETTINGS.gamepad);

  if (typeof candidate.gamepadDeadzone === 'number' && Number.isFinite(candidate.gamepadDeadzone)) {
    normalized.gamepadDeadzone = Math.min(0.95, Math.max(0.05, candidate.gamepadDeadzone));
  }

  if (candidate.debug && typeof candidate.debug === 'object') {
    if (typeof candidate.debug.autoRefresh === 'boolean') {
      normalized.debug.autoRefresh = candidate.debug.autoRefresh;
    }
    if (typeof candidate.debug.vramTileLayout === 'string' && TESTPLAY_VRAM_LAYOUTS.includes(candidate.debug.vramTileLayout)) {
      normalized.debug.vramTileLayout = candidate.debug.vramTileLayout;
    }
  }

  return normalized;
}

function getDefaultTestPlaySettings() {
  return cloneDefaultTestPlaySettings();
}

function getTestPlaySettings() {
  const settings = loadSettings();
  return normalizeTestPlaySettings(settings.testPlay);
}

function saveTestPlaySettings(next) {
  const current = getTestPlaySettings();
  const merged = {
    keyboard: { ...current.keyboard, ...(next && typeof next.keyboard === 'object' ? next.keyboard : {}) },
    gamepad: { ...current.gamepad, ...(next && typeof next.gamepad === 'object' ? next.gamepad : {}) },
    gamepadDeadzone: next && Object.prototype.hasOwnProperty.call(next, 'gamepadDeadzone')
      ? next.gamepadDeadzone
      : current.gamepadDeadzone,
    debug: { ...current.debug, ...(next && typeof next.debug === 'object' ? next.debug : {}) },
  };
  const normalized = normalizeTestPlaySettings(merged);
  saveSettings({ testPlay: normalized });
  return normalized;
}

// ---------------------------------------------------------------- settings --

function loadSettings() {
  const p = getSettingsPath();
  if (!fs.existsSync(p)) return {};
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8'));
  } catch {
    return {};
  }
}

function saveSettings(obj) {
  const dir = getToolsDir();
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const current = loadSettings();
  fs.writeFileSync(getSettingsPath(), JSON.stringify({ ...current, ...obj }, null, 2), 'utf-8');
}

// ------------------------------------------------------------- SGDK path --

/**
 * 自動展開先のディレクトリ内の最初のサブディレクトリを返す
 * GitHub から DL した zip は SGDK-X.XX/ という名前のサブフォルダになる
 */
function findExtractedSgdkDir() {
  const base = getSgdkBaseDir();
  if (!fs.existsSync(base)) return null;
  const entries = fs.readdirSync(base).filter((e) => {
    try { return fs.statSync(path.join(base, e)).isDirectory(); } catch { return false; }
  });
  if (entries.length === 0) {
    return null;
  }

  const parseVer = (name) => {
    const m = name.match(/(\d+)\.(\d+)(?:\.(\d+))?/);
    if (!m) return [0, 0, 0];
    return [Number(m[1]), Number(m[2]), Number(m[3] || 0)];
  };

  entries.sort((a, b) => {
    const va = parseVer(a);
    const vb = parseVer(b);
    for (let i = 0; i < 3; i += 1) {
      if (va[i] !== vb[i]) return vb[i] - va[i];
    }
    return b.localeCompare(a);
  });

  return path.join(base, entries[0]);
}

function getSgdkPath() {
  const settings = loadSettings();
  if (settings.sgdkPath && fs.existsSync(settings.sgdkPath)) {
    return settings.sgdkPath;
  }
  return findExtractedSgdkDir();
}

function setSgdkPath(p) {
  saveSettings({ sgdkPath: p });
}

// --------------------------------------------------------- Marsdev path --

function findExtractedMarsdevDir() {
  const base = getMarsdevBaseDir();
  if (!fs.existsSync(base)) return null;
  const entries = fs.readdirSync(base).filter((e) => {
    try { return fs.statSync(path.join(base, e)).isDirectory(); } catch { return false; }
  });
  if (entries.length === 0) {
    return null;
  }

  const parseVer = (name) => {
    const m = name.match(/(\d+)\.(\d+)(?:\.(\d+))?/);
    if (!m) return [0, 0, 0];
    return [Number(m[1]), Number(m[2]), Number(m[3] || 0)];
  };

  entries.sort((a, b) => {
    const va = parseVer(a);
    const vb = parseVer(b);
    for (let i = 0; i < 3; i += 1) {
      if (va[i] !== vb[i]) return vb[i] - va[i];
    }
    return b.localeCompare(a);
  });

  return path.join(base, entries[0]);
}

function resolveMarsdevGdkPath(basePath) {
  if (!basePath || !fs.existsSync(basePath)) return null;
  if (fs.existsSync(path.join(basePath, 'makelib.gen'))) {
    return basePath;
  }
  const gdkPath = path.join(basePath, 'm68k-elf');
  if (fs.existsSync(path.join(gdkPath, 'makelib.gen'))) {
    return gdkPath;
  }
  return null;
}

function getMarsdevPath() {
  const settings = loadSettings();
  if (settings.marsdevPath && fs.existsSync(settings.marsdevPath)) {
    const resolved = resolveMarsdevGdkPath(settings.marsdevPath);
    if (resolved) return resolved;
  }
  return resolveMarsdevGdkPath(findExtractedMarsdevDir());
}

function setMarsdevPath(p) {
  saveSettings({ marsdevPath: p });
}

function checkSgdk() {
  const p = getSgdkPath();
  if (!p) return { installed: false, path: null, version: null };
  const makelib = path.join(p, 'makelib.gen');
  const installed = fs.existsSync(makelib);
  // バージョンをディレクトリ名から推定
  const version = path.basename(p).replace(/^SGDK-?/i, '') || 'unknown';
  return { installed, path: installed ? p : null, version };
}

function checkMarsdev() {
  const p = getMarsdevPath();
  if (!p) return { installed: false, path: null, version: null };
  const makelib = path.join(p, 'makelib.gen');
  const installed = fs.existsSync(makelib);
  const settings = loadSettings();
  let version = settings.marsdevVersion || 'unknown';
  if (!settings.marsdevVersion) {
    // 旧レイアウト向けにディレクトリ名から推定（失敗時は unknown）
    const guessed = path.basename(path.dirname(path.dirname(p))).replace(/^marsdev-?/i, '');
    if (guessed && /\d/.test(guessed)) {
      version = guessed;
    }
  }
  return { installed, path: installed ? p : null, version };
}

function findFirstExisting(baseDir, relativeCandidates) {
  for (const rel of relativeCandidates) {
    const abs = path.join(baseDir, rel);
    if (fs.existsSync(abs)) {
      return abs;
    }
  }
  return null;
}

function getBundledTools(toolchainPath, isMarsdev = false) {
  if (!toolchainPath || !fs.existsSync(toolchainPath)) {
    return { make: null, gcc: null, java: null, as: null };
  }

  const isWin = process.platform === 'win32';

  let make, gcc, java, as;

  if (isMarsdev || process.platform !== 'win32') {
    // Marsdev or Unix-like platform: look for native binaries
    make = findFirstExisting(toolchainPath, ['bin/make', 'make']);
    gcc = findFirstExisting(toolchainPath, [
      'bin/m68k-elf-gcc',
      'm68k-elf-gcc',
      'bin/gcc',
      'gcc',
    ]);
    as = findFirstExisting(toolchainPath, [
      'bin/m68k-elf-as',
      'm68k-elf-as',
      'bin/as',
      'as',
    ]);
    java = findFirstExisting(toolchainPath, [
      'bin/java',
      'java',
    ]);
  } else {
    // Windows: prefer .exe versions
    make = findFirstExisting(toolchainPath, [
      'bin/make/make.exe',
      'bin/make.exe',
    ]);
    gcc = findFirstExisting(toolchainPath, [
      'bin/gcc/bin/m68k-elf-gcc.exe',
      'bin/m68k-elf-gcc.exe',
      'bin/gcc.exe',
    ]);
    java = findFirstExisting(toolchainPath, [
      'bin/java/bin/java.exe',
      'bin/java/bin/java',
    ]);
  }

  return { make, gcc, java, as };
}

function getSgdkBundledTools(sgdkPath) {
  return getBundledTools(sgdkPath, false);
}

function getMarsdevBundledTools(marsdevPath) {
  return getBundledTools(marsdevPath, true);
}

// -------------------------------------------------------------- Java path --

function findExtractedJreDir() {
  const base = getJreBaseDir();
  if (!fs.existsSync(base)) return null;
  const entries = fs.readdirSync(base).filter((e) => {
    try { return fs.statSync(path.join(base, e)).isDirectory(); } catch { return false; }
  });
  if (entries.length === 0) return null;
  const javaExe = path.join(base, entries[0], 'bin', 'java.exe');
  return fs.existsSync(javaExe) ? path.join(base, entries[0]) : null;
}

function getJavaExePath() {
  const settings = loadSettings();
  if (settings.javaPath) {
    const abs = settings.javaPath.endsWith('java') || settings.javaPath.endsWith('java.exe')
      ? settings.javaPath
      : path.join(settings.javaPath, 'bin', process.platform === 'win32' ? 'java.exe' : 'java');
    if (fs.existsSync(abs)) return abs;
  }

  const sgdkPath = getSgdkPath();
  const bundled = getSgdkBundledTools(sgdkPath).java;
  if (bundled) {
    return bundled;
  }

  if (process.platform === 'win32') {
    // 別途 DL した JRE
    const jreDir = findExtractedJreDir();
    if (jreDir) return path.join(jreDir, 'bin', 'java.exe');
    return null;
  }

  // macOS/Linux: システム java を確認
  try {
    execSync('java -version', { stdio: 'ignore' });
    return 'java';
  } catch {
    return null;
  }
}

function checkJava() {
  const javaBin = getJavaExePath();
  if (!javaBin) {
    return { installed: false, system: process.platform !== 'win32', path: null };
  }
  return {
    installed: true,
    system: javaBin === 'java',
    path: javaBin,
  };
}

function checkM68kGcc() {
  if (process.platform === 'win32') {
    // Windows: SGDK bundled tools only
    const sgdkPath = getSgdkPath();
    if (!sgdkPath) return { installed: false, path: null, source: 'none' };
    const tools = getSgdkBundledTools(sgdkPath);
    return {
      installed: !!tools.gcc,
      path: tools.gcc,
      source: 'sgdk',
    };
  }

  // macOS/Linux: Marsdev → SGDK (if native) → system
  const marsdevPath = getMarsdevPath();
  if (marsdevPath) {
    const tools = getMarsdevBundledTools(marsdevPath);
    if (tools.gcc) {
      return { installed: true, path: tools.gcc, source: 'marsdev' };
    }
  }

  const sgdkPath = getSgdkPath();
  if (sgdkPath) {
    const tools = getSgdkBundledTools(sgdkPath);
    if (tools.gcc) {
      return { installed: true, path: tools.gcc, source: 'sgdk' };
    }
  }

  try {
    const which = execSync('which m68k-elf-gcc', { encoding: 'utf-8' }).trim();
    if (which) {
      return { installed: true, path: which, source: 'system' };
    }
  } catch (_err) {
  }

  return { installed: false, path: null, source: 'none' };
}

function tryPatchMachODylib(binaryPath, oldPath, newPath) {
  const { spawnSync } = require('child_process');
  const inspect = spawnSync('otool', ['-L', binaryPath], { encoding: 'utf-8' });
  if (inspect.status !== 0 || !String(inspect.stdout || '').includes(oldPath)) {
    return false;
  }
  const patch = spawnSync('install_name_tool', ['-change', oldPath, newPath, binaryPath], { encoding: 'utf-8' });
  return patch.status === 0;
}

function getMachOArches(filePath) {
  const { spawnSync } = require('child_process');
  const res = spawnSync('lipo', ['-archs', filePath], { encoding: 'utf-8' });
  if (res.status !== 0) return [];
  return String(res.stdout || '').trim().split(/\s+/).filter(Boolean);
}

function ensureMarsdevX64Libintl() {
  const targetDir = path.join(getToolsDir(), 'marsdev', 'runtime-lib', 'x86_64');
  const targetLib = path.join(targetDir, 'libintl.8.dylib');
  if (fs.existsSync(targetLib) && getMachOArches(targetLib).includes('x86_64')) {
    return { ok: true, path: targetLib, source: 'cache' };
  }

  const { spawnSync, execSync } = require('child_process');
  try {
    const formulaJson = execSync('curl -fsSL https://formulae.brew.sh/api/formula/gettext.json', { encoding: 'utf-8' });
    const formula = JSON.parse(formulaJson);
    const files = formula?.bottle?.stable?.files || {};

    // Select Intel macOS bottle dynamically.
    // Newer Homebrew keys can be like: arm64_tahoe, arm64_sequoia, sonoma, etc.
    // We need non-arm64 and non-linux key.
    const allKeys = Object.keys(files);
    const intelMacKeys = allKeys.filter((k) => {
      const key = String(k || '').toLowerCase();
      return !key.startsWith('arm64_') && !key.includes('linux');
    });

    // Prefer newer macOS keys first if multiple exist.
    const keyPriority = ['tahoe', 'sequoia', 'sonoma', 'ventura', 'monterey', 'big_sur', 'catalina', 'mojave', 'high_sierra'];
    intelMacKeys.sort((a, b) => {
      const ai = keyPriority.indexOf(String(a).toLowerCase());
      const bi = keyPriority.indexOf(String(b).toLowerCase());
      const ar = ai === -1 ? 999 : ai;
      const br = bi === -1 ? 999 : bi;
      return ar - br;
    });

    let bottleUrl = null;
    for (const tag of intelMacKeys) {
      if (files[tag] && files[tag].url) {
        bottleUrl = files[tag].url;
        break;
      }
    }
    if (!bottleUrl) {
      return { ok: false, error: 'x86_64 gettext bottle URL was not found in formula metadata.' };
    }

    const tmpDir = path.join(getToolsDir(), 'tmp-gettext-x64');
    if (fs.existsSync(tmpDir)) fs.rmSync(tmpDir, { recursive: true, force: true });
    fs.mkdirSync(tmpDir, { recursive: true });
    const bottlePath = path.join(tmpDir, 'gettext-x64.tar.gz');

    const dl = spawnSync('curl', ['-fL', bottleUrl, '-o', bottlePath], { encoding: 'utf-8' });
    if (dl.status !== 0 || !fs.existsSync(bottlePath)) {
      return { ok: false, error: 'Failed to download x86_64 gettext bottle.' };
    }

    const list = spawnSync('tar', ['-tzf', bottlePath], { encoding: 'utf-8' });
    if (list.status !== 0) {
      return { ok: false, error: 'Failed to inspect gettext bottle archive.' };
    }
    const lines = String(list.stdout || '').split('\n');
    const dylibEntry = lines.find((l) => l.endsWith('/lib/libintl.8.dylib'));
    if (!dylibEntry) {
      return { ok: false, error: 'libintl.8.dylib not found inside gettext bottle.' };
    }

    const extract = spawnSync('tar', ['-xzf', bottlePath, '-C', tmpDir, dylibEntry], { encoding: 'utf-8' });
    if (extract.status !== 0) {
      return { ok: false, error: 'Failed to extract libintl.8.dylib from gettext bottle.' };
    }

    const extractedPath = path.join(tmpDir, dylibEntry);
    if (!fs.existsSync(extractedPath)) {
      return { ok: false, error: 'Extracted libintl.8.dylib path was not found.' };
    }

    fs.mkdirSync(targetDir, { recursive: true });
    fs.copyFileSync(extractedPath, targetLib);

    if (!getMachOArches(targetLib).includes('x86_64')) {
      return { ok: false, error: 'Extracted libintl.8.dylib is not x86_64 architecture.' };
    }

    return { ok: true, path: targetLib, source: 'download' };
  } catch (err) {
    return { ok: false, error: `Failed to prepare x86_64 libintl: ${err.message || String(err)}` };
  }
}

function fixMarsdevMacosGettext(marsdevPath) {
  if (process.platform !== 'darwin') {
    return { ok: true, patched: 0, reason: 'not-macos' };
  }
  if (!marsdevPath || !fs.existsSync(marsdevPath)) {
    return { ok: false, patched: 0, error: 'Marsdev path is not set' };
  }

  const legacyIntl = '/usr/local/opt/gettext/lib/libintl.8.dylib';
  const armIntl = '/opt/homebrew/opt/gettext/lib/libintl.8.dylib';

  const gccBin = path.join(marsdevPath, 'bin', 'm68k-elf-gcc');
  const gccArches = fs.existsSync(gccBin) ? getMachOArches(gccBin) : [];
  if (gccArches.length === 0) {
    return { ok: false, patched: 0, error: `Cannot inspect Marsdev binary architecture: ${gccBin}` };
  }

  let targetIntl = null;
  let targetArch = null;

  if (gccArches.includes('x86_64')) {
    targetArch = 'x86_64';
    if (fs.existsSync(legacyIntl) && getMachOArches(legacyIntl).includes('x86_64')) {
      targetIntl = legacyIntl;
    } else {
      const localLib = ensureMarsdevX64Libintl();
      if (localLib.ok) {
        targetIntl = localLib.path;
      } else {
        return {
          ok: false,
          patched: 0,
          error: `${localLib.error}\nMarsdev が x86_64 バイナリのため、x86_64 の gettext が必要です。\n自動復旧に失敗した場合は Intel Homebrew で gettext を導入してください。\n例:\n1) softwareupdate --install-rosetta --agree-to-license\n2) arch -x86_64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n3) arch -x86_64 /usr/local/bin/brew install gettext\n4) その後に再ビルド\n※ /usr/local/bin/brew が無い場合は Intel Homebrew の導入が未完了です。`,
        };
      }
    }
  } else if (gccArches.includes('arm64')) {
    targetArch = 'arm64';
    if (fs.existsSync(armIntl) && getMachOArches(armIntl).includes('arm64')) {
      targetIntl = armIntl;
    } else {
      return {
        ok: false,
        patched: 0,
        error: 'Marsdev が arm64 バイナリですが、`/opt/homebrew/opt/gettext/lib/libintl.8.dylib` (arm64) が見つかりません。`brew install gettext` を実行してください。',
      };
    }
  } else {
    return {
      ok: false,
      patched: 0,
      error: `Unsupported Marsdev binary architecture: ${gccArches.join(', ')}`,
    };
  }

  const binDir = path.join(marsdevPath, 'bin');
  if (!fs.existsSync(binDir)) {
    return { ok: false, patched: 0, error: `Marsdev bin directory not found: ${binDir}` };
  }

  const entries = fs.readdirSync(binDir);
  let patched = 0;
  for (const e of entries) {
    const p = path.join(binDir, e);
    let st;
    try {
      st = fs.statSync(p);
    } catch (_err) {
      continue;
    }
    if (!st.isFile()) continue;
    if ((st.mode & 0o111) === 0) continue;

    try {
      // 旧参照 -> 目標参照 の補正（両方向に対応してアーキ不一致を解消）
      for (const candidate of [legacyIntl, armIntl]) {
        if (candidate === targetIntl) continue;
        if (tryPatchMachODylib(p, candidate, targetIntl)) {
          patched += 1;
        }
      }
    } catch (_err) {
      // Ignore single-file patch errors and continue.
    }
  }

  return { ok: true, patched, reason: `patched-or-already-healthy (${targetArch})` };
}

// ---------------------------------------------------------------- network --

function httpsGet(url, options = {}) {
  return new Promise((resolve, reject) => {
    const opts = { ...options, headers: { 'User-Agent': 'md-game-editor/1.0', ...(options.headers || {}) } };
    const req = https.get(url, opts, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        resolve(httpsGet(res.headers.location, options));
        return;
      }
      let data = '';
      res.on('data', (c) => { data += c; });
      res.on('end', () => resolve({ statusCode: res.statusCode, body: data, headers: res.headers }));
    });
    req.on('error', reject);
  });
}

function downloadToFile(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const doGet = (u) => {
      const opts = { headers: { 'User-Agent': 'md-game-editor/1.0' } };
      https.get(u, opts, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          doGet(res.headers.location);
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${u}`));
          return;
        }
        const total = parseInt(res.headers['content-length'] || '0', 10);
        let received = 0;
        const out = fs.createWriteStream(destPath);
        res.on('data', (chunk) => {
          received += chunk.length;
          if (onProgress && total > 0) onProgress(received, total);
        });
        res.pipe(out);
        out.on('finish', () => out.close(resolve));
        out.on('error', (err) => { fs.unlink(destPath, () => {}); reject(err); });
        res.on('error', (err) => { fs.unlink(destPath, () => {}); reject(err); });
      }).on('error', reject);
    };
    doGet(url);
  });
}

async function getLatestSgdkRelease() {
  const url = `https://api.github.com/repos/${SGDK_OWNER}/${SGDK_REPO}/releases/latest`;
  const res = await httpsGet(url);
  if (res.statusCode !== 200) throw new Error(`GitHub API returned ${res.statusCode}`);
  const data = JSON.parse(res.body);
  const tag = data.tag_name; // e.g. "v2.00"
  const zipUrl = `https://github.com/${SGDK_OWNER}/${SGDK_REPO}/archive/refs/tags/${tag}.zip`;
  return { tag, zipUrl, name: data.name };
}

async function listSgdkReleases(limit = 20) {
  const url = `https://api.github.com/repos/${SGDK_OWNER}/${SGDK_REPO}/releases?per_page=${Math.max(1, Math.min(limit, 50))}`;
  const res = await httpsGet(url);
  if (res.statusCode !== 200) throw new Error(`GitHub API returned ${res.statusCode}`);
  const data = JSON.parse(res.body);
  const releases = (Array.isArray(data) ? data : [])
    .filter((r) => !r.draft)
    .map((r) => ({
      tag: r.tag_name,
      name: r.name || r.tag_name,
      prerelease: !!r.prerelease,
      publishedAt: r.published_at || null,
    }));
  return { releases };
}

async function listMarsdevReleases(limit = 20) {
  const url = `https://api.github.com/repos/${MARSDEV_OWNER}/${MARSDEV_REPO}/releases?per_page=${Math.max(1, Math.min(limit, 50))}`;
  const res = await httpsGet(url);
  if (res.statusCode !== 200) throw new Error(`GitHub API returned ${res.statusCode}`);
  const data = JSON.parse(res.body);
  const releases = (Array.isArray(data) ? data : [])
    .filter((r) => !r.draft)
    .map((r) => ({
      tag: r.tag_name,
      name: r.name || r.tag_name,
      prerelease: !!r.prerelease,
      publishedAt: r.published_at || null,
    }));
  return { releases };
}

// -------------------------------------------------------------- extraction --

function extractZip(zipPath, destDir) {
  return new Promise((resolve, reject) => {
    const { spawn } = require('child_process');
    if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });

    let proc;
    if (process.platform === 'win32') {
      proc = spawn('powershell', [
        '-NoProfile', '-Command',
        `Expand-Archive -Path "${zipPath}" -DestinationPath "${destDir}" -Force`,
      ], { windowsHide: true });
    } else {
      proc = spawn('unzip', ['-q', '-o', zipPath, '-d', destDir]);
    }

    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`unzip exited with code ${code}`));
    });
    proc.on('error', reject);
  });
}

function extractTarGz(tarPath, destDir) {
  return new Promise((resolve, reject) => {
    const { spawn } = require('child_process');
    if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });

    const proc = spawn('tar', ['-xf', tarPath, '-C', destDir]);
    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`tar exited with code ${code}`));
    });
    proc.on('error', reject);
  });
}

// ---------------------------------------------------------------- download --

async function downloadSgdk(selectedTag, onProgress) {
  let tag = selectedTag;
  let zipUrl;

  if (!tag) {
    const latest = await getLatestSgdkRelease();
    tag = latest.tag;
    zipUrl = latest.zipUrl;
  } else {
    zipUrl = `https://github.com/${SGDK_OWNER}/${SGDK_REPO}/archive/refs/tags/${tag}.zip`;
  }

  const toolsDir = getToolsDir();
  if (!fs.existsSync(toolsDir)) fs.mkdirSync(toolsDir, { recursive: true });

  const zipPath = path.join(toolsDir, `sgdk-${tag}.zip`);

  onProgress && onProgress({ phase: 'download', message: `Downloading SGDK ${tag}...`, percent: 0 });
  await downloadToFile(zipUrl, zipPath, (received, total) => {
    onProgress && onProgress({ phase: 'download', message: `Downloading SGDK ${tag}...`, percent: Math.round((received / total) * 70) });
  });

  onProgress && onProgress({ phase: 'extract', message: 'Extracting...', percent: 75 });
  const sgdkBase = getSgdkBaseDir();
  if (fs.existsSync(sgdkBase)) fs.rmSync(sgdkBase, { recursive: true, force: true });
  await extractZip(zipPath, sgdkBase);

  // 展開後 zip を削除
  fs.unlink(zipPath, () => {});

  onProgress && onProgress({ phase: 'done', message: `SGDK ${tag} installed`, percent: 100 });
  return { ok: true, tag };
}

async function downloadMarsdev(selectedTag, onProgress) {
  let tag = selectedTag;
  let release;

  if (process.platform !== 'darwin' && process.platform !== 'linux') {
    return { ok: false, error: 'Marsdev is only available for macOS and Linux' };
  }

  if (!tag) {
    const url = `https://api.github.com/repos/${MARSDEV_OWNER}/${MARSDEV_REPO}/releases/latest`;
    const res = await httpsGet(url);
    if (res.statusCode !== 200) throw new Error(`GitHub API returned ${res.statusCode}`);
    release = JSON.parse(res.body);
    tag = release.tag_name;
  } else {
    const url = `https://api.github.com/repos/${MARSDEV_OWNER}/${MARSDEV_REPO}/releases/tags/${tag}`;
    const res = await httpsGet(url);
    if (res.statusCode !== 200) throw new Error(`GitHub API returned ${res.statusCode}`);
    release = JSON.parse(res.body);
  }

  const assets = Array.isArray(release.assets) ? release.assets : [];
  const platformTokens = process.platform === 'darwin'
    ? ['macos', 'darwin']
    : ['linux'];
  const archTokens = process.arch === 'arm64'
    ? ['arm64', 'aarch64']
    : ['x86_64', 'x64', 'amd64'];

  const isSupportedArchive = (name) => (
    name.endsWith('.tar.xz') || name.endsWith('.tar.gz') || name.endsWith('.zip')
  );

  const platformAssets = assets.filter((a) => {
    const n = String(a.name || '').toLowerCase();
    return isSupportedArchive(n) && platformTokens.some((t) => n.includes(t));
  });

  const preferredAsset = platformAssets.find((a) => {
    const n = String(a.name || '').toLowerCase();
    return archTokens.some((t) => n.includes(t));
  }) || platformAssets[0];

  if (!preferredAsset) {
    const available = assets.map((a) => a.name).join(', ');
    throw new Error(`No Marsdev asset found for ${process.platform}. Available: ${available}`);
  }

  const downloadUrl = preferredAsset.browser_download_url;

  const toolsDir = getToolsDir();
  if (!fs.existsSync(toolsDir)) fs.mkdirSync(toolsDir, { recursive: true });

  const lowerName = String(preferredAsset.name || '').toLowerCase();
  const ext = lowerName.endsWith('.tar.xz')
    ? '.tar.xz'
    : (lowerName.endsWith('.tar.gz') ? '.tar.gz' : '.zip');
  const fileName = `marsdev-${tag}${ext}`;
  const filePath = path.join(toolsDir, fileName);

  onProgress && onProgress({ phase: 'download', message: `Downloading Marsdev ${tag}...`, percent: 0 });
  await downloadToFile(downloadUrl, filePath, (received, total) => {
    onProgress && onProgress({ phase: 'download', message: `Downloading Marsdev ${tag}...`, percent: Math.round((received / total) * 70) });
  });

  onProgress && onProgress({ phase: 'extract', message: 'Extracting...', percent: 75 });
  const marsdevBase = getMarsdevBaseDir();
  if (fs.existsSync(marsdevBase)) fs.rmSync(marsdevBase, { recursive: true, force: true });

  if (ext === '.tar.xz' || ext === '.tar.gz') {
    await extractTarGz(filePath, marsdevBase);
  } else {
    await extractZip(filePath, marsdevBase);
  }

  fs.unlink(filePath, () => {});

  const installedPath = getMarsdevPath();
  if (installedPath) {
    saveSettings({ marsdevPath: installedPath, marsdevVersion: tag });
    const fix = fixMarsdevMacosGettext(installedPath);
    if (!fix.ok) {
      return { ok: false, error: fix.error };
    }
  }

  onProgress && onProgress({ phase: 'done', message: `Marsdev ${tag} installed`, percent: 100 });
  return { ok: true, tag, path: installedPath };
}

async function downloadJava(onProgress) {
  if (process.platform !== 'win32') {
    return { ok: false, error: 'Java auto-download is Windows only' };
  }

  // Adoptium Temurin 21 LTS for Windows x64
  const url = 'https://api.adoptium.net/v3/assets/latest/21/hotspot?os=windows&architecture=x64&image_type=jre';
  onProgress && onProgress({ phase: 'fetch', message: 'Fetching Java download URL...', percent: 5 });

  const res = await httpsGet(url);
  if (res.statusCode !== 200) throw new Error(`Adoptium API ${res.statusCode}`);
  const assets = JSON.parse(res.body);
  if (!assets || assets.length === 0) throw new Error('No Java assets found');

  const asset = assets[0];
  const downloadUrl = asset.binary?.package?.link;
  if (!downloadUrl) throw new Error('Could not find Java download URL');

  const toolsDir = getToolsDir();
  if (!fs.existsSync(toolsDir)) fs.mkdirSync(toolsDir, { recursive: true });

  const zipPath = path.join(toolsDir, 'jre-temurin.zip');
  onProgress && onProgress({ phase: 'download', message: 'Downloading Java JRE...', percent: 10 });

  await downloadToFile(downloadUrl, zipPath, (received, total) => {
    onProgress && onProgress({ phase: 'download', message: 'Downloading Java JRE...', percent: 10 + Math.round((received / total) * 65) });
  });

  onProgress && onProgress({ phase: 'extract', message: 'Extracting Java JRE...', percent: 80 });
  const jreBase = getJreBaseDir();
  if (fs.existsSync(jreBase)) fs.rmSync(jreBase, { recursive: true, force: true });
  await extractZip(zipPath, jreBase);
  fs.unlink(zipPath, () => {});

  onProgress && onProgress({ phase: 'done', message: 'Java JRE installed', percent: 100 });
  return { ok: true };
}

// ------------------------------------------------------------------ status --

function getStatus() {
  const sgdk = checkSgdk();
  const marsdev = checkMarsdev();
  const java = checkJava();
  const gcc = checkM68kGcc();
  return { sgdk, marsdev, java, gcc, platform: process.platform };
}

function getToolchainDir() {
  // On macOS/Linux prefer Marsdev, on Windows use SGDK
  if (process.platform === 'win32') {
    return getSgdkPath();
  }
  const marsdevPath = getMarsdevPath();
  if (marsdevPath) return marsdevPath;
  return getSgdkPath();
}

module.exports = {
  getStatus,
  listSgdkReleases,
  listMarsdevReleases,
  getDefaultTestPlaySettings,
  getTestPlaySettings,
  saveTestPlaySettings,
  getSgdkPath,
  setSgdkPath,
  getMarsdevPath,
  setMarsdevPath,
  getToolchainDir,
  getSgdkBundledTools,
  getMarsdevBundledTools,
  fixMarsdevMacosGettext,
  getJavaExePath,
  checkSgdk,
  checkMarsdev,
  checkJava,
  checkM68kGcc,
  downloadSgdk,
  downloadMarsdev,
  downloadJava,
};
