/**
 * MD Game Editor - renderer.js
 * エディタのフロントエンドロジック
 */

// ------------------------------------------------------------------ state --
const state = {
  currentPage: 'assets',
  logOpen: false,
  building: false,
  lastRomPath: null,
  projectConfig: { romName: 'MY GAME', author: 'AUTHOR', region: 'JP' },
};

// -------------------------------------------------------------------- DOM --
const $ = (id) => document.getElementById(id);

const el = {
  btnBuild:       $('btnBuild'),
  btnTestPlay:    $('btnTestPlay'),
  btnDebug:       $('btnDebug'),
  btnSetup:       $('btnSetup'),
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
  mainLayout:     document.querySelector('.main-layout'),
  // code page
  codeEditor:     $('codeEditor'),
  codeStatus:     $('codeStatus'),
  btnGenSample:   $('btnGenSample'),
  btnSaveCode:    $('btnSaveCode'),
  btnCopyCode:    $('btnCopyCode'),
  // settings page
  settingRomName:  $('settingRomName'),
  settingAuthor:   $('settingAuthor'),
  settingRegion:   $('settingRegion'),
  settingOutputPath: $('settingOutputPath'),
  btnSaveSettings:  $('btnSaveSettings'),
  settingsSavedMsg: $('settingsSavedMsg'),
};

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
  // chevron
  const use = el.btnToggleLog.querySelector('use');
  if (use) use.setAttribute('href', open ? '#icon-chevron-down' : '#icon-chevron-up');
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
  el.projectName.textContent = state.projectConfig.romName || 'MY GAME';
}

async function loadProjectConfig() {
  try {
    const cfg = await window.electronAPI.getProjectConfig();
    if (cfg) {
      state.projectConfig = { ...state.projectConfig, ...cfg };
      el.settingRomName.value  = cfg.romName  || state.projectConfig.romName;
      el.settingAuthor.value   = cfg.author   || state.projectConfig.author;
      el.settingRegion.value   = cfg.region   || state.projectConfig.region;
      updateProjectNameDisplay();
    }
    const romPath = await window.electronAPI.getRomPath();
    if (romPath) {
      state.lastRomPath = romPath;
      el.settingOutputPath.value = romPath;
    }
  } catch (_err) {
    // 初回起動など、設定が無い場合は無視
  }
}

async function saveSettings() {
  const cfg = {
    romName: el.settingRomName.value.trim() || 'MY GAME',
    author:  el.settingAuthor.value.trim()  || 'AUTHOR',
    region:  el.settingRegion.value,
  };
  state.projectConfig = cfg;
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
  appendBuildLog(`プロジェクト: ${state.projectConfig.romName}`);
  appendBuildLog('');

  try {
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

// ====================================================== EVENT BINDING ===

function bindEvents() {
  // Sidebar navigation
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchPage(btn.dataset.page));
  });

  // Topbar buttons
  el.btnBuild.addEventListener('click', runBuild);
  el.btnTestPlay.addEventListener('click', openTestPlay);
  el.btnDebug.addEventListener('click', () => {
    window.electronAPI.openDebugWindow({ mode: 'wasm' });
  });
  el.btnSetup.addEventListener('click', () => {
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
  el.settingRomName.addEventListener('input', () => {
    state.projectConfig.romName = el.settingRomName.value;
    updateProjectNameDisplay();
  });

  // Build log
  el.buildLogHeader.addEventListener('click', () => setLogOpen(!state.logOpen));
  el.btnCopyLog.addEventListener('click', async (e) => {
    e.stopPropagation();
    await copyBuildLog();
  });
  el.btnClearLog.addEventListener('click', (e) => { e.stopPropagation(); clearBuildLog(); });
  el.btnToggleLog.addEventListener('click', (e) => { e.stopPropagation(); setLogOpen(!state.logOpen); });

  // IPC events
  window.electronAPI.onBuildLog((payload) => {
    appendBuildLog(payload.text || '', payload.level);
    setLogOpen(true);
  });

  window.electronAPI.onBuildEnd((payload) => {
    if (payload.success) {
      state.lastRomPath = payload.romPath;
      if (payload.romPath) el.settingOutputPath.value = payload.romPath;
      const sizeKb = payload.romSize != null ? `${(payload.romSize / 1024).toFixed(1)} KB` : '';
      el.buildRomSize.textContent = sizeKb ? `ROM: ${sizeKb}` : '';
      setBuildStatus('success', '✓ ビルド成功');
    } else {
      setBuildStatus('error', '✕ ビルド失敗');
    }
  });

  // Keyboard shortcut: Ctrl/Cmd+B = Build
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      runBuild();
    }
  });
}

// ============================================================ BOOTSTRAP ===

async function bootstrap() {
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
