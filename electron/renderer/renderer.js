/**
 * MD Game Editor - renderer.js
 * エディタのフロントエンドロジック
 */

// ------------------------------------------------------------------ state --
const state = {
  currentPage: 'assets',
  logOpen: false,
  logOpenHeight: 220,
  building: false,
  lastRomPath: null,
  projectConfig: {
    title: 'MY GAME',
    author: 'AUTHOR',
    serial: 'GM 00000000-00',
    region: 'JUE',
  },
};

// -------------------------------------------------------------------- DOM --
const $ = (id) => document.getElementById(id);

const el = {
  btnBuild:       $('btnBuild'),
  btnTestPlay:    $('btnTestPlay'),
  projectName:    $('projectName'),
  buildLog:       $('buildLog'),
  buildLogBar:    $('buildLogBar'),
  buildLogBody:   $('buildLogBody'),
  buildStatusBadge: $('buildStatusBadge'),
  buildRomSize:   $('buildRomSize'),
  btnCopyLog:     $('btnCopyLog'),
  btnToggleLog:   $('btnToggleLog'),
  btnClearLog:    $('btnClearLog'),
  buildLogHeader: $('buildLogHeader'),
  buildLogResizer: $('buildLogResizer'),
  mainLayout:     document.querySelector('.main-layout'),
  // code page
  codeEditor:     $('codeEditor'),
  codeStatus:     $('codeStatus'),
  btnGenSample:   $('btnGenSample'),
  btnSaveCode:    $('btnSaveCode'),
  btnCopyCode:    $('btnCopyCode'),
  // settings page
  settingTitle:  $('settingTitle'),
  settingAuthor:   $('settingAuthor'),
  settingSerial:   $('settingSerial'),
  settingTitleError: $('settingTitleError'),
  settingAuthorError: $('settingAuthorError'),
  settingSerialError: $('settingSerialError'),
  settingOutputPath: $('settingOutputPath'),
  btnOpenOutputFolder: $('btnOpenOutputFolder'),
  btnDownloadRom: $('btnDownloadRom'),
  btnSaveSettings:  $('btnSaveSettings'),
  settingsSavedMsg: $('settingsSavedMsg'),
  aboutModal: $('aboutModal'),
  aboutBackdrop: $('aboutBackdrop'),
  btnAboutClose: $('btnAboutClose'),
  aboutTitle: $('aboutTitle'),
  aboutDescription: $('aboutDescription'),
  aboutAppVersion: $('aboutAppVersion'),
  aboutWasmBuildVersion: $('aboutWasmBuildVersion'),
  aboutWasmPackageVersion: $('aboutWasmPackageVersion'),
  aboutElectronVersion: $('aboutElectronVersion'),
  aboutChromeVersion: $('aboutChromeVersion'),
  aboutNodeVersion: $('aboutNodeVersion'),
  aboutPlatform: $('aboutPlatform'),
  aboutArch: $('aboutArch'),
  aboutAppPath: $('aboutAppPath'),
};

const TITLE_MAX = 48;
const AUTHOR_MAX = 16;
const SERIAL_MAX = 14;
const PRINTABLE_ASCII_RE = /^[\x20-\x7E]+$/;
const SERIAL_RE = /^[A-Z]{2}\s[0-9A-Z]{8}-[0-9A-Z]{2}$/;

// ============================================================ BUILD LOG ===

function appendBuildLog(text, level = 'info') {
  const pre = el.buildLog;
  if (level === 'error') {
    pre.textContent += text + '\n';
  } else {
    pre.textContent += text + '\n';
  }
  pre.scrollTop = pre.scrollHeight;
}

function clearBuildLog() {
  el.buildLog.textContent = '';
}

function updateRomOutputActions() {
  const hasRom = !!state.lastRomPath;
  if (el.btnDownloadRom) {
    el.btnDownloadRom.disabled = !hasRom;
    el.btnDownloadRom.style.display = hasRom ? 'inline-flex' : 'none';
  }
}

async function copyBuildLog() {
  const text = el.buildLog.textContent || '';
  if (!text.trim()) {
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    el.btnCopyLog.title = 'コピーしました';
    setTimeout(() => {
      if (el.btnCopyLog) {
        el.btnCopyLog.title = 'ログをコピー';
      }
    }, 1200);
  } catch (_err) {
    const range = document.createRange();
    range.selectNodeContents(el.buildLog);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand('copy');
    selection.removeAllRanges();
  }
}

function setBuildStatus(type, text) {
  const badge = el.buildStatusBadge;
  badge.textContent = text;
  badge.className = 'build-status-badge ' + (type || '');
}

function setLogOpen(open) {
  state.logOpen = open;
  el.buildLogBar.classList.toggle('open', open);
  el.mainLayout.classList.toggle('log-open', open);
  if (el.buildLogResizer) {
    el.buildLogResizer.style.display = open ? 'block' : 'none';
  }
  // chevron
  const use = el.btnToggleLog.querySelector('use');
  if (use) use.setAttribute('href', open ? '#icon-chevron-down' : '#icon-chevron-up');
}

function setLogOpenHeight(height) {
  const minHeight = 140;
  const maxHeight = Math.max(minHeight, Math.floor(window.innerHeight * 0.75));
  const next = Math.max(minHeight, Math.min(maxHeight, Number(height) || state.logOpenHeight));
  state.logOpenHeight = next;
  document.documentElement.style.setProperty('--log-h-open', `${next}px`);
}

// ============================================================= PAGE NAV ===

function switchPage(page) {
  state.currentPage = page;
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });
  document.querySelectorAll('.editor-page').forEach((sec) => {
    sec.classList.toggle('active', sec.id === `page-${page}`);
  });
}

// ========================================================== SAMPLE CODE ===

const HELLO_WORLD_C = `/**
 * Hello World - MD Game Editor サンプル
 * SGDK を使った最小限のメガドライブゲーム
 */
#include <genesis.h>

int main(void)
{
    /* 背景色を設定（パレット 0, カラー 0: 濃い青） */
    PAL_setColor(0, RGB24_TO_VDPCOLOR(0x000060));

    /* テキスト表示 */
    VDP_drawText("*** HELLO, MEGA WORLD! ***", 3, 10);
    VDP_drawText("MD GAME EDITOR SAMPLE", 6, 13);
    VDP_drawText("PRESS START", 10, 18);

    /* メインループ */
    while (1)
    {
        SYS_doVBlankProcess();
    }

    return 0;
}
`;

function loadSampleCode() {
  el.codeEditor.value = HELLO_WORLD_C;
  el.codeStatus.textContent = 'Hello World サンプルを読み込みました。Build ボタンでビルドできます。';
}

// ============================================================== SETTINGS ===

function updateProjectNameDisplay() {
  el.projectName.textContent = state.projectConfig.title || 'MY GAME';
}

function setFieldError(inputEl, errorEl, message) {
  if (!inputEl || !errorEl) return;
  const hasError = !!message;
  inputEl.classList.toggle('invalid', hasError);
  errorEl.textContent = message || '';
}

function validateTitle(value) {
  if (!value) return 'タイトルを入力してください';
  if (value.length > TITLE_MAX) return `タイトルは ${TITLE_MAX} 文字以内です`;
  if (!PRINTABLE_ASCII_RE.test(value)) return 'タイトルは半角ASCII文字で入力してください';
  return '';
}

function validateAuthor(value) {
  if (!value) return '作者名を入力してください';
  if (value.length > AUTHOR_MAX) return `作者名は ${AUTHOR_MAX} 文字以内です`;
  if (!PRINTABLE_ASCII_RE.test(value)) return '作者名は半角ASCII文字で入力してください';
  return '';
}

function validateSerial(value) {
  if (!value) return 'シリアルナンバーを入力してください';
  if (value.length !== SERIAL_MAX) return `シリアルナンバーは ${SERIAL_MAX} 文字固定です`;
  if (!PRINTABLE_ASCII_RE.test(value)) return 'シリアルナンバーは半角ASCII文字で入力してください';
  if (!SERIAL_RE.test(value)) return '形式が不正です (例: GM 00000000-00)';
  return '';
}

function collectAndValidateSettings({ showError = true } = {}) {
  const title = el.settingTitle.value.trim();
  const author = el.settingAuthor.value.trim();
  const serial = el.settingSerial.value.trim().toUpperCase();

  const errors = {
    title: validateTitle(title),
    author: validateAuthor(author),
    serial: validateSerial(serial),
  };

  if (showError) {
    setFieldError(el.settingTitle, el.settingTitleError, errors.title);
    setFieldError(el.settingAuthor, el.settingAuthorError, errors.author);
    setFieldError(el.settingSerial, el.settingSerialError, errors.serial);
  }

  const valid = !errors.title && !errors.author && !errors.serial;
  return {
    valid,
    errors,
    config: {
      title: title || state.projectConfig.title,
      author: author || state.projectConfig.author,
      serial: serial || state.projectConfig.serial,
      region: 'JUE',
    },
  };
}

async function loadProjectConfig() {
  try {
    const cfg = await window.electronAPI.getProjectConfig();
    if (cfg) {
      const normalized = {
        title: cfg.title || cfg.romName || state.projectConfig.title,
        author: cfg.author || state.projectConfig.author,
        serial: cfg.serial || state.projectConfig.serial,
        region: 'JUE',
      };
      state.projectConfig = { ...state.projectConfig, ...normalized };
      el.settingTitle.value   = state.projectConfig.title;
      el.settingAuthor.value  = state.projectConfig.author;
      el.settingSerial.value  = state.projectConfig.serial;
      updateProjectNameDisplay();
      collectAndValidateSettings({ showError: true });
    }
    const romPath = await window.electronAPI.getRomPath();
    if (romPath) {
      state.lastRomPath = romPath;
      el.settingOutputPath.value = romPath;
    }
    updateRomOutputActions();
  } catch (_err) {
    // 初回起動など、設定が無い場合は無視
  }
}

async function saveSettings() {
  const result = collectAndValidateSettings({ showError: true });
  if (!result.valid) {
    el.settingsSavedMsg.textContent = '✕ 入力内容を修正してください';
    return;
  }
  state.projectConfig = result.config;
  el.settingSerial.value = state.projectConfig.serial;
  updateProjectNameDisplay();
  // 保存は generateProject 時に行うため、ここではメモリのみ更新
  el.settingsSavedMsg.textContent = '✓ 設定を保存しました';
  setTimeout(() => { el.settingsSavedMsg.textContent = ''; }, 2000);
}

// ============================================================== BUILD ===

async function runBuild() {
  if (state.building) return;

  const sourceCode = el.codeEditor.value.trim();
  if (!sourceCode) {
    switchPage('code');
    el.codeStatus.textContent = '⚠ ソースコードが空です。サンプル生成ボタンでサンプルを読み込んでください。';
    setLogOpen(true);
    setBuildStatus('error', 'ソースコードが空です');
    return;
  }

  state.building = true;
  el.btnBuild.classList.add('building');
  el.btnBuild.disabled = true;
  clearBuildLog();
  setLogOpen(true);
  setBuildStatus('building', 'ビルド中...');
  el.buildRomSize.textContent = '';
  appendBuildLog('=== MD Game Editor Build ===');
  appendBuildLog(`プロジェクト: ${state.projectConfig.title}`);
  appendBuildLog('');

  try {
    const settingsResult = collectAndValidateSettings({ showError: true });
    if (!settingsResult.valid) {
      appendBuildLog('[ERROR] プロジェクト設定に不正な値があります。Settings を確認してください。', 'error');
      setBuildStatus('error', '設定エラー');
      return;
    }
    state.projectConfig = settingsResult.config;
    updateProjectNameDisplay();

    // 1. ソースを生成
    const genResult = await window.electronAPI.generateProject(sourceCode, state.projectConfig);
    if (!genResult.ok) {
      appendBuildLog(`[ERROR] プロジェクト生成失敗: ${genResult.error}`, 'error');
      setBuildStatus('error', 'プロジェクト生成失敗');
      return;
    }
    appendBuildLog(`[INFO] プロジェクト生成: ${genResult.projectDir}`);

    // 2. ビルド実行（ログは IPC イベントでストリーム）
    const buildResult = await window.electronAPI.runBuild();

    if (buildResult.success) {
      state.lastRomPath = buildResult.romPath;
      el.settingOutputPath.value = buildResult.romPath;
      updateRomOutputActions();
      const sizeKb = buildResult.romSize != null ? `${(buildResult.romSize / 1024).toFixed(1)} KB` : '';
      el.buildRomSize.textContent = sizeKb ? `ROM: ${sizeKb}` : '';
      setBuildStatus('success', '✓ ビルド成功');
      appendBuildLog('');
      appendBuildLog(`=== ビルド成功 (${sizeKb}) ===`);
    } else {
      setBuildStatus('error', '✕ ビルド失敗');
      appendBuildLog('');
      appendBuildLog(`=== ビルド失敗: ${buildResult.error || ''} ===`, 'error');
    }
  } catch (err) {
    const msg = err.message || String(err);
    appendBuildLog(`[ERROR] ${msg}`, 'error');
    setBuildStatus('error', '✕ エラー');
  } finally {
    state.building = false;
    el.btnBuild.classList.remove('building');
    el.btnBuild.disabled = false;
  }
}

// ========================================================= TEST PLAY ===

async function openTestPlay() {
  const romPath = state.lastRomPath || (await window.electronAPI.getRomPath());
  if (!romPath) {
    setLogOpen(true);
    appendBuildLog('[WARN] ROM が見つかりません。先に Build を実行してください。');
    setBuildStatus('error', 'ROM なし');
    return;
  }
  try {
    await window.electronAPI.openTestPlayWindow(romPath);
  } catch (err) {
    appendBuildLog(`[ERROR] テストプレイ起動失敗: ${err.message}`, 'error');
  }
}

// ========================================================= MAP CANVAS ===

function drawDummyMap() {
  const canvas = $('mapCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const COLS = 64, ROWS = 56, TILE = 8;
  canvas.width  = COLS * TILE;
  canvas.height = ROWS * TILE;
  const colors = ['#0a1428', '#0e1e38', '#0a2818', '#1a1020'];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const ci = Math.floor(Math.random() * colors.length);
      ctx.fillStyle = colors[ci];
      ctx.fillRect(c * TILE, r * TILE, TILE, TILE);
    }
  }
  ctx.strokeStyle = '#1e2a40';
  ctx.lineWidth = 0.5;
  for (let r = 0; r <= ROWS; r++) {
    ctx.beginPath(); ctx.moveTo(0, r * TILE); ctx.lineTo(COLS * TILE, r * TILE); ctx.stroke();
  }
  for (let c = 0; c <= COLS; c++) {
    ctx.beginPath(); ctx.moveTo(c * TILE, 0); ctx.lineTo(c * TILE, ROWS * TILE); ctx.stroke();
  }
}

function buildTilePalette() {
  const grid = $('tilePaletteGrid');
  if (!grid) return;
  const palColors = [
    '#0a1428','#0e1e38','#0a2818','#1a1020',
    '#1e3060','#203828','#381e60','#382018',
    '#4040a0','#40a060','#a04080','#a08040',
  ];
  palColors.forEach((color, i) => {
    const div = document.createElement('div');
    div.className = 'tile-swatch' + (i === 0 ? ' active' : '');
    div.style.background = color;
    div.title = `Tile ${i}`;
    div.addEventListener('click', () => {
      grid.querySelectorAll('.tile-swatch').forEach((s) => s.classList.remove('active'));
      div.classList.add('active');
    });
    grid.appendChild(div);
  });
}

// ======================================================= ASSET TABLE ===

function bindAssetTable() {
  const rows = document.querySelectorAll('.asset-row');
  const assetData = {
    player_sprite: { name: 'player_sprite', type: 'Sprite', size: '16 × 16 px', palette: 'PAL0', color: '#1e3060' },
    bg_tileset:    { name: 'bg_tileset',    type: 'Tileset', size: '16 tiles (128px)', palette: 'PAL1', color: '#1e3828' },
    main_bgm:      { name: 'main_bgm',      type: 'Music (BGM)', size: '2:30 / XGM2', palette: '—', color: '#2e1e3a' },
  };
  rows.forEach((row) => {
    row.addEventListener('click', () => {
      rows.forEach((r) => r.classList.remove('active'));
      row.classList.add('active');
      const key = row.dataset.asset;
      const d = assetData[key];
      if (d) {
        $('infoName').textContent    = d.name;
        $('infoType').textContent    = d.type;
        $('infoSize').textContent    = d.size;
        $('infoPalette').textContent = d.palette;
        const preview = $('assetPreview');
        preview.innerHTML = '';
        const box = document.createElement('div');
        box.style.cssText = `width:80px;height:80px;border-radius:8px;background:${d.color};display:flex;align-items:center;justify-content:center;font-size:11px;color:#8b98ab;`;
        box.textContent = d.type;
        preview.appendChild(box);
      }
    });
  });
}

// ====================================================== ABOUT DIALOG ===

function closeAboutDialog() {
  if (!el.aboutModal) {
    return;
  }
  el.aboutModal.classList.remove('open');
  el.aboutModal.setAttribute('aria-hidden', 'true');
}

async function openAboutDialog() {
  if (!el.aboutModal) {
    return;
  }
  el.aboutModal.classList.add('open');
  el.aboutModal.setAttribute('aria-hidden', 'false');

  try {
    const info = await window.electronAPI.getAppInfo();
    if (!info) {
      return;
    }
    const wasm = info.embeddedWasm || {};
    if (el.aboutTitle) {
      el.aboutTitle.textContent = info.appName || 'MD Game Editor';
    }
    if (el.aboutDescription) {
      el.aboutDescription.textContent = info.appDescription || 'Embedded emulator information';
    }
    if (el.aboutAppVersion) {
      el.aboutAppVersion.textContent = info.appVersion || 'unknown';
    }
    if (el.aboutWasmBuildVersion) {
      el.aboutWasmBuildVersion.textContent = wasm.buildVersion || 'unknown';
    }
    if (el.aboutWasmPackageVersion) {
      el.aboutWasmPackageVersion.textContent = wasm.packageVersion || 'unknown';
    }
    if (el.aboutElectronVersion) {
      el.aboutElectronVersion.textContent = info.electronVersion || 'unknown';
    }
    if (el.aboutChromeVersion) {
      el.aboutChromeVersion.textContent = info.chromeVersion || 'unknown';
    }
    if (el.aboutNodeVersion) {
      el.aboutNodeVersion.textContent = info.nodeVersion || 'unknown';
    }
    if (el.aboutPlatform) {
      el.aboutPlatform.textContent = info.platform || 'unknown';
    }
    if (el.aboutArch) {
      el.aboutArch.textContent = info.arch || 'unknown';
    }
    if (el.aboutAppPath) {
      el.aboutAppPath.textContent = info.appPath || 'unknown';
    }
  } catch (_err) {
    if (el.aboutWasmBuildVersion) {
      el.aboutWasmBuildVersion.textContent = 'failed to load';
    }
  }
}

// ====================================================== EVENT BINDING ===

function bindEvents() {
  // Sidebar navigation
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchPage(btn.dataset.page));
  });

  // Topbar buttons
  el.btnBuild.addEventListener('click', runBuild);
  el.btnTestPlay.addEventListener('click', openTestPlay);
  $('btnOpenSetup').addEventListener('click', () => {
    window.electronAPI.openSetupWindow();
  });

  // Code page
  el.btnGenSample.addEventListener('click', () => {
    loadSampleCode();
    switchPage('code');
  });
  el.btnSaveCode.addEventListener('click', async () => {
    const code = el.codeEditor.value;
    try {
      await window.electronAPI.generateProject(code, state.projectConfig);
      el.codeStatus.textContent = '✓ コードを保存しました';
      setTimeout(() => { el.codeStatus.textContent = ''; }, 2000);
    } catch (err) {
      el.codeStatus.textContent = `保存エラー: ${err.message}`;
    }
  });
  el.btnCopyCode.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(el.codeEditor.value);
      el.codeStatus.textContent = '✓ クリップボードにコピーしました';
      setTimeout(() => { el.codeStatus.textContent = ''; }, 2000);
    } catch (_err) {
      el.codeStatus.textContent = 'コピーに失敗しました';
    }
  });

  // Settings page
  el.btnSaveSettings.addEventListener('click', saveSettings);
  el.settingTitle.addEventListener('input', () => {
    state.projectConfig.title = el.settingTitle.value;
    updateProjectNameDisplay();
    collectAndValidateSettings({ showError: true });
  });
  el.settingAuthor.addEventListener('input', () => collectAndValidateSettings({ showError: true }));
  el.settingSerial.addEventListener('input', () => {
    el.settingSerial.value = el.settingSerial.value.toUpperCase();
    collectAndValidateSettings({ showError: true });
  });
  el.btnOpenOutputFolder.addEventListener('click', async () => {
    if (!state.lastRomPath) {
      el.settingsSavedMsg.textContent = 'ROM 出力先がまだありません。先にビルドしてください。';
      return;
    }
    const result = await window.electronAPI.openPathInExplorer(state.lastRomPath, { parentOnly: true });
    if (!result?.ok) {
      el.settingsSavedMsg.textContent = `フォルダを開けませんでした: ${result?.error || 'unknown'}`;
    }
  });
  el.btnDownloadRom.addEventListener('click', async () => {
    if (!state.lastRomPath) {
      return;
    }
    const result = await window.electronAPI.saveRomAs(state.lastRomPath);
    if (result?.ok) {
      el.settingsSavedMsg.textContent = `✓ 保存しました: ${result.path}`;
      setTimeout(() => { el.settingsSavedMsg.textContent = ''; }, 2500);
    } else if (!result?.canceled) {
      el.settingsSavedMsg.textContent = `保存に失敗: ${result?.error || 'unknown'}`;
    }
  });

  if (el.btnAboutClose) {
    el.btnAboutClose.addEventListener('click', closeAboutDialog);
  }
  if (el.aboutBackdrop) {
    el.aboutBackdrop.addEventListener('click', closeAboutDialog);
  }

  // Build log
  el.buildLogHeader.addEventListener('click', () => setLogOpen(!state.logOpen));
  el.btnCopyLog.addEventListener('click', async (e) => {
    e.stopPropagation();
    await copyBuildLog();
  });
  el.btnClearLog.addEventListener('click', (e) => { e.stopPropagation(); clearBuildLog(); });
  el.btnToggleLog.addEventListener('click', (e) => { e.stopPropagation(); setLogOpen(!state.logOpen); });

  if (el.buildLogResizer) {
    let dragStartY = 0;
    let dragStartHeight = 0;
    const onMouseMove = (event) => {
      const delta = dragStartY - event.clientY;
      setLogOpenHeight(dragStartHeight + delta);
    };
    const onMouseUp = () => {
      el.buildLogResizer.classList.remove('dragging');
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    el.buildLogResizer.addEventListener('mousedown', (event) => {
      if (!state.logOpen) {
        return;
      }
      event.preventDefault();
      dragStartY = event.clientY;
      dragStartHeight = state.logOpenHeight;
      el.buildLogResizer.classList.add('dragging');
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });
  }

  // IPC events
  window.electronAPI.onBuildLog((payload) => {
    appendBuildLog(payload.text || '', payload.level);
    setLogOpen(true);
  });

  window.electronAPI.onBuildEnd((payload) => {
    if (payload.success) {
      state.lastRomPath = payload.romPath;
      if (payload.romPath) el.settingOutputPath.value = payload.romPath;
      updateRomOutputActions();
      const sizeKb = payload.romSize != null ? `${(payload.romSize / 1024).toFixed(1)} KB` : '';
      el.buildRomSize.textContent = sizeKb ? `ROM: ${sizeKb}` : '';
      setBuildStatus('success', '✓ ビルド成功');
    } else {
      setBuildStatus('error', '✕ ビルド失敗');
    }
  });

  // Menu → Setup message handler
  window.electronAPI.onMenuOpenSetup?.(() => {
    switchPage('settings');
    window.electronAPI.openSetupWindow();
  });

  window.electronAPI.onMenuOpenAbout?.(() => {
    openAboutDialog();
  });

  // Keyboard shortcut: Ctrl/Cmd+B = Build
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && el.aboutModal?.classList.contains('open')) {
      e.preventDefault();
      closeAboutDialog();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      runBuild();
    }
  });
}

// ============================================================ BOOTSTRAP ===

async function bootstrap() {
  setLogOpenHeight(state.logOpenHeight);
  setLogOpen(false);
  bindEvents();
  bindAssetTable();
  drawDummyMap();
  buildTilePalette();
  await loadProjectConfig();

  // サンプルコードを初期表示
  if (!el.codeEditor.value) {
    loadSampleCode();
  }
}

bootstrap();
