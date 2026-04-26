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
  project: {
    dir: '',
    name: '',
    projectsRootDir: '',
    availableProjects: [],
  },
  preview: {
    audio: null,
    audioEntryId: '',
    imageEntryId: '',
    imageZoom: 'fit',
    imageNaturalWidth: 0,
    imageNaturalHeight: 0,
    paramsOpen: true,
    previewOpen: true,
    panelOpen: true,
  },
  rescomp: {
    resRoot: '',
    files: [],
    selectedFile: '',
    selectedEntryLine: null,
    searchText: '',
    pendingImageSource: null,
    pendingAssetPick: null,
  },
};

const TYPE_OPTIONS = ['PALETTE', 'IMAGE', 'BITMAP', 'SPRITE', 'XGM', 'XGM2', 'WAV', 'MAP', 'TILEMAP', 'TILESET'];
const COMPRESSION_OPTIONS = ['AUTO', 'NONE', 'APLIB', 'LZ4W'];
const MAP_OPT_OPTIONS = ['NONE', 'ALL', 'DUPLICATE'];
const ORDERING_OPTIONS = ['ROW', 'COLUMN'];
const COLLISION_OPTIONS = ['NONE', 'CIRCLE', 'BOX'];
const SPRITE_OPT_TYPE_OPTIONS = ['BALANCED', 'SPRITE', 'TILE', 'NONE'];
const SPRITE_OPT_LEVEL_OPTIONS = ['FAST', 'MEDIUM', 'SLOW', 'MAX'];
const BOOLEAN_WORD_OPTIONS = ['TRUE', 'FALSE'];
const XGM_TIMING_OPTIONS = ['AUTO', 'NTSC', 'PAL'];
const WAV_DRIVER_OPTIONS = ['DEFAULT', 'PCM', 'DPCM2', 'PCM4', 'XGM', 'XGM2'];
const IMAGE_EXTS = ['.png', '.bmp'];

const FORM_FIELDS_BY_TYPE = {
  PALETTE: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力ファイル', type: 'text' },
  ],
  IMAGE: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
    { key: 'mapOpt', label: 'map_opt', type: 'select', options: MAP_OPT_OPTIONS },
    { key: 'mapBase', label: 'map_base', type: 'text' },
  ],
  BITMAP: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
  ],
  SPRITE: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像', type: 'text' },
    { key: 'width', label: 'フレーム幅', type: 'text' },
    { key: 'height', label: 'フレーム高', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
    { key: 'time', label: 'time', type: 'text' },
    { key: 'collision', label: 'collision', type: 'select', options: COLLISION_OPTIONS },
    { key: 'optType', label: 'opt_type', type: 'select', options: SPRITE_OPT_TYPE_OPTIONS },
    { key: 'optLevel', label: 'opt_level', type: 'select', options: SPRITE_OPT_LEVEL_OPTIONS },
    { key: 'optDuplicate', label: 'opt_duplicate', type: 'select', options: BOOLEAN_WORD_OPTIONS },
  ],
  XGM: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力音源', type: 'text' },
    { key: 'timing', label: 'timing', type: 'select', options: XGM_TIMING_OPTIONS },
    { key: 'options', label: 'options', type: 'text' },
  ],
  XGM2: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力音源(1つ目)', type: 'text' },
    { key: 'options', label: 'options', type: 'text' },
  ],
  WAV: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力wav', type: 'text' },
    { key: 'driver', label: 'driver', type: 'select', options: WAV_DRIVER_OPTIONS },
    { key: 'outRate', label: 'out_rate', type: 'text' },
    { key: 'far', label: 'far', type: 'select', options: BOOLEAN_WORD_OPTIONS },
  ],
  MAP: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像/TMX', type: 'text' },
    { key: 'tileset', label: 'tileset_id', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
    { key: 'mapBase', label: 'map_base', type: 'text' },
    { key: 'ordering', label: 'ordering', type: 'select', options: ORDERING_OPTIONS },
  ],
  TILEMAP: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像/TMX', type: 'text' },
    { key: 'tileset', label: 'tileset_id', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
    { key: 'mapOpt', label: 'map_opt', type: 'select', options: MAP_OPT_OPTIONS },
    { key: 'mapBase', label: 'map_base', type: 'text' },
    { key: 'ordering', label: 'ordering', type: 'select', options: ORDERING_OPTIONS },
  ],
  TILESET: [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力画像/TSX', type: 'text' },
    { key: 'compression', label: '圧縮', type: 'select', options: COMPRESSION_OPTIONS },
    { key: 'opt', label: 'opt', type: 'select', options: MAP_OPT_OPTIONS },
    { key: 'ordering', label: 'ordering', type: 'select', options: ORDERING_OPTIONS },
    { key: 'export', label: 'export', type: 'select', options: BOOLEAN_WORD_OPTIONS },
  ],
};

const DITHER_PATTERNS = {
  diagonal4: [
    [0.0, 0.5, 0.125, 0.625],
    [0.75, 0.25, 0.875, 0.375],
    [0.1875, 0.6875, 0.0625, 0.5625],
    [0.9375, 0.4375, 0.8125, 0.3125],
  ],
  diagonal2: [
    [0.0, 0.5],
    [0.75, 0.25],
  ],
  horizontal4: [
    [0.1, 0.3, 0.6, 0.9],
    [0.1, 0.3, 0.6, 0.9],
    [0.1, 0.3, 0.6, 0.9],
    [0.1, 0.3, 0.6, 0.9],
  ],
  horizontal2: [
    [0.2, 0.8],
    [0.2, 0.8],
  ],
  vertical4: [
    [0.1, 0.1, 0.1, 0.1],
    [0.3, 0.3, 0.3, 0.3],
    [0.6, 0.6, 0.6, 0.6],
    [0.9, 0.9, 0.9, 0.9],
  ],
  vertical2: [
    [0.25, 0.25],
    [0.75, 0.75],
  ],
};

const quantizeState = {
  active: false,
  originalCanvas: null,
  originalCtx: null,
  originalData: null,
  convertedDataUrl: '',
  onApply: null,
};

// -------------------------------------------------------------------- DOM --
const $ = (id) => document.getElementById(id);

const el = {
  btnBuild: $('btnBuild'),
  btnTestPlay: $('btnTestPlay'),
  btnNewProject: $('btnNewProject'),
  btnOpenProject: $('btnOpenProject'),
  projectName: $('projectName'),
  projectDirLabel: $('projectDirLabel'),
  buildLog: $('buildLog'),
  buildLogBar: $('buildLogBar'),
  buildLogBody: $('buildLogBody'),
  buildStatusBadge: $('buildStatusBadge'),
  buildRomSize: $('buildRomSize'),
  btnCopyLog: $('btnCopyLog'),
  btnToggleLog: $('btnToggleLog'),
  btnClearLog: $('btnClearLog'),
  buildLogHeader: $('buildLogHeader'),
  buildLogResizer: $('buildLogResizer'),
  mainLayout: document.querySelector('.main-layout'),
  codeEditor: $('codeEditor'),
  codeStatus: $('codeStatus'),
  btnGenSample: $('btnGenSample'),
  btnSaveCode: $('btnSaveCode'),
  btnCopyCode: $('btnCopyCode'),
  settingTitle: $('settingTitle'),
  settingAuthor: $('settingAuthor'),
  settingSerial: $('settingSerial'),
  settingTitleError: $('settingTitleError'),
  settingAuthorError: $('settingAuthorError'),
  settingSerialError: $('settingSerialError'),
  settingOutputPath: $('settingOutputPath'),
  currentProjectDir: $('currentProjectDir'),
  btnOpenProjectDir: $('btnOpenProjectDir'),
  btnSettingsProjectPicker: $('btnSettingsProjectPicker'),
  btnOpenOutputFolder: $('btnOpenOutputFolder'),
  btnDownloadRom: $('btnDownloadRom'),
  btnSaveSettings: $('btnSaveSettings'),
  settingsSavedMsg: $('settingsSavedMsg'),
  pluginList: $('pluginList'),
  btnReloadPlugins: $('btnReloadPlugins'),
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
  btnOpenResDir: $('btnOpenResDir'),
  btnCreateResFile: $('btnCreateResFile'),
  btnAddAsset: $('btnAddAsset'),
  resFileModal: $('resFileModal'),
  btnResFileModalClose: $('btnResFileModalClose'),
  btnResFileCancel: $('btnResFileCancel'),
  btnResFileCreate: $('btnResFileCreate'),
  resFileNameInput: $('resFileNameInput'),
  assetModal: $('assetModal'),
  btnAssetModalClose: $('btnAssetModalClose'),
  btnAssetModalCancel: $('btnAssetModalCancel'),
  btnAssetModalCreate: $('btnAssetModalCreate'),
  assetSourcePathInput: $('assetSourcePathInput'),
  assetTypeInput: $('assetTypeInput'),
  assetResFileInput: $('assetResFileInput'),
  assetTargetSubdirInput: $('assetTargetSubdirInput'),
  assetTargetFileNameInput: $('assetTargetFileNameInput'),
  assetSymbolNameInput: $('assetSymbolNameInput'),
  projectModal: $('projectModal'),
  btnProjectModalClose: $('btnProjectModalClose'),
  btnProjectModalCancel: $('btnProjectModalCancel'),
  btnProjectModalCreate: $('btnProjectModalCreate'),
  projectSystemNameInput: $('projectSystemNameInput'),
  projectTitleInput: $('projectTitleInput'),
  projectAuthorInput: $('projectAuthorInput'),
  projectSerialInput: $('projectSerialInput'),
  projectPickerModal: $('projectPickerModal'),
  btnProjectPickerClose: $('btnProjectPickerClose'),
  btnProjectPickerCancel: $('btnProjectPickerCancel'),
  projectPickerRoot: $('projectPickerRoot'),
  projectPickerList: $('projectPickerList'),
  resFileSelect: $('resFileSelect'),
  assetSearchInput: $('assetSearchInput'),
  assetTableBody: $('assetTableBody'),
  assetTableHint: $('assetTableHint'),
  assetEditForm: $('assetEditForm'),
  assetNoSelectionHint: $('assetNoSelectionHint'),
  assetEditorPanel: $('assetEditorPanel'),
  assetEditorActions: $('assetEditorActions'),
  btnDeleteAssetEntry: $('btnDeleteAssetEntry'),
  btnTogglePreviewPanel: $('btnTogglePreviewPanel'),
  assetsLayout: $('assetsLayout'),
  assetPreviewPanel: $('assetPreviewPanel'),
  btnAccordionParams: $('btnAccordionParams'),
  accordionParamsBody: $('accordionParamsBody'),
  btnAccordionPreview: $('btnAccordionPreview'),
  accordionPreviewBody: $('accordionPreviewBody'),
  inlineImagePreview: $('inlineImagePreview'),
  inlinePreviewInfo: $('inlinePreviewInfo'),
  inlineImageZoom: $('inlineImageZoom'),
  inlineImageFrame: $('inlineImageFrame'),
  inlinePreviewImage: $('inlinePreviewImage'),
  inlinePalette: $('inlinePalette'),
  inlineAudioPreview: $('inlineAudioPreview'),
  audioPreviewMeta: $('audioPreviewMeta'),
  audioPlayer: $('audioPlayer'),
  btnAudioPlay: $('btnAudioPlay'),
  audioPlayIcon: $('audioPlayIcon'),
  audioSeek: $('audioSeek'),
  audioTime: $('audioTime'),
  inlineNoPreview: $('inlineNoPreview'),
  assetCommentInput: $('assetCommentInput'),
  resizeModal: $('resizeModal'),
  btnResizeModalClose: $('btnResizeModalClose'),
  resizeMode: $('resizeMode'),
  resizeDimGroup: $('resizeDimGroup'),
  resizeWidth: $('resizeWidth'),
  resizeHeight: $('resizeHeight'),
  resizeValidationMessage: $('resizeValidationMessage'),
  resizeOriginalSize: $('resizeOriginalSize'),
  resizePreviewCanvas: $('resizePreviewCanvas'),
  btnResizeCancel: $('btnResizeCancel'),
  btnResizeSkip: $('btnResizeSkip'),
  btnResizeApply: $('btnResizeApply'),
  quantizeModal: $('quantizeModal'),
  quantizeBackdrop: $('quantizeBackdrop'),
  btnQuantizeClose: $('btnQuantizeClose'),
  btnQuantizeCancel: $('btnQuantizeCancel'),
  btnQuantizeApply: $('btnQuantizeApply'),
  quantizeTransparencyMode: $('quantizeTransparencyMode'),
  quantizeColorPickerRow: $('quantizeColorPickerRow'),
  quantizeTransparencyColor: $('quantizeTransparencyColor'),
  quantizeTransparencyColorValue: $('quantizeTransparencyColorValue'),
  quantizeTransparencyColorSwatch: $('quantizeTransparencyColorSwatch'),
  quantizeUseSharedCustomColor: $('quantizeUseSharedCustomColor'),
  quantizeSharedColorRow: $('quantizeSharedColorRow'),
  quantizeDitheringEnabled: $('quantizeDitheringEnabled'),
  quantizeDitheringWeight: $('quantizeDitheringWeight'),
  quantizeWeightLabel: $('quantizeWeightLabel'),
  quantizePattern: $('quantizePattern'),
  quantizeBeforeCanvas: $('quantizeBeforeCanvas'),
  quantizeAfterCanvas: $('quantizeAfterCanvas'),
  quantizeStats: $('quantizeStats'),
};

const TITLE_MAX = 48;
const AUTHOR_MAX = 16;
const SERIAL_MAX = 14;
const PRINTABLE_ASCII_RE = /^[\x20-\x7E]+$/;
const SERIAL_RE = /^[A-Z]{2}\s[0-9A-Z]{8}-[0-9A-Z]{2}$/;

// ============================================================ BUILD LOG ===

function appendBuildLog(text, level = 'info') {
  const pre = el.buildLog;
  if (!pre) return;
  if (level === 'error') {
    pre.textContent += text + '\n';
  } else {
    pre.textContent += text + '\n';
  }
  pre.scrollTop = pre.scrollHeight;
}

function clearBuildLog() {
  if (el.buildLog) {
    el.buildLog.textContent = '';
  }
}

function updateRomOutputActions() {
  const hasRom = !!state.lastRomPath;
  if (el.btnDownloadRom) {
    el.btnDownloadRom.disabled = !hasRom;
    el.btnDownloadRom.style.display = hasRom ? 'inline-flex' : 'none';
  }
}

async function copyBuildLog() {
  const text = el.buildLog?.textContent || '';
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
  if (!el.buildStatusBadge) return;
  el.buildStatusBadge.textContent = text;
  el.buildStatusBadge.className = 'build-status-badge ' + (type || '');
}

function setLogOpen(open) {
  state.logOpen = open;
  el.buildLogBar?.classList.toggle('open', open);
  el.mainLayout?.classList.toggle('log-open', open);
  if (el.buildLogResizer) {
    el.buildLogResizer.style.display = open ? 'block' : 'none';
  }
  const use = el.btnToggleLog?.querySelector('use');
  if (use) use.setAttribute('href', open ? '#icon-chevron-down' : '#icon-chevron-up');
}

function setLogOpenHeight(height) {
  const minHeight = 140;
  const maxHeight = Math.max(minHeight, Math.floor(window.innerHeight * 0.75));
  const next = Math.max(minHeight, Math.min(maxHeight, Number(height) || state.logOpenHeight));
  state.logOpenHeight = next;
  document.documentElement.style.setProperty('--log-h-open', `${next}px`);
}

// ============================================================= PLUGINS ===

const pluginState = {
  plugins: [],
  generating: {},
  /** 現在ビルダーとして使用中のプラグイン ID (null = コードエディタ使用) */
  activeBuilderPlugin: null,
};

async function setActiveBuilderPlugin(id) {
  pluginState.activeBuilderPlugin = id || null;
  try {
    await window.electronAPI.setBuilderPlugin(id || null);
  } catch (_) {}
  updateBuildButtonLabel();
  renderPluginList();
}

function updateBuildButtonLabel() {
  if (!el.btnBuild) return;
  const id = pluginState.activeBuilderPlugin;
  if (id) {
    const p = pluginState.plugins.find((x) => x.id === id);
    el.btnBuild.title = `ビルダー: ${p ? p.name : id}`;
    el.btnBuild.dataset.pluginBuilder = id;
  } else {
    el.btnBuild.title = '';
    delete el.btnBuild.dataset.pluginBuilder;
  }
}

async function loadPlugins() {
  if (!el.pluginList) return;
  el.pluginList.innerHTML = '<p class="hint-text">読み込み中...</p>';
  try {
    pluginState.plugins = await window.electronAPI.listPlugins();
  } catch (_) {
    pluginState.plugins = [];
  }

  // プロジェクトに保存されているビルダーを読み込む
  try {
    const saved = await window.electronAPI.getBuilderPlugin();
    pluginState.activeBuilderPlugin = saved.id || null;
  } catch (_) {
    pluginState.activeBuilderPlugin = null;
  }

  // 未設定 & スライドショープラグインが有効なら自動でデフォルトに設定
  if (!pluginState.activeBuilderPlugin) {
    const slideshow = pluginState.plugins.find(
      (p) => p.id === 'slideshow' && p.enabled && p.hasGenerator,
    );
    if (slideshow) {
      pluginState.activeBuilderPlugin = slideshow.id;
      try {
        await window.electronAPI.setBuilderPlugin(slideshow.id);
      } catch (_) {}
    }
  }

  updateBuildButtonLabel();
  renderPluginList();
}

function renderPluginList() {
  if (!el.pluginList) return;
  if (pluginState.plugins.length === 0) {
    el.pluginList.innerHTML = '<p class="hint-text">electron/plugins/ フォルダにプラグインが見つかりません。</p>';
    return;
  }

  el.pluginList.innerHTML = '';
  pluginState.plugins.forEach((plugin) => {
    const isActiveBuilder = pluginState.activeBuilderPlugin === plugin.id;
    const card = document.createElement('div');
    card.className = `plugin-card${plugin.enabled ? '' : ' plugin-card-disabled'}${isActiveBuilder ? ' plugin-card-active-builder' : ''}`;
    card.dataset.id = plugin.id;

    const isBusy = Boolean(pluginState.generating[plugin.id]);

    card.innerHTML = `
      <div class="plugin-card-header">
        <div class="plugin-card-meta">
          <span class="plugin-card-name">${escHtml(plugin.name)}</span>
          <span class="plugin-card-version">v${escHtml(plugin.version)}</span>
          ${isActiveBuilder ? '<span class="plugin-builder-badge">🔨 ビルダー</span>' : ''}
        </div>
        <label class="plugin-toggle" title="${plugin.enabled ? '無効にする' : '有効にする'}">
          <input type="checkbox" class="plugin-toggle-input" data-plugin-id="${escHtml(plugin.id)}"
            ${plugin.enabled ? 'checked' : ''} />
          <span class="plugin-toggle-slider"></span>
        </label>
      </div>
      <p class="plugin-card-desc">${escHtml(plugin.description)}</p>
      <div class="plugin-card-actions">
        ${plugin.hasGenerator ? `
          <button class="btn-primary plugin-generate-btn" data-plugin-id="${escHtml(plugin.id)}"
            ${!plugin.enabled || isBusy ? 'disabled' : ''}>${isBusy ? '生成中...' : '🎮 生成 & ビルド'}</button>
          ${isActiveBuilder
            ? `<button class="btn-sm plugin-builder-clear-btn" title="ビルダーを解除してコードエディタに戻す">✕ ビルダー解除</button>`
            : `<button class="btn-sm plugin-set-builder-btn" ${!plugin.enabled ? 'disabled' : ''}
                title="この Generate をメインの Build ボタンと連動させる">🔨 ビルダーに設定</button>`
          }
        ` : ''}
        <span class="plugin-generate-result" id="plugin-result-${escHtml(plugin.id)}"></span>
      </div>
    `;

    // トグル
    const toggle = card.querySelector('.plugin-toggle-input');
    toggle?.addEventListener('change', async () => {
      await window.electronAPI.setPluginEnabled(plugin.id, toggle.checked);
      // アクティブビルダーが無効になった場合は解除
      if (!toggle.checked && pluginState.activeBuilderPlugin === plugin.id) {
        await setActiveBuilderPlugin(null);
      }
      await loadPlugins();
    });

    // 生成 & ビルドボタン
    const genBtn = card.querySelector('.plugin-generate-btn');
    genBtn?.addEventListener('click', async () => {
      await runPluginGenerateAndBuild(plugin.id);
    });

    // ビルダーに設定ボタン
    const setBuilderBtn = card.querySelector('.plugin-set-builder-btn');
    setBuilderBtn?.addEventListener('click', async () => {
      await setActiveBuilderPlugin(plugin.id);
    });

    // ビルダー解除ボタン
    const clearBuilderBtn = card.querySelector('.plugin-builder-clear-btn');
    clearBuilderBtn?.addEventListener('click', async () => {
      await setActiveBuilderPlugin(null);
    });

    el.pluginList.appendChild(card);
  });
}

/** プラグインで生成してすぐビルドまで実行する */
async function runPluginGenerateAndBuild(id) {
  pluginState.generating[id] = true;
  renderPluginList();
  const resultEl = document.getElementById(`plugin-result-${id}`);
  try {
    const genResult = await window.electronAPI.runPluginGenerator(id);
    if (!genResult.ok) {
      if (resultEl) {
        resultEl.className = 'plugin-generate-result plugin-result-err';
        resultEl.textContent = `✗ ${genResult.error || '生成失敗'}`;
      }
      return;
    }
    if (resultEl) {
      resultEl.className = 'plugin-generate-result plugin-result-ok';
      resultEl.textContent = '✓ main.c を生成しました — ビルド開始...';
    }
  } finally {
    pluginState.generating[id] = false;
    renderPluginList();
  }
  // Build を走らせる (プラグイン生成済みなので _generatedByPlugin フラグを立てる)
  await runBuild({ _generatedByPlugin: id });
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
  if (!el.codeEditor || !el.codeStatus) return;
  el.codeEditor.value = HELLO_WORLD_C;
  el.codeStatus.textContent = 'Hello World サンプルを読み込みました。Build ボタンでビルドできます。';
}

// ============================================================== SETTINGS ===

function updateProjectNameDisplay() {
  if (el.projectName) {
    el.projectName.textContent = state.projectConfig.title || 'MY GAME';
  }
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

function openModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.add('open');
  modalEl.setAttribute('aria-hidden', 'false');
}

function closeModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.remove('open');
  modalEl.setAttribute('aria-hidden', 'true');
}

function getModalPanel(modalEl) {
  return modalEl?.querySelector('.app-panel') || null;
}

function resetModalPanelPosition(modalEl) {
  const panel = getModalPanel(modalEl);
  if (!panel) return;
  panel.style.transform = '';
}

function setCurrentProjectInfo(info) {
  state.project.dir = info?.projectDir || '';
  state.project.name = info?.projectName || '';
  state.project.projectsRootDir = info?.projectsRootDir || state.project.projectsRootDir || '';
  if (el.projectDirLabel) {
    el.projectDirLabel.textContent = state.project.dir || 'no project';
    el.projectDirLabel.title = state.project.dir || '';
  }
  if (el.currentProjectDir) {
    el.currentProjectDir.value = state.project.dir || '';
  }
}

async function refreshProjectList() {
  const result = await window.electronAPI.listProjects();
  if (!result?.ok) {
    throw new Error(result?.error || 'project list failed');
  }
  state.project.projectsRootDir = result.projectsRootDir || '';
  state.project.availableProjects = Array.isArray(result.projects) ? result.projects : [];
  return result;
}

function renderProjectPicker() {
  if (!el.projectPickerList) return;
  el.projectPickerList.innerHTML = '';
  if (el.projectPickerRoot) {
    el.projectPickerRoot.textContent = state.project.projectsRootDir || '-';
    el.projectPickerRoot.title = state.project.projectsRootDir || '';
  }

  const projects = state.project.availableProjects || [];
  if (projects.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'project-picker-root';
    empty.textContent = 'projects 配下にプロジェクトがありません。';
    el.projectPickerList.appendChild(empty);
  }

  projects.forEach((project) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `project-picker-item${project.current ? ' current' : ''}`;
    button.innerHTML = `
      <span class="project-picker-main">
        <span class="project-picker-name">${escHtml(project.projectName || '')}</span>
        <span class="project-picker-title">${escHtml(project.title || '')}</span>
        <span class="project-picker-path">${escHtml(project.projectDir || '')}</span>
      </span>
      ${project.current ? '<span class="project-picker-badge">現在</span>' : ''}
    `;
    button.addEventListener('click', async () => {
      const result = await window.electronAPI.openExistingProject({ projectName: project.projectName });
      if (!result?.ok) {
        if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = `プロジェクトを開けませんでした: ${result?.error || 'unknown'}`;
        return;
      }
      closeModal(el.projectPickerModal);
      await loadProjectConfig();
      await loadResDefinitions({ keepSelection: false });
      await loadPlugins();
      await refreshProjectList();
      if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = `✓ プロジェクトを切り替えました: ${result.projectDir}`;
    });
    el.projectPickerList.appendChild(button);
  });

  const addButton = document.createElement('button');
  addButton.type = 'button';
  addButton.className = 'project-picker-item add-new';
  addButton.innerHTML = `
    <span class="project-picker-main">
      <span class="project-picker-name">新規プロジェクトを追加</span>
      <span class="project-picker-title">projects 配下に新しいフォルダを作成します</span>
    </span>
  `;
  addButton.addEventListener('click', () => {
    closeModal(el.projectPickerModal);
    openProjectModal();
  });
  el.projectPickerList.appendChild(addButton);
}

async function openProjectPicker() {
  try {
    await refreshProjectList();
    renderProjectPicker();
    openModal(el.projectPickerModal);
  } catch (err) {
    if (el.settingsSavedMsg) {
      el.settingsSavedMsg.textContent = `プロジェクト一覧取得失敗: ${err?.message || err}`;
    }
  }
}

async function loadProjectConfig() {
  try {
    const projectInfo = await window.electronAPI.getCurrentProject();
    if (projectInfo?.ok) {
      setCurrentProjectInfo(projectInfo);
    }

    const cfg = await window.electronAPI.getProjectConfig();
    if (cfg) {
      const normalized = {
        title: cfg.title || cfg.romName || state.projectConfig.title,
        author: cfg.author || state.projectConfig.author,
        serial: cfg.serial || state.projectConfig.serial,
        region: cfg.region || 'JUE',
      };
      state.projectConfig = { ...state.projectConfig, ...normalized };
      if (el.settingTitle) el.settingTitle.value = state.projectConfig.title;
      if (el.settingAuthor) el.settingAuthor.value = state.projectConfig.author;
      if (el.settingSerial) el.settingSerial.value = state.projectConfig.serial;
      updateProjectNameDisplay();
      collectAndValidateSettings({ showError: true });
    }

    const currentSource = await window.electronAPI.getCurrentSource();
    if (currentSource != null && el.codeEditor) {
      el.codeEditor.value = currentSource;
    }

    const romPath = await window.electronAPI.getRomPath();
    if (romPath) {
      state.lastRomPath = romPath;
      if (el.settingOutputPath) el.settingOutputPath.value = romPath;
    } else {
      state.lastRomPath = null;
      if (el.settingOutputPath) el.settingOutputPath.value = '';
    }
    updateRomOutputActions();
  } catch (_err) {
    // no-op
  }
}

async function saveSettings() {
  const result = collectAndValidateSettings({ showError: true });
  if (!result.valid) {
    if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = '✕ 入力内容を修正してください';
    return;
  }
  state.projectConfig = result.config;
  if (el.settingSerial) el.settingSerial.value = state.projectConfig.serial;
  updateProjectNameDisplay();
  if (el.settingsSavedMsg) {
    el.settingsSavedMsg.textContent = '✓ 設定を保存しました';
    setTimeout(() => { if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = ''; }, 2000);
  }
}

// ============================================================== BUILD ===

/**
 * @param {object} [opts]
 * @param {string} [opts._generatedByPlugin] - このプラグイン ID が既に main.c を書き込み済み
 */
async function runBuild(opts = {}) {
  if (state.building) return;

  // ---- アクティブビルダープラグインが設定されており、かつ呼び出し元がプラグイン生成後でない場合 ----
  const builderPluginId = pluginState.activeBuilderPlugin;
  if (builderPluginId && !opts._generatedByPlugin) {
    // プラグインで main.c を生成してから再度 runBuild を呼ぶ
    appendBuildLog(`[Plugin] ${builderPluginId}: コード生成中...`);
    const genResult = await window.electronAPI.runPluginGenerator(builderPluginId);
    if (!genResult.ok) {
      setLogOpen(true);
      setBuildStatus('error', 'プラグイン生成失敗');
      appendBuildLog(`[ERROR] プラグイン生成失敗: ${genResult.error}`, 'error');
      return;
    }
    appendBuildLog(`[Plugin] ${builderPluginId}: main.c を生成しました`);
    await runBuild({ _generatedByPlugin: builderPluginId });
    return;
  }

  // ---- プラグイン生成済みでない通常ビルド: コードエディタのソースを検証 ----
  const sourceCode = opts._generatedByPlugin ? null : el.codeEditor?.value.trim();
  if (!opts._generatedByPlugin && !sourceCode) {
    switchPage('code');
    if (el.codeStatus) {
      el.codeStatus.textContent = '⚠ ソースコードが空です。サンプル生成ボタンでサンプルを読み込んでください。';
    }
    setLogOpen(true);
    setBuildStatus('error', 'ソースコードが空です');
    return;
  }

  state.building = true;
  el.btnBuild?.classList.add('building');
  if (el.btnBuild) el.btnBuild.disabled = true;
  clearBuildLog();
  setLogOpen(true);
  setBuildStatus('building', 'ビルド中...');
  if (el.buildRomSize) el.buildRomSize.textContent = '';
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

    // プラグイン生成済みの場合はソースを上書きしない (構造整備のみ)
    let genResult;
    if (opts._generatedByPlugin) {
      genResult = await window.electronAPI.generateStructureOnly(state.projectConfig);
    } else {
      genResult = await window.electronAPI.generateProject(sourceCode, state.projectConfig);
    }
    if (!genResult.ok) {
      appendBuildLog(`[ERROR] プロジェクト生成失敗: ${genResult.error}`, 'error');
      setBuildStatus('error', 'プロジェクト生成失敗');
      return;
    }
    appendBuildLog(`[INFO] プロジェクト生成: ${genResult.projectDir}`);

    const buildResult = await window.electronAPI.runBuild();

    if (buildResult.success) {
      state.lastRomPath = buildResult.romPath;
      if (el.settingOutputPath) el.settingOutputPath.value = buildResult.romPath;
      updateRomOutputActions();
      const sizeKb = buildResult.romSize != null ? `${(buildResult.romSize / 1024).toFixed(1)} KB` : '';
      if (el.buildRomSize) el.buildRomSize.textContent = sizeKb ? `ROM: ${sizeKb}` : '';
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
    el.btnBuild?.classList.remove('building');
    if (el.btnBuild) el.btnBuild.disabled = false;
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

// ========================================================= ASSET UTILS ===

function toTypeBadge(type) {
  const cls = `type-${String(type).toLowerCase().replace(/[^a-z0-9]/g, '')}`;
  return `<span class="asset-type-pill ${cls}">${type}</span>`;
}

function escHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getSelectedFile() {
  return state.rescomp.files.find((f) => f.file === state.rescomp.selectedFile) || null;
}

function getFilteredEntries() {
  const file = getSelectedFile();
  if (!file) return [];
  const q = state.rescomp.searchText.trim().toLowerCase();
  if (!q) return file.entries;
  return file.entries.filter((e) => {
    const hay = `${e.name} ${e.type} ${e.sourcePath}`.toLowerCase();
    return hay.includes(q);
  });
}

function getCurrentSelectedEntry() {
  const file = getSelectedFile();
  if (!file || state.rescomp.selectedEntryLine == null) return null;
  return file.entries.find((e) => Number(e.lineNumber) === Number(state.rescomp.selectedEntryLine)) || null;
}

function inferTypeFromExtension(ext) {
  const e = String(ext || '').toLowerCase();
  if (e === '.pal') return 'PALETTE';
  if (e === '.wav') return 'WAV';
  if (e === '.vgm' || e === '.xgm') return 'XGM';
  if (e === '.tsx') return 'TILESET';
  if (e === '.tmx') return 'MAP';
  if (e === '.png' || e === '.bmp') return 'IMAGE';
  return 'BIN';
}

function defaultSubDirForType(type) {
  switch (type) {
    case 'PALETTE': return 'pal';
    case 'SPRITE': return 'sprite';
    case 'IMAGE':
    case 'BITMAP':
    case 'TILESET':
    case 'TILEMAP':
    case 'MAP': return 'gfx';
    case 'XGM':
    case 'XGM2': return 'music';
    case 'WAV': return 'sfx';
    default: return 'assets';
  }
}

function normalizeSymbolName(name) {
  return String(name || '')
    .replace(/\.[^.]+$/, '')
    .replace(/[^A-Za-z0-9_]/g, '_')
    .replace(/^[^A-Za-z_]+/, '')
    .replace(/_+/g, '_')
    .toLowerCase() || 'asset_name';
}

function createDefaultEntry(type, sourcePath, fileName) {
  const base = {
    type,
    name: normalizeSymbolName(fileName),
    sourcePath,
  };

  if (type === 'IMAGE') {
    return { ...base, compression: 'NONE', mapOpt: 'ALL', mapBase: '0' };
  }
  if (type === 'BITMAP') {
    return { ...base, compression: 'NONE' };
  }
  if (type === 'SPRITE') {
    return {
      ...base,
      width: '2',
      height: '2',
      compression: 'NONE',
      time: '0',
      collision: 'NONE',
      optType: 'BALANCED',
      optLevel: 'FAST',
      optDuplicate: 'FALSE',
    };
  }
  if (type === 'XGM') {
    return { ...base, timing: 'AUTO', options: '' };
  }
  if (type === 'XGM2') {
    return { ...base, files: [sourcePath], options: '' };
  }
  if (type === 'WAV') {
    return { ...base, driver: 'DEFAULT', outRate: '', far: 'TRUE' };
  }
  if (type === 'MAP') {
    return { ...base, tileset: 'tileset_main', compression: 'NONE', mapBase: '0', ordering: 'ROW' };
  }
  if (type === 'TILEMAP') {
    return { ...base, tileset: 'tileset_main', compression: 'NONE', mapOpt: 'ALL', mapBase: '0', ordering: 'ROW' };
  }
  if (type === 'TILESET') {
    return { ...base, compression: 'NONE', opt: 'ALL', ordering: 'ROW', export: 'FALSE' };
  }
  return base;
}

function getEntryByLine(lineNumber) {
  const file = getSelectedFile();
  if (!file) return null;
  return file.entries.find((e) => Number(e.lineNumber) === Number(lineNumber)) || null;
}

function renderResFileSelect() {
  if (!el.resFileSelect) return;
  el.resFileSelect.innerHTML = '';

  state.rescomp.files.forEach((f) => {
    const opt = document.createElement('option');
    opt.value = f.file;
    opt.textContent = `${f.file} (${f.entryCount})`;
    el.resFileSelect.appendChild(opt);
  });

  if (!state.rescomp.selectedFile && state.rescomp.files.length > 0) {
    state.rescomp.selectedFile = state.rescomp.files[0].file;
  }

  if (state.rescomp.selectedFile) {
    el.resFileSelect.value = state.rescomp.selectedFile;
  }
}

function renderEntryMeta(entry) {
  if (!entry) {
    if (el.infoLine) el.infoLine.textContent = '-';
    if (el.infoType) el.infoType.textContent = '-';
    if (el.infoName) el.infoName.textContent = '-';
    if (el.infoComment) el.infoComment.textContent = '-';
    if (el.infoSource) el.infoSource.textContent = '-';
    return;
  }

  if (el.infoLine) el.infoLine.textContent = String(entry.lineNumber || '-');
  if (el.infoType) el.infoType.textContent = String(entry.type || '-');
  if (el.infoName) el.infoName.textContent = String(entry.name || '-');
  if (el.infoComment) el.infoComment.textContent = String(entry.comment || '-');
  if (el.infoSource) el.infoSource.textContent = String(entry.sourcePath || '-');
}

function isImageEntry(entry) {
  return !!entry && IMAGE_EXTS.includes(pathExt(entry.sourcePath));
}

function isAudioEntry(entry) {
  return !!entry && pathExt(entry.sourcePath) === '.wav';
}

function pathExt(value) {
  const m = String(value || '').toLowerCase().match(/(\.[a-z0-9]+)$/i);
  return m ? m[1] : '';
}

function toFileUrl(absPath) {
  return `file:///${encodeURI(String(absPath || '').replace(/\\/g, '/'))}`;
}

function buildEntryTooltip(entry) {
  const parts = [];
  if (entry.comment) {
    parts.push(entry.comment);
  }
  if (entry.raw) {
    parts.push(entry.raw);
  }
  return parts.join('\n');
}

function stopAudioPreview() {
  if (state.preview.audio) {
    state.preview.audio.pause();
    state.preview.audio.currentTime = 0;
    state.preview.audio = null;
  }
  state.preview.audioEntryId = '';
  syncAudioPlayer(false);
}

function extractDisplayPalette(imageData, maxSwatches) {
  const seen = new Map();
  const data = imageData.data;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 128) continue;
    const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    seen.set(key, (seen.get(key) || 0) + 1);
  }
  const sorted = [...seen.entries()].sort((a, b) => b[1] - a[1]);
  return sorted.slice(0, maxSwatches).map(([key]) => ({
    r: (key >> 16) & 0xff,
    g: (key >> 8) & 0xff,
    b: key & 0xff,
  }));
}

const IMAGE_PREVIEW_ZOOM_PRESETS = ['25', '50', '100', '200', '300', '400', '800'];

function applyInlineImageZoom() {
  if (!el.inlinePreviewImage) return;
  const zoom = String(state.preview.imageZoom || 'fit');
  const nw = Number(state.preview.imageNaturalWidth || 0);
  const nh = Number(state.preview.imageNaturalHeight || 0);

  if (zoom === 'fit' || !nw || !nh) {
    el.inlinePreviewImage.style.width = '';
    el.inlinePreviewImage.style.height = '';
    el.inlinePreviewImage.style.maxWidth = '100%';
    el.inlinePreviewImage.style.maxHeight = '100%';
    el.inlinePreviewImage.style.objectFit = 'contain';
    return;
  }

  const ratio = Math.max(0.01, Number(zoom) / 100);
  el.inlinePreviewImage.style.maxWidth = 'none';
  el.inlinePreviewImage.style.maxHeight = 'none';
  el.inlinePreviewImage.style.objectFit = 'fill';
  el.inlinePreviewImage.style.width = `${Math.round(nw * ratio)}px`;
  el.inlinePreviewImage.style.height = `${Math.round(nh * ratio)}px`;
}

function stepInlineImageZoom(step) {
  const list = ['fit', ...IMAGE_PREVIEW_ZOOM_PRESETS];
  const current = String(state.preview.imageZoom || 'fit');
  if (current === 'fit') {
    state.preview.imageZoom = step > 0 ? '100' : '50';
    if (el.inlineImageZoom) el.inlineImageZoom.value = state.preview.imageZoom;
    applyInlineImageZoom();
    return;
  }
  let idx = list.indexOf(current);
  if (idx < 0) idx = 0;
  const nextIdx = Math.max(0, Math.min(list.length - 1, idx + step));
  state.preview.imageZoom = list[nextIdx];
  if (el.inlineImageZoom) el.inlineImageZoom.value = state.preview.imageZoom;
  applyInlineImageZoom();
}

function parseWavHeader(dataUrl) {
  try {
    const b64 = dataUrl.split(',')[1];
    if (!b64 || b64.length < 60) return null;
    const dec = atob(b64.slice(0, 64));
    const u8 = new Uint8Array(dec.length);
    for (let i = 0; i < dec.length; i++) u8[i] = dec.charCodeAt(i);
    const view = new DataView(u8.buffer);
    const riff = String.fromCharCode(u8[0], u8[1], u8[2], u8[3]);
    const wave = String.fromCharCode(u8[8], u8[9], u8[10], u8[11]);
    if (riff !== 'RIFF' || wave !== 'WAVE') return null;
    const numChannels = view.getUint16(22, true);
    const sampleRate = view.getUint32(24, true);
    const bitsPerSample = view.getUint16(34, true);
    const dataSize = view.getUint32(40, true);
    const durationSec = sampleRate > 0
      ? dataSize / (sampleRate * numChannels * (bitsPerSample / 8))
      : 0;
    const fileSizeBytes = Math.round(b64.replace(/=/g, '').length * 0.75);
    return { sampleRate, numChannels, bitsPerSample, durationSec, fileSizeBytes };
  } catch {
    return null;
  }
}

function formatDuration(sec) {
  if (!isFinite(sec) || sec < 0) return '-';
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2);
  return `${m}:${s.padStart(5, '0')}`;
}

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function syncInlinePreview(entry) {
  if (!entry) {
    if (el.inlineImagePreview) el.inlineImagePreview.hidden = true;
    if (el.inlineAudioPreview) el.inlineAudioPreview.hidden = true;
    if (el.inlineNoPreview) el.inlineNoPreview.hidden = false;
    return;
  }

  if (isImageEntry(entry)) {
    if (el.inlineAudioPreview) el.inlineAudioPreview.hidden = true;
    if (el.inlineNoPreview) el.inlineNoPreview.hidden = true;
    if (el.inlineImagePreview) el.inlineImagePreview.hidden = false;

    state.preview.imageEntryId = entry.id;
    state.preview.imageNaturalWidth = 0;
    state.preview.imageNaturalHeight = 0;
    if (el.inlinePalette) el.inlinePalette.innerHTML = '';
    if (el.inlinePreviewInfo) el.inlinePreviewInfo.textContent = '';

    const src = entry.sourceAbsolutePath ? toFileUrl(entry.sourceAbsolutePath) : '';
    if (el.inlinePreviewImage) {
      el.inlinePreviewImage.src = src;
      applyInlineImageZoom();
    }

    if (src) {
      const img = new Image();
      img.onload = () => {
        state.preview.imageNaturalWidth = img.naturalWidth;
        state.preview.imageNaturalHeight = img.naturalHeight;
        if (el.inlinePreviewInfo) {
          el.inlinePreviewInfo.textContent = `${img.naturalWidth} × ${img.naturalHeight} px`;
        }
        applyInlineImageZoom();
        const cvs = document.createElement('canvas');
        cvs.width = img.naturalWidth;
        cvs.height = img.naturalHeight;
        const ctx = cvs.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(img, 0, 0);
        const imageData = ctx.getImageData(0, 0, cvs.width, cvs.height);
        const colors = extractDisplayPalette(imageData, 64);
        if (el.inlinePalette) {
          el.inlinePalette.innerHTML = '';
          colors.forEach(({ r, g, b }) => {
            const sw = document.createElement('div');
            sw.className = 'palette-swatch';
            sw.style.background = `rgb(${r},${g},${b})`;
            const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
            sw.title = hex;
            el.inlinePalette.appendChild(sw);
          });
        }
      };
      img.src = src;
      // fetch file size via dataUrl
      if (entry.sourceAbsolutePath) {
        window.electronAPI.readFileAsDataUrl(entry.sourceAbsolutePath).then((res) => {
          if (res?.ok && el.inlinePreviewInfo) {
            const bytes = Math.round(res.dataUrl.replace(/^data:[^,]+,/, '').replace(/=/g, '').length * 0.75);
            const sz = formatFileSize(bytes);
            const cur = el.inlinePreviewInfo.textContent;
            if (cur && sz !== '-') el.inlinePreviewInfo.textContent = `${cur}  |  ${sz}`;
          }
        }).catch(() => {});
      }
    }
    return;
  }

  if (isAudioEntry(entry)) {
    if (el.inlineImagePreview) el.inlineImagePreview.hidden = true;
    if (el.inlineNoPreview) el.inlineNoPreview.hidden = true;
    if (el.inlineAudioPreview) el.inlineAudioPreview.hidden = false;
    if (el.audioPreviewMeta) el.audioPreviewMeta.innerHTML = '<span class="audio-meta-loading">読み込み中...</span>';
    syncAudioPlayer(false);

    if (entry.sourceAbsolutePath) {
      window.electronAPI.readFileAsDataUrl(entry.sourceAbsolutePath).then((res) => {
        if (!res?.ok || !el.audioPreviewMeta) return;
        const meta = parseWavHeader(res.dataUrl);
        if (!meta) {
          el.audioPreviewMeta.innerHTML = `<div class="audio-meta-row"><span>${escHtml(entry.sourcePath || '')}</span></div>`;
          return;
        }
        const chStr = meta.numChannels === 1 ? 'モノラル' : meta.numChannels === 2 ? 'ステレオ' : `${meta.numChannels}ch`;
        el.audioPreviewMeta.innerHTML = `
          <div class="audio-meta-row"><span class="audio-meta-label">ファイル</span><span>${escHtml(entry.sourcePath || '')}</span></div>
          <div class="audio-meta-row"><span class="audio-meta-label">再生時間</span><span>${formatDuration(meta.durationSec)}</span></div>
          <div class="audio-meta-row"><span class="audio-meta-label">サンプルレート</span><span>${meta.sampleRate.toLocaleString()} Hz</span></div>
          <div class="audio-meta-row"><span class="audio-meta-label">形式</span><span>${chStr} / ${meta.bitsPerSample} bit</span></div>
          <div class="audio-meta-row"><span class="audio-meta-label">ファイルサイズ</span><span>${formatFileSize(meta.fileSizeBytes)}</span></div>
        `;
      }).catch(() => {
        if (el.audioPreviewMeta) el.audioPreviewMeta.innerHTML = `<div class="audio-meta-row"><span>${escHtml(entry.sourcePath || '')}</span></div>`;
      });
    }
    return;
  }

  // no preview available
  if (el.inlineImagePreview) el.inlineImagePreview.hidden = true;
  if (el.inlineAudioPreview) el.inlineAudioPreview.hidden = true;
  if (el.inlineNoPreview) el.inlineNoPreview.hidden = false;
}

function setAccordionOpen(section, open) {
  if (section === 'params') {
    state.preview.paramsOpen = open;
    if (el.btnAccordionParams) el.btnAccordionParams.setAttribute('aria-expanded', String(open));
    if (el.accordionParamsBody) el.accordionParamsBody.classList.toggle('is-collapsed', !open);
  } else {
    state.preview.previewOpen = open;
    if (el.btnAccordionPreview) el.btnAccordionPreview.setAttribute('aria-expanded', String(open));
    if (el.accordionPreviewBody) el.accordionPreviewBody.classList.toggle('is-collapsed', !open);
  }
}

function setPreviewPanelOpen(open) {
  state.preview.panelOpen = open;
  if (el.assetsLayout) el.assetsLayout.classList.toggle('preview-collapsed', !open);
  if (el.btnTogglePreviewPanel) {
    el.btnTogglePreviewPanel.setAttribute('aria-pressed', String(open));
    el.btnTogglePreviewPanel.title = open ? 'プレビューパネルを閉じる' : 'プレビューパネルを開く';
    const iconClose = el.btnTogglePreviewPanel.querySelector('.icon-panel-close');
    const iconOpen = el.btnTogglePreviewPanel.querySelector('.icon-panel-open');
    if (iconClose) iconClose.style.display = open ? '' : 'none';
    if (iconOpen) iconOpen.style.display = open ? 'none' : '';
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function syncAudioPlayer(isPlaying) {
  if (el.audioPlayIcon) {
    el.audioPlayIcon.querySelector('use')?.setAttribute('href', isPlaying ? '#icon-stop' : '#icon-play');
  }
  if (el.btnAudioPlay) {
    el.btnAudioPlay.title = isPlaying ? '停止' : '再生';
  }
  if (!isPlaying && el.audioSeek) {
    el.audioSeek.value = 0;
  }
  if (!isPlaying && el.audioTime) {
    el.audioTime.textContent = '0:00';
  }
}

function toggleAudioPreview(entry) {
  if (!isAudioEntry(entry) || !entry.sourceAbsolutePath) {
    return;
  }

  if (state.preview.audioEntryId === entry.id && state.preview.audio) {
    stopAudioPreview();
    return;
  }

  stopAudioPreview();
  const audio = new Audio(toFileUrl(entry.sourceAbsolutePath));

  audio.addEventListener('timeupdate', () => {
    if (!audio.duration || !el.audioSeek || !el.audioTime) return;
    el.audioSeek.value = (audio.currentTime / audio.duration) * 100;
    const m = Math.floor(audio.currentTime / 60);
    const s = Math.floor(audio.currentTime % 60).toString().padStart(2, '0');
    el.audioTime.textContent = `${m}:${s}`;
  });

  audio.addEventListener('ended', () => {
    stopAudioPreview();
  });

  state.preview.audio = audio;
  state.preview.audioEntryId = entry.id;
  audio.play().then(() => {
    syncAudioPlayer(true);
  }).catch(() => {
    stopAudioPreview();
  });
}

function renderAssetTable() {
  if (!el.assetTableBody) return;

  const rows = getFilteredEntries();
  el.assetTableBody.innerHTML = '';

  if (rows.length === 0) {
    const tr = document.createElement('tr');
    tr.className = 'asset-row-empty';
    tr.innerHTML = '<td colspan="6">一致する定義がありません</td>';
    el.assetTableBody.appendChild(tr);
    if (el.assetTableHint) el.assetTableHint.textContent = '定義を追加するか、検索条件を変更してください。';
    renderAssetEditor(null);
    return;
  }

  if (el.assetTableHint) {
    el.assetTableHint.textContent = `${rows.length} 件 / ${state.rescomp.selectedFile}`;
  }

  rows.forEach((entry) => {
    const tr = document.createElement('tr');
    tr.className = 'asset-row';
    tr.title = buildEntryTooltip(entry);
    tr.draggable = true;
    if (Number(state.rescomp.selectedEntryLine) === Number(entry.lineNumber)) {
      tr.classList.add('active');
    }

    const isPlaying = isAudioEntry(entry) && state.preview.audioEntryId === entry.id;

    tr.innerHTML = `
      <td class="asset-drag-cell"><span class="drag-handle">&#8942;&#8942;</span></td>
      <td>${toTypeBadge(escHtml(entry.type))}</td>
      <td>${escHtml(entry.name)}</td>
      <td class="asset-path-cell">${escHtml(entry.sourcePath || '')}</td>
      <td class="asset-comment-cell">${escHtml(entry.comment || '')}</td>
      <td class="asset-actions-cell">
        <button class="icon-btn-sm" data-delete-line="${entry.lineNumber}" title="定義削除">
          <svg class="icon-sm"><use href="#icon-trash"></use></svg>
        </button>
      </td>
    `;

    tr.addEventListener('click', (ev) => {
      if (ev.target.closest('button[data-delete-line]')) return;
      state.rescomp.selectedEntryLine = Number(entry.lineNumber);
      renderAssetTable();
      renderAssetEditor(entry);
    });

    const deleteBtn = tr.querySelector('button[data-delete-line]');
    deleteBtn?.addEventListener('click', async (ev) => {
      ev.stopPropagation();
      await deleteEntry(entry);
    });

    tr.addEventListener('dragstart', (ev) => {
      ev.dataTransfer.effectAllowed = 'move';
      ev.dataTransfer.setData('text/plain', String(entry.lineNumber));
      tr.classList.add('drag-source');
    });
    tr.addEventListener('dragend', () => {
      tr.classList.remove('drag-source');
      el.assetTableBody?.querySelectorAll('.drag-over').forEach((r) => r.classList.remove('drag-over'));
    });
    tr.addEventListener('dragover', (ev) => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      el.assetTableBody?.querySelectorAll('.drag-over').forEach((r) => r.classList.remove('drag-over'));
      tr.classList.add('drag-over');
    });
    tr.addEventListener('dragleave', (ev) => {
      if (!tr.contains(ev.relatedTarget)) tr.classList.remove('drag-over');
    });
    tr.addEventListener('drop', async (ev) => {
      ev.preventDefault();
      tr.classList.remove('drag-over');
      const fromLine = Number(ev.dataTransfer.getData('text/plain'));
      const toLine = Number(entry.lineNumber);
      if (fromLine !== toLine) await reorderEntry(fromLine, toLine);
    });

    el.assetTableBody.appendChild(tr);
  });

  const current = getEntryByLine(state.rescomp.selectedEntryLine) || rows[0];
  state.rescomp.selectedEntryLine = current ? Number(current.lineNumber) : null;
  renderAssetEditor(current);
}

function createFieldInput(field, value) {
  let input;
  if (field.type === 'select') {
    input = document.createElement('select');
    input.className = 'form-input form-input-mono';
    field.options.forEach((opt) => {
      const o = document.createElement('option');
      o.value = opt;
      o.textContent = opt;
      input.appendChild(o);
    });
    input.value = value || field.options[0] || '';
  } else {
    input = document.createElement('input');
    input.type = 'text';
    input.className = field.key === 'sourcePath' ? 'form-input form-input-mono' : 'form-input';
    input.value = value || '';
  }
  input.dataset.field = field.key;
  return input;
}

let _autoSaveTimer = null;
function scheduleAutoSave() {
  if (_autoSaveTimer) clearTimeout(_autoSaveTimer);
  _autoSaveTimer = setTimeout(() => {
    _autoSaveTimer = null;
    saveCurrentEntry(true);
  }, 400);
}

function renderAssetEditor(entry) {
  if (!el.assetEditForm || !el.assetEditorPanel) return;

  if (!entry) {
    if (el.assetEditorActions) el.assetEditorActions.hidden = true;
    if (el.assetNoSelectionHint) el.assetNoSelectionHint.hidden = false;
    el.assetEditForm.innerHTML = '';
    syncInlinePreview(null);
    return;
  }

  if (el.assetEditorActions) el.assetEditorActions.hidden = false;
  if (el.assetNoSelectionHint) el.assetNoSelectionHint.hidden = true;

  // restore accordion state
  setAccordionOpen('params', state.preview.paramsOpen);
  setAccordionOpen('preview', state.preview.previewOpen);

  const fields = FORM_FIELDS_BY_TYPE[entry.type] || [
    { key: 'name', label: 'シンボル名', type: 'text' },
    { key: 'sourcePath', label: '入力ファイル', type: 'text' },
  ];

  el.assetEditForm.innerHTML = '';
  const grid = document.createElement('div');
  grid.className = 'asset-edit-grid';

  fields.forEach((field) => {
    const label = document.createElement('label');
    label.textContent = field.label;
    const input = createFieldInput(field, entry[field.key]);
    grid.appendChild(label);
    grid.appendChild(input);
  });

  const warning = document.createElement('div');
  warning.className = 'asset-warning';
  warning.textContent = entry.type === 'XGM2'
    ? 'XGM2 の複数ファイル対応は options で追記可能です。'
    : '';

  const commentLabel = document.createElement('label');
  commentLabel.textContent = 'コメント';
  const commentInput = document.createElement('textarea');
  commentInput.className = 'form-input form-input-mono';
  commentInput.rows = 4;
  commentInput.value = entry.comment || '';
  commentInput.dataset.field = 'comment';

  grid.appendChild(commentLabel);
  grid.appendChild(commentInput);

  el.assetEditForm.appendChild(grid);
  if (warning.textContent) {
    el.assetEditForm.appendChild(warning);
  }

  // auto-save on edit
  el.assetEditForm.querySelectorAll('[data-field]').forEach((input) => {
    input.addEventListener('input', scheduleAutoSave);
    input.addEventListener('change', scheduleAutoSave);
  });

  // update preview tab
  syncInlinePreview(entry);
}

function collectEditedEntry(entry) {
  const next = { ...entry };
  if (!el.assetEditForm) return next;

  el.assetEditForm.querySelectorAll('[data-field]').forEach((input) => {
    const key = input.dataset.field;
    next[key] = input.value;
  });

  next.type = String(entry.type || '').toUpperCase();
  if (next.type === 'XGM2') {
    next.files = [next.sourcePath || ''];
  }

  return next;
}

async function saveCurrentEntry(silent = false) {
  const entry = getEntryByLine(state.rescomp.selectedEntryLine);
  if (!entry) return;

  const edited = collectEditedEntry(entry);
  const payload = {
    file: state.rescomp.selectedFile,
    lineNumber: entry.lineNumber,
    entry: edited,
  };

  const result = await window.electronAPI.updateResEntry(payload);
  if (!result?.ok) {
    if (el.assetTableHint) {
      el.assetTableHint.textContent = `保存失敗: ${result?.error || 'unknown'}`;
    }
    return;
  }

  if (silent) {
    // update local entry in memory without re-rendering (avoids cursor loss during typing)
    const file = getSelectedFile();
    if (file) {
      const idx = file.entries.findIndex((e) => e.lineNumber === entry.lineNumber);
      if (idx >= 0) file.entries[idx] = { ...file.entries[idx], ...edited };
    }
    if (el.assetTableHint) el.assetTableHint.textContent = '自動保存しました';
    return;
  }

  await loadResDefinitions({ keepSelection: true });
  if (el.assetTableHint) {
    el.assetTableHint.textContent = '定義を保存しました';
  }
}

async function deleteEntry(entry) {
  const ok = window.confirm(`定義を削除しますか？\n${entry.type} ${entry.name}`);
  if (!ok) return;

  const result = await window.electronAPI.deleteResEntry({
    file: state.rescomp.selectedFile,
    lineNumber: entry.lineNumber,
  });

  if (!result?.ok) {
    if (el.assetTableHint) {
      el.assetTableHint.textContent = `削除失敗: ${result?.error || 'unknown'}`;
    }
    return;
  }

  state.rescomp.selectedEntryLine = null;
  await loadResDefinitions({ keepSelection: true });
}

async function reorderEntry(fromLine, toLine) {
  const file = getSelectedFile();
  if (!file) return;
  const entries = file.entries;
  const fromIdx = entries.findIndex((e) => Number(e.lineNumber) === fromLine);
  const toIdx = entries.findIndex((e) => Number(e.lineNumber) === toLine);
  if (fromIdx < 0 || toIdx < 0) return;

  const orderedLineNumbers = entries.map((e) => Number(e.lineNumber));
  const [removed] = orderedLineNumbers.splice(fromIdx, 1);
  orderedLineNumbers.splice(toIdx, 0, removed);

  const result = await window.electronAPI.reorderResEntries({
    file: state.rescomp.selectedFile,
    orderedLineNumbers,
  });
  if (!result?.ok) {
    if (el.assetTableHint) el.assetTableHint.textContent = `\u4e26\u3073\u66ff\u3048\u5931\u6557: ${result?.error || 'unknown'}`;
    return;
  }
  state.rescomp.selectedEntryLine = null;
  await loadResDefinitions({ keepSelection: false });
}

async function loadResDefinitions({ keepSelection = false } = {}) {
  const prevFile = state.rescomp.selectedFile;
  const prevLine = state.rescomp.selectedEntryLine;

  const result = await window.electronAPI.listResDefinitions();
  if (!result?.ok) {
    if (el.assetTableHint) {
      el.assetTableHint.textContent = `読み込み失敗: ${result?.error || 'unknown'}`;
    }
    return;
  }

  state.rescomp.resRoot = result.resRoot || '';
  state.rescomp.files = result.files || [];

  if (keepSelection && prevFile && state.rescomp.files.some((f) => f.file === prevFile)) {
    state.rescomp.selectedFile = prevFile;
  } else if (!state.rescomp.selectedFile || !state.rescomp.files.some((f) => f.file === state.rescomp.selectedFile)) {
    state.rescomp.selectedFile = state.rescomp.files[0]?.file || '';
  }

  if (keepSelection && prevLine) {
    state.rescomp.selectedEntryLine = prevLine;
  } else {
    state.rescomp.selectedEntryLine = null;
  }

  renderResFileSelect();
  renderAssetTable();
}

function populateAssetTypeOptions(selectedType) {
  if (!el.assetTypeInput) return;
  el.assetTypeInput.innerHTML = '';
  TYPE_OPTIONS.forEach((type) => {
    const opt = document.createElement('option');
    opt.value = type;
    opt.textContent = type;
    el.assetTypeInput.appendChild(opt);
  });
  el.assetTypeInput.value = selectedType || 'IMAGE';
}

function populateAssetResFileOptions() {
  if (!el.assetResFileInput) return;
  el.assetResFileInput.innerHTML = '';
  state.rescomp.files.forEach((f) => {
    const opt = document.createElement('option');
    opt.value = f.file;
    opt.textContent = f.file;
    el.assetResFileInput.appendChild(opt);
  });
  el.assetResFileInput.value = state.rescomp.selectedFile || state.rescomp.files[0]?.file || 'resources.res';
}

function syncAssetModalForType() {
  const type = el.assetTypeInput?.value || 'IMAGE';
  const fileName = el.assetTargetFileNameInput?.value || '';
  if (el.assetTargetSubdirInput && !el.assetTargetSubdirInput.dataset.userEdited) {
    el.assetTargetSubdirInput.value = defaultSubDirForType(type);
  }
  if (el.assetSymbolNameInput && fileName && !el.assetSymbolNameInput.dataset.userEdited) {
    el.assetSymbolNameInput.value = normalizeSymbolName(fileName);
  }
}

function openResFileModal() {
  if (el.resFileNameInput) el.resFileNameInput.value = '';
  openModal(el.resFileModal);
}

async function submitResFileModal() {
  const fileName = el.resFileNameInput?.value.trim() || '';
  if (!fileName) {
    if (el.assetTableHint) el.assetTableHint.textContent = 'ファイル名を入力してください。';
    return;
  }
  const result = await window.electronAPI.createResFile(fileName);
  if (!result?.ok) {
    if (el.assetTableHint) el.assetTableHint.textContent = `作成失敗: ${result?.error || 'unknown'}`;
    return;
  }
  state.rescomp.selectedFile = fileName;
  await loadResDefinitions({ keepSelection: true });
  closeModal(el.resFileModal);
  if (el.assetTableHint) el.assetTableHint.textContent = `作成しました: ${fileName}`;
}

function snapChannelTo3Bit(value) {
  const level = Math.max(0, Math.min(7, Math.round((Number(value) / 255) * 7)));
  return Math.round((level / 7) * 255);
}

function snapColorToMegaDrive(color) {
  return {
    r: snapChannelTo3Bit(color.r),
    g: snapChannelTo3Bit(color.g),
    b: snapChannelTo3Bit(color.b),
  };
}

function colorDistanceSq(a, b) {
  const dr = a.r - b.r;
  const dg = a.g - b.g;
  const db = a.b - b.b;
  return dr * dr + dg * dg + db * db;
}

function countUniqueColors(imageData) {
  const seen = new Set();
  const data = imageData.data;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] < 128) continue;
    seen.add((data[i] << 16) | (data[i + 1] << 8) | data[i + 2]);
  }
  return seen.size;
}

function hexToRgb(hex) {
  const h = String(hex || '#000000').replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16) || 0,
    g: parseInt(h.slice(2, 4), 16) || 0,
    b: parseInt(h.slice(4, 6), 16) || 0,
  };
}

function buildPalette(imageData, maxColors, transparencyMode, customTransparent, reserveCustomColor) {
  const data = imageData.data;
  let transparentColor = { r: 0, g: 0, b: 0 };
  let transparentFound = false;
  const pixels = [];

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const a = data[i + 3];
    const isSourceTransparent = a < 128;
    const isCustomTransparent = transparencyMode === 'custom'
      && !reserveCustomColor
      && colorDistanceSq({ r, g, b }, customTransparent) <= (16 * 16 * 3);
    const transparent = (transparencyMode === 'source' && isSourceTransparent) || isCustomTransparent;

    if (transparent) {
      if (!transparentFound) {
        transparentColor = snapColorToMegaDrive(transparencyMode === 'custom' ? customTransparent : { r, g, b });
        transparentFound = true;
      }
      continue;
    }

    pixels.push({ r, g, b });
  }

  if (pixels.length === 0) {
    return {
      palette: Array.from({ length: maxColors }, () => ({ r: 0, g: 0, b: 0 })),
      transparentColor,
      hasTransparent: transparencyMode !== 'none' && !reserveCustomColor,
    };
  }

  const maxSamples = 40000;
  const stride = Math.max(1, Math.floor(pixels.length / maxSamples));
  const sampled = [];
  for (let i = 0; i < pixels.length; i += stride) {
    sampled.push(pixels[i]);
  }

  let boxes = [sampled];
  while (boxes.length < maxColors) {
    boxes.sort((a, b) => {
      const rangeA = Math.max(
        Math.max(...a.map((c) => c.r)) - Math.min(...a.map((c) => c.r)),
        Math.max(...a.map((c) => c.g)) - Math.min(...a.map((c) => c.g)),
        Math.max(...a.map((c) => c.b)) - Math.min(...a.map((c) => c.b))
      );
      const rangeB = Math.max(
        Math.max(...b.map((c) => c.r)) - Math.min(...b.map((c) => c.r)),
        Math.max(...b.map((c) => c.g)) - Math.min(...b.map((c) => c.g)),
        Math.max(...b.map((c) => c.b)) - Math.min(...b.map((c) => c.b))
      );
      return rangeB - rangeA;
    });

    const box = boxes.shift();
    if (!box || box.length <= 1) {
      if (box) boxes.push(box);
      break;
    }

    const rangeR = Math.max(...box.map((c) => c.r)) - Math.min(...box.map((c) => c.r));
    const rangeG = Math.max(...box.map((c) => c.g)) - Math.min(...box.map((c) => c.g));
    const rangeB = Math.max(...box.map((c) => c.b)) - Math.min(...box.map((c) => c.b));
    const channel = rangeR >= rangeG && rangeR >= rangeB ? 'r' : rangeG >= rangeB ? 'g' : 'b';
    box.sort((left, right) => left[channel] - right[channel]);
    const mid = Math.floor(box.length / 2);
    boxes.push(box.slice(0, mid), box.slice(mid));
  }

  const deduped = [];
  const seen = new Set();
  boxes.forEach((box) => {
    if (!box.length) return;
    const avg = snapColorToMegaDrive({
      r: box.reduce((sum, c) => sum + c.r, 0) / box.length,
      g: box.reduce((sum, c) => sum + c.g, 0) / box.length,
      b: box.reduce((sum, c) => sum + c.b, 0) / box.length,
    });
    const key = `${avg.r},${avg.g},${avg.b}`;
    if (!seen.has(key)) {
      seen.add(key);
      deduped.push(avg);
    }
  });

  while (deduped.length < maxColors) {
    deduped.push({ ...deduped[deduped.length - 1] || { r: 0, g: 0, b: 0 } });
  }

  return {
    palette: deduped.slice(0, maxColors),
    transparentColor,
    hasTransparent: transparencyMode !== 'none' && !reserveCustomColor,
  };
}

function nearestColorIndex(color, palette) {
  let best = 0;
  let bestScore = Number.POSITIVE_INFINITY;
  for (let i = 0; i < palette.length; i += 1) {
    const score = colorDistanceSq(color, palette[i]);
    if (score < bestScore) {
      bestScore = score;
      best = i;
    }
  }
  return best;
}

function getPatternValue(patternName, x, y) {
  const p = DITHER_PATTERNS[patternName] || DITHER_PATTERNS.diagonal4;
  const h = p.length;
  const w = p[0].length;
  return p[y % h][x % w];
}

function quantizeToIndexed16(imageData, options) {
  const out = new ImageData(imageData.width, imageData.height);
  const src = imageData.data;
  const dst = out.data;
  const indices = new Uint8Array(imageData.width * imageData.height);

  const transparencyMode = options.transparencyMode || 'none';
  const ditherEnabled = options.ditherEnabled;
  const ditherWeight = Number(options.ditherWeight || 0);
  const ditherPattern = options.ditherPattern || 'diagonal4';
  const customTransparent = hexToRgb(options.transparencyColor || '#ff00ff');
  const reserveCustomColor = Boolean(options.reserveCustomColor);

  const effectivePaletteSize = (transparencyMode === 'none' && !reserveCustomColor) ? 16 : 15;
  const { palette, transparentColor, hasTransparent } = buildPalette(
    imageData,
    effectivePaletteSize,
    transparencyMode,
    customTransparent,
    reserveCustomColor
  );

  const fullPalette = reserveCustomColor
    ? [{ ...snapColorToMegaDrive(customTransparent) }, ...palette]
    : (hasTransparent ? [{ ...transparentColor }, ...palette] : palette);

  for (let y = 0; y < imageData.height; y += 1) {
    for (let x = 0; x < imageData.width; x += 1) {
      const i = (y * imageData.width + x) * 4;
      const r = src[i];
      const g = src[i + 1];
      const b = src[i + 2];
      const a = src[i + 3];

      const isSourceTransparent = a < 128;
      const isCustomTransparent = transparencyMode === 'custom'
        && !reserveCustomColor
        && colorDistanceSq({ r, g, b }, customTransparent) <= (16 * 16 * 3);
      const transparent = (transparencyMode === 'source' && isSourceTransparent) || isCustomTransparent;

      if (transparent && hasTransparent) {
        dst[i] = transparentColor.r;
        dst[i + 1] = transparentColor.g;
        dst[i + 2] = transparentColor.b;
        dst[i + 3] = 0;
        indices[y * imageData.width + x] = 0; // 透明色はパレットindex 0
        continue;
      }

      let rr = r;
      let gg = g;
      let bb = b;

      if (ditherEnabled) {
        const p = getPatternValue(ditherPattern, x, y);
        const shift = (p - 0.5) * ditherWeight * 96;
        rr = Math.max(0, Math.min(255, rr + shift));
        gg = Math.max(0, Math.min(255, gg + shift));
        bb = Math.max(0, Math.min(255, bb + shift));
      }

      const idx = nearestColorIndex({ r: rr, g: gg, b: bb }, fullPalette);
      const c = fullPalette[idx];
      dst[i] = c.r;
      dst[i + 1] = c.g;
      dst[i + 2] = c.b;
      dst[i + 3] = 255;
      indices[y * imageData.width + x] = idx;
    }
  }

  return { imageData: out, palette: fullPalette, indices, transparentPaletteIndex: hasTransparent ? 0 : -1 };
}

function drawImageDataToCanvas(canvas, imageData) {
  const ctx = canvas.getContext('2d');
  canvas.width = imageData.width;
  canvas.height = imageData.height;
  ctx.putImageData(imageData, 0, 0);
}

function readCanvasAsPngDataUrl(canvas) {
  return canvas.toDataURL('image/png');
}

// ── インデックス PNG エンコーダ ─────────────────────────────────────────
// canvas.toDataURL() は RGBA PNG しか生成できず RESCOMP がエラーになるため、
// RESCOMP が正しく読める indexed PNG (color type 3) を自前で生成する。

const PNG_CRC32_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    t[n] = c >>> 0;
  }
  return t;
})();

function pngCrc32(buf, start, end) {
  let crc = 0xFFFFFFFF;
  for (let i = start; i < end; i++) {
    crc = (PNG_CRC32_TABLE[(crc ^ buf[i]) & 0xFF] ^ (crc >>> 8)) >>> 0;
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function pngWriteU32BE(buf, off, v) {
  buf[off] = (v >>> 24) & 0xFF;
  buf[off + 1] = (v >>> 16) & 0xFF;
  buf[off + 2] = (v >>> 8) & 0xFF;
  buf[off + 3] = v & 0xFF;
}

function pngMakeChunk(typeStr, data) {
  const typeBytes = [typeStr.charCodeAt(0), typeStr.charCodeAt(1), typeStr.charCodeAt(2), typeStr.charCodeAt(3)];
  const chunk = new Uint8Array(4 + 4 + data.length + 4);
  pngWriteU32BE(chunk, 0, data.length);
  chunk[4] = typeBytes[0]; chunk[5] = typeBytes[1]; chunk[6] = typeBytes[2]; chunk[7] = typeBytes[3];
  chunk.set(data, 8);
  const crc = pngCrc32(chunk, 4, 8 + data.length);
  pngWriteU32BE(chunk, 8 + data.length, crc);
  return chunk;
}

async function pngZlibDeflate(data) {
  const cs = new CompressionStream('deflate');
  const writer = cs.writable.getWriter();
  writer.write(data);
  writer.close();
  const chunks = [];
  const reader = cs.readable.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((s, c) => s + c.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
}

/**
 * インデックス PNG を生成して data URL で返す。
 * @param {number} width
 * @param {number} height
 * @param {Uint8Array} indices - 長さ width*height のパレットインデックス配列
 * @param {Array<{r,g,b}>} palette - パレット配列（最大256色）
 * @param {number} transparentIndex - 透明扱いにするパレットインデックス（-1=なし）
 * @returns {Promise<string>} data URL
 */
async function encodeIndexedPng(width, height, indices, palette, transparentIndex) {
  const PNG_SIG = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR
  const ihdrData = new Uint8Array(13);
  pngWriteU32BE(ihdrData, 0, width);
  pngWriteU32BE(ihdrData, 4, height);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 3; // color type: indexed
  // bytes 10,11,12 = 0 (compression, filter, interlace)
  const ihdr = pngMakeChunk('IHDR', ihdrData);

  // PLTE
  const plteData = new Uint8Array(palette.length * 3);
  for (let i = 0; i < palette.length; i++) {
    plteData[i * 3] = palette[i].r;
    plteData[i * 3 + 1] = palette[i].g;
    plteData[i * 3 + 2] = palette[i].b;
  }
  const plte = pngMakeChunk('PLTE', plteData);

  // tRNS: 指定インデックスのみ alpha=0 (他は 255)
  let trns = null;
  if (transparentIndex >= 0 && transparentIndex < palette.length) {
    const trnsData = new Uint8Array(transparentIndex + 1).fill(255);
    trnsData[transparentIndex] = 0;
    trns = pngMakeChunk('tRNS', trnsData);
  }

  // IDAT: filter byte(0=None) + index values per scanline
  const rawData = new Uint8Array((width + 1) * height);
  for (let y = 0; y < height; y++) {
    rawData[y * (width + 1)] = 0; // filter None
    for (let x = 0; x < width; x++) {
      rawData[y * (width + 1) + 1 + x] = indices[y * width + x];
    }
  }
  const compressed = await pngZlibDeflate(rawData);
  const idat = pngMakeChunk('IDAT', compressed);
  const iend = pngMakeChunk('IEND', new Uint8Array(0));

  const parts = trns ? [PNG_SIG, ihdr, plte, trns, idat, iend] : [PNG_SIG, ihdr, plte, idat, iend];
  const total = parts.reduce((s, p) => s + p.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) { result.set(p, offset); offset += p.length; }

  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(/** @type {string} */(reader.result));
    reader.readAsDataURL(new Blob([result], { type: 'image/png' }));
  });
}

/**
 * RGBA ImageData から palette を抽出し indexed PNG data URL を返す。
 * alpha<128 のピクセルはパレット index 0 (透明) に割り当てる。
 */
async function imageDataToIndexedPng(imageData) {
  const data = imageData.data;
  const w = imageData.width;
  const h = imageData.height;
  const indices = new Uint8Array(w * h);
  const palette = [];
  const palMap = new Map();
  let hasTransparent = false;
  const transparentColor = { r: 0, g: 0, b: 0 };

  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3];
    if (a < 128) { hasTransparent = true; }
  }

  // index 0 = transparent placeholder (placed first if transparent pixels exist)
  if (hasTransparent) {
    palette.push({ ...transparentColor });
    palMap.set('__transparent__', 0);
  }

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]; const g = data[i + 1]; const b = data[i + 2]; const a = data[i + 3];
    const pixIdx = i >> 2;
    if (a < 128) {
      indices[pixIdx] = 0; // transparent
    } else {
      const key = `${r},${g},${b}`;
      if (!palMap.has(key)) {
        if (palette.length < 256) { palMap.set(key, palette.length); palette.push({ r, g, b }); }
        else {
          // フォールバック: 最近傍
          let best = 0; let bestD = Infinity;
          for (let pi = 0; pi < palette.length; pi++) {
            const d = colorDistanceSq({ r, g, b }, palette[pi]);
            if (d < bestD) { bestD = d; best = pi; }
          }
          palMap.set(key, best);
        }
      }
      indices[pixIdx] = palMap.get(key);
    }
  }

  return encodeIndexedPng(w, h, indices, palette, hasTransparent ? 0 : -1);
}
// ── インデックス PNG エンコーダ ここまで ────────────────────────────────

function closeQuantizeModal() {
  quantizeState.active = false;
  quantizeState.onApply = null;
  if (el.quantizeModal) {
    el.quantizeModal.classList.remove('open');
    el.quantizeModal.setAttribute('aria-hidden', 'true');
  }
}

function syncQuantizeColorUI() {
  const color = (el.quantizeTransparencyColor?.value || '#ff00ff').toLowerCase();
  if (el.quantizeTransparencyColorValue) {
    el.quantizeTransparencyColorValue.textContent = color;
  }
  if (el.quantizeTransparencyColorSwatch) {
    el.quantizeTransparencyColorSwatch.style.background = color;
  }

  const isCustom = (el.quantizeTransparencyMode?.value || 'none') === 'custom';
  if (el.quantizeColorPickerRow) {
    el.quantizeColorPickerRow.style.display = isCustom ? 'flex' : 'none';
  }
  if (el.quantizeSharedColorRow) {
    el.quantizeSharedColorRow.classList.toggle('quantize-shared-disabled', !isCustom);
  }
  if (el.quantizeUseSharedCustomColor) {
    el.quantizeUseSharedCustomColor.disabled = !isCustom;
    if (!isCustom) {
      el.quantizeUseSharedCustomColor.checked = false;
    }
  }
}

function syncQuantizeDitheringUI() {
  const enabled = Boolean(el.quantizeDitheringEnabled?.checked);
  if (el.quantizeDitheringWeight) {
    el.quantizeDitheringWeight.disabled = !enabled;
    el.quantizeDitheringWeight.classList.toggle('quantize-control-disabled', !enabled);
  }
  if (el.quantizePattern) {
    el.quantizePattern.disabled = !enabled;
    el.quantizePattern.classList.toggle('quantize-control-disabled', !enabled);
  }
}

function rerenderQuantizePreview() {
  if (!quantizeState.originalData || !el.quantizeAfterCanvas || !el.quantizeStats) return;

  syncQuantizeColorUI();
  syncQuantizeDitheringUI();

  const options = {
    transparencyMode: el.quantizeTransparencyMode?.value || 'none',
    transparencyColor: el.quantizeTransparencyColor?.value || '#ff00ff',
    reserveCustomColor: Boolean(el.quantizeUseSharedCustomColor?.checked),
    ditherEnabled: Boolean(el.quantizeDitheringEnabled?.checked),
    ditherWeight: Number(el.quantizeDitheringWeight?.value || 0),
    ditherPattern: el.quantizePattern?.value || 'diagonal4',
  };

  if (el.quantizeWeightLabel) {
    el.quantizeWeightLabel.textContent = options.ditherWeight.toFixed(2);
  }

  const converted = quantizeToIndexed16(quantizeState.originalData, options);
  drawImageDataToCanvas(el.quantizeAfterCanvas, converted.imageData);
  // プレビュー表示用 (RGBA PNG) – 実際の保存は indexed PNG を使う
  quantizeState.convertedDataUrl = readCanvasAsPngDataUrl(el.quantizeAfterCanvas);
  // indexed PNG 生成用に最終変換結果を保存
  quantizeState._lastConvertResult = {
    indices: converted.indices,
    palette: converted.palette,
    transparentPaletteIndex: converted.transparentPaletteIndex,
    width: quantizeState.originalData.width,
    height: quantizeState.originalData.height,
  };

  const srcColors = countUniqueColors(quantizeState.originalData);
  const dstColors = countUniqueColors(converted.imageData);
  el.quantizeStats.textContent = `colors: ${srcColors} -> ${dstColors} / palette: ${converted.palette.length}`;
}

async function openQuantizeModal(sourceDataUrl) {
  const img = new Image();
  img.src = sourceDataUrl;
  await img.decode();

  const tmpCanvas = document.createElement('canvas');
  tmpCanvas.width = img.width;
  tmpCanvas.height = img.height;
  const tmpCtx = tmpCanvas.getContext('2d', { willReadFrequently: true });
  tmpCtx.drawImage(img, 0, 0);
  const imageData = tmpCtx.getImageData(0, 0, img.width, img.height);

  quantizeState.originalCanvas = tmpCanvas;
  quantizeState.originalCtx = tmpCtx;
  quantizeState.originalData = imageData;

  if (el.quantizeBeforeCanvas) {
    drawImageDataToCanvas(el.quantizeBeforeCanvas, imageData);
  }

  if (el.quantizeModal) {
    el.quantizeModal.classList.add('open');
    el.quantizeModal.setAttribute('aria-hidden', 'false');
  }

  if (el.quantizeDitheringEnabled) {
    el.quantizeDitheringEnabled.checked = true;
  }

  rerenderQuantizePreview();

  return new Promise((resolve) => {
    quantizeState.onApply = async (ok) => {
      if (ok) {
        let finalDataUrl = quantizeState.convertedDataUrl || sourceDataUrl;
        // indexed PNG (パレットPNG) を生成して RESCOMP に渡す
        const cr = quantizeState._lastConvertResult;
        if (cr && cr.indices && cr.palette) {
          try {
            finalDataUrl = await encodeIndexedPng(
              cr.width, cr.height, cr.indices, cr.palette, cr.transparentPaletteIndex
            );
          } catch (e) {
            console.warn('indexed PNG エンコード失敗、RGBA PNG でフォールバック:', e);
          }
        }
        resolve({ ok: true, dataUrl: finalDataUrl });
      } else {
        resolve({ ok: false, dataUrl: '' });
      }
      closeQuantizeModal();
    };
  });
}

const resizeState = {
  onApply: null,
  originalImg: null,
  sourceDataUrl: '',
  canSkip: false,
  cropRect: null,
  renderMap: null,
  drag: null,
};

function snapTo8(v) {
  return Math.max(8, Math.round(v / 8) * 8);
}

function isMultipleOf8(v) {
  return Number.isFinite(v) && v >= 8 && v % 8 === 0;
}

function closeResizeModal() {
  resizeState.onApply = null;
  resizeState.originalImg = null;
  resizeState.sourceDataUrl = '';
  resizeState.cropRect = null;
  resizeState.renderMap = null;
  resizeState.drag = null;
  closeModal(el.resizeModal);
}

function getResizeTargetSize() {
  const w = Number(el.resizeWidth?.value || 0);
  const h = Number(el.resizeHeight?.value || 0);
  return { w, h };
}

function updateResizeValidation() {
  const { w, h } = getResizeTargetSize();
  let message = '';
  if (!isMultipleOf8(w) || !isMultipleOf8(h)) {
    message = '幅/高さは 8 の倍数で指定してください。';
  }
  if (el.resizeValidationMessage) {
    el.resizeValidationMessage.textContent = message;
  }
  if (el.btnResizeApply) {
    el.btnResizeApply.disabled = message.length > 0;
  }
  return message.length === 0;
}

function ensureCropRect() {
  const img = resizeState.originalImg;
  if (!img) return;
  const { w, h } = getResizeTargetSize();
  if (!isMultipleOf8(w) || !isMultipleOf8(h)) {
    resizeState.cropRect = null;
    return;
  }

  const aspect = w / h;
  const maxW = img.naturalWidth;
  const maxH = img.naturalHeight;
  let rectW = maxW;
  let rectH = Math.round(rectW / aspect);
  if (rectH > maxH) {
    rectH = maxH;
    rectW = Math.round(rectH * aspect);
  }
  rectW = Math.max(1, Math.min(maxW, rectW));
  rectH = Math.max(1, Math.min(maxH, rectH));

  if (!resizeState.cropRect) {
    resizeState.cropRect = {
      x: Math.floor((maxW - rectW) / 2),
      y: Math.floor((maxH - rectH) / 2),
      w: rectW,
      h: rectH,
    };
  } else {
    // アスペクト比が変わった（target w/h を変更した）か、サイズが画像を超える場合だけリセット
    const cur = resizeState.cropRect;
    const curAspect = cur.w / cur.h;
    const aspectChanged = Math.abs(curAspect - aspect) > 0.005;
    const oversized = cur.w > maxW || cur.h > maxH;
    if (aspectChanged || oversized) {
      cur.w = rectW;
      cur.h = rectH;
    }
    cur.x = Math.max(0, Math.min(maxW - cur.w, cur.x));
    cur.y = Math.max(0, Math.min(maxH - cur.h, cur.y));
  }
}

function clampCropRectIntoImage() {
  const img = resizeState.originalImg;
  const rect = resizeState.cropRect;
  if (!img || !rect) return;
  rect.x = Math.max(0, Math.min(img.naturalWidth - rect.w, rect.x));
  rect.y = Math.max(0, Math.min(img.naturalHeight - rect.h, rect.y));
}

function renderResizePreview() {
  const img = resizeState.originalImg;
  if (!img || !el.resizePreviewCanvas) return;

  const cvs = el.resizePreviewCanvas;
  const mode = el.resizeMode?.value || 'resize';
  const pad = 12;
  const maxW = Math.max(240, Math.min(640, (el.resizePreviewCanvas.parentElement?.clientWidth || 640) - pad * 2));
  const maxH = 420;
  const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight, 1);
  const drawW = Math.max(1, Math.round(img.naturalWidth * scale));
  const drawH = Math.max(1, Math.round(img.naturalHeight * scale));
  const canvasW = drawW + pad * 2;
  const canvasH = drawH + pad * 2;
  const offsetX = Math.floor((canvasW - drawW) / 2);
  const offsetY = Math.floor((canvasH - drawH) / 2);

  cvs.width = canvasW;
  cvs.height = canvasH;
  const ctx = cvs.getContext('2d');
  ctx.clearRect(0, 0, canvasW, canvasH);
  ctx.fillStyle = '#0a0e16';
  ctx.fillRect(0, 0, canvasW, canvasH);
  ctx.drawImage(img, offsetX, offsetY, drawW, drawH);

  resizeState.renderMap = { scale, offsetX, offsetY, drawW, drawH };

  if (mode === 'clip') {
    ensureCropRect();
    const rect = resizeState.cropRect;
    if (rect) {
      const rx = offsetX + Math.round(rect.x * scale);
      const ry = offsetY + Math.round(rect.y * scale);
      const rw = Math.max(1, Math.round(rect.w * scale));
      const rh = Math.max(1, Math.round(rect.h * scale));

      ctx.fillStyle = 'rgba(0,0,0,0.45)';
      ctx.fillRect(offsetX, offsetY, drawW, drawH);
      ctx.clearRect(rx, ry, rw, rh);
      ctx.drawImage(img, rect.x, rect.y, rect.w, rect.h, rx, ry, rw, rh);

      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 2;
      ctx.strokeRect(rx + 0.5, ry + 0.5, rw - 1, rh - 1);

      const hs = 5;
      const handles = [
        { x: rx, y: ry },
        { x: rx + rw, y: ry },
        { x: rx + rw, y: ry + rh },
        { x: rx, y: ry + rh },
      ];
      ctx.fillStyle = '#58a6ff';
      handles.forEach((p) => {
        ctx.fillRect(Math.round(p.x - hs), Math.round(p.y - hs), hs * 2, hs * 2);
      });
    }
  }
}

function getCropCanvasRect() {
  const img = resizeState.originalImg;
  const map = resizeState.renderMap;
  const rect = resizeState.cropRect;
  if (!img || !map || !rect) return null;
  return {
    x: map.offsetX + Math.round(rect.x * map.scale),
    y: map.offsetY + Math.round(rect.y * map.scale),
    w: Math.max(1, Math.round(rect.w * map.scale)),
    h: Math.max(1, Math.round(rect.h * map.scale)),
  };
}

function detectCropDragMode(canvasX, canvasY) {
  const rect = getCropCanvasRect();
  if (!rect) return 'none';
  const hs = 14;
  const points = [
    { mode: 'resize-nw', x: rect.x, y: rect.y },
    { mode: 'resize-ne', x: rect.x + rect.w, y: rect.y },
    { mode: 'resize-se', x: rect.x + rect.w, y: rect.y + rect.h },
    { mode: 'resize-sw', x: rect.x, y: rect.y + rect.h },
  ];
  const hit = points.find((p) => Math.abs(canvasX - p.x) <= hs && Math.abs(canvasY - p.y) <= hs);
  if (hit) return hit.mode;
  if (canvasX >= rect.x && canvasX <= rect.x + rect.w && canvasY >= rect.y && canvasY <= rect.y + rect.h) {
    return 'move';
  }
  return 'none';
}

function resizeCropRectWithAspect(mode, pointerImgX, pointerImgY) {
  const img = resizeState.originalImg;
  const startRect = resizeState.drag?.startRect;
  if (!img || !startRect) return;

  const { w: targetW, h: targetH } = getResizeTargetSize();
  const aspect = Math.max(0.01, targetW / targetH);
  const minW = Math.min(img.naturalWidth, 8);
  const minH = Math.min(img.naturalHeight, 8);

  let ax;
  let ay;
  let fromLeft;
  let fromTop;
  if (mode === 'resize-nw') {
    ax = startRect.x + startRect.w;
    ay = startRect.y + startRect.h;
    fromLeft = true;
    fromTop = true;
  } else if (mode === 'resize-ne') {
    ax = startRect.x;
    ay = startRect.y + startRect.h;
    fromLeft = false;
    fromTop = true;
  } else if (mode === 'resize-se') {
    ax = startRect.x;
    ay = startRect.y;
    fromLeft = false;
    fromTop = false;
  } else {
    ax = startRect.x + startRect.w;
    ay = startRect.y;
    fromLeft = true;
    fromTop = false;
  }

  let rawW = fromLeft ? (ax - pointerImgX) : (pointerImgX - ax);
  let rawH = fromTop ? (ay - pointerImgY) : (pointerImgY - ay);
  rawW = Math.max(minW, rawW);
  rawH = Math.max(minH, rawH);

  let nextW = rawW;
  let nextH = rawH;
  if ((rawW / rawH) > aspect) {
    nextH = rawW / aspect;
  } else {
    nextW = rawH * aspect;
  }

  let x = fromLeft ? (ax - nextW) : ax;
  let y = fromTop ? (ay - nextH) : ay;
  let w = nextW;
  let h = nextH;

  if (x < 0) {
    w += x;
    x = 0;
    h = w / aspect;
    if (fromTop) y = ay - h;
  }
  if (y < 0) {
    h += y;
    y = 0;
    w = h * aspect;
    if (fromLeft) x = ax - w;
  }
  if (x + w > img.naturalWidth) {
    w = img.naturalWidth - x;
    h = w / aspect;
    if (fromTop) y = ay - h;
  }
  if (y + h > img.naturalHeight) {
    h = img.naturalHeight - y;
    w = h * aspect;
    if (fromLeft) x = ax - w;
  }

  resizeState.cropRect = {
    x: Math.max(0, Math.round(x)),
    y: Math.max(0, Math.round(y)),
    w: Math.max(minW, Math.round(w)),
    h: Math.max(minH, Math.round(h)),
  };
  clampCropRectIntoImage();
}

function moveCropRectFromCanvasPoint(clientX, clientY) {
  const img = resizeState.originalImg;
  const map = resizeState.renderMap;
  const rect = resizeState.cropRect;
  if (!img || !map || !rect || !el.resizePreviewCanvas) return;

  const b = el.resizePreviewCanvas.getBoundingClientRect();
  const scaleX = b.width ? el.resizePreviewCanvas.width / b.width : 1;
  const scaleY = b.height ? el.resizePreviewCanvas.height / b.height : 1;
  const canvasX = (clientX - b.left) * scaleX;
  const canvasY = (clientY - b.top) * scaleY;
  const pointerImgX = (canvasX - map.offsetX) / map.scale;
  const pointerImgY = (canvasY - map.offsetY) / map.scale;

  if (resizeState.drag?.mode === 'move') {
    const sx = resizeState.drag.startPointerX;
    const sy = resizeState.drag.startPointerY;
    const sr = resizeState.drag.startRect;
    const dx = pointerImgX - sx;
    const dy = pointerImgY - sy;
    rect.x = Math.round(sr.x + dx);
    rect.y = Math.round(sr.y + dy);
    clampCropRectIntoImage();
  } else if (String(resizeState.drag?.mode || '').startsWith('resize-')) {
    resizeCropRectWithAspect(resizeState.drag.mode, pointerImgX, pointerImgY);
  }
  clampCropRectIntoImage();
  renderResizePreview();
}

function beginResizeCropDrag(event) {
  if ((el.resizeMode?.value || 'resize') !== 'clip') return;
  if (!resizeState.cropRect) return;
  if (!el.resizePreviewCanvas || !resizeState.renderMap) return;
  const b = el.resizePreviewCanvas.getBoundingClientRect();
  const scaleX = b.width ? el.resizePreviewCanvas.width / b.width : 1;
  const scaleY = b.height ? el.resizePreviewCanvas.height / b.height : 1;
  const canvasX = (event.clientX - b.left) * scaleX;
  const canvasY = (event.clientY - b.top) * scaleY;
  const mode = detectCropDragMode(canvasX, canvasY);
  if (mode === 'none') return;
  const pointerImgX = (canvasX - resizeState.renderMap.offsetX) / resizeState.renderMap.scale;
  const pointerImgY = (canvasY - resizeState.renderMap.offsetY) / resizeState.renderMap.scale;
  resizeState.drag = {
    active: true,
    mode,
    startPointerX: pointerImgX,
    startPointerY: pointerImgY,
    startRect: { ...resizeState.cropRect },
  };
  // ポインターキャプチャでキャンバス外ドラッグも確実に追跡する
  event.target.setPointerCapture(event.pointerId);
  moveCropRectFromCanvasPoint(event.clientX, event.clientY);
  event.preventDefault();
}

function updateResizeCropDrag(event) {
  if (!resizeState.drag?.active) return;
  moveCropRectFromCanvasPoint(event.clientX, event.clientY);
}

function endResizeCropDrag() {
  if (!resizeState.drag?.active) return;
  resizeState.drag = null;
  if (el.resizePreviewCanvas) el.resizePreviewCanvas.style.cursor = 'crosshair';
}

function applyResizeTransform() {
  const img = resizeState.originalImg;
  if (!img) return '';
  const { w, h } = getResizeTargetSize();
  if (!isMultipleOf8(w) || !isMultipleOf8(h)) return '';

  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  const ctx = out.getContext('2d');
  const mode = el.resizeMode?.value || 'resize';

  if (mode === 'clip') {
    ensureCropRect();
    const rect = resizeState.cropRect || { x: 0, y: 0, w: img.naturalWidth, h: img.naturalHeight };
    ctx.drawImage(img, rect.x, rect.y, rect.w, rect.h, 0, 0, w, h);
  } else {
    ctx.drawImage(img, 0, 0, w, h);
  }
  return out.toDataURL('image/png');
}

async function openResizeModal(dataUrl, imgWidth, imgHeight) {
  const img = new Image();
  img.src = dataUrl;
  await img.decode();

  resizeState.originalImg = img;
  resizeState.sourceDataUrl = dataUrl;
  resizeState.canSkip = (imgWidth % 8 === 0) && (imgHeight % 8 === 0);
  resizeState.cropRect = null;
  resizeState.drag = null;

  if (el.resizeOriginalSize) {
    el.resizeOriginalSize.textContent = `${imgWidth} × ${imgHeight} px`;
  }

  if (el.resizeWidth) el.resizeWidth.value = snapTo8(imgWidth);
  if (el.resizeHeight) el.resizeHeight.value = snapTo8(imgHeight);
  if (el.resizeMode) el.resizeMode.value = 'resize';
  if (el.btnResizeSkip) {
    el.btnResizeSkip.disabled = !resizeState.canSkip;
    el.btnResizeSkip.title = resizeState.canSkip ? '' : '元画像サイズが 8 の倍数のときのみスキップできます';
  }

  updateResizeValidation();
  openModal(el.resizeModal);
  renderResizePreview();

  return new Promise((resolve) => {
    resizeState.onApply = (mode) => {
      if (mode === 'apply') {
        const resultDataUrl = applyResizeTransform();
        closeResizeModal();
        resolve({ ok: true, dataUrl: resultDataUrl || dataUrl, skipped: false });
      } else if (mode === 'skip' && resizeState.canSkip) {
        closeResizeModal();
        resolve({ ok: true, dataUrl, skipped: true });
      } else {
        closeResizeModal();
        resolve({ ok: false, dataUrl: '', skipped: false });
      }
    };
  });
}

async function maybeConvertImageToIndexed16(sourcePath) {
  const read = await window.electronAPI.readFileAsDataUrl(sourcePath);
  if (!read?.ok || !read.dataUrl) {
    return { canceled: true, convertedDataUrl: '', originalDataUrl: '', warning: read?.error || '' };
  }

  const img = new Image();
  img.src = read.dataUrl;
  await img.decode();

  let warning = '';
  let workingDataUrl = read.dataUrl;
  const resizeResult = await openResizeModal(read.dataUrl, img.naturalWidth, img.naturalHeight);
  if (!resizeResult.ok) {
    return { canceled: true, convertedDataUrl: '', originalDataUrl: read.dataUrl, warning: 'リサイズ/クリッピングをキャンセルしました' };
  }
  if (resizeResult.dataUrl && resizeResult.dataUrl !== read.dataUrl) {
    workingDataUrl = resizeResult.dataUrl;
    warning = 'リサイズ/クリッピングを適用しました';
  }

  const workImg = new Image();
  workImg.src = workingDataUrl;
  await workImg.decode();

  const canvas = document.createElement('canvas');
  canvas.width = workImg.width;
  canvas.height = workImg.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(workImg, 0, 0);
  const imageData = ctx.getImageData(0, 0, workImg.width, workImg.height);
  const unique = countUniqueColors(imageData);

  if (unique <= 16) {
    // canvas を経由した場合 (リサイズ/クリッピング後) は RGBA PNG になっているため
    // indexed PNG に変換して RESCOMP に渡す
    let savedDataUrl = '';
    if (workingDataUrl !== read.dataUrl) {
      try {
        savedDataUrl = await imageDataToIndexedPng(imageData);
      } catch (e) {
        console.warn('indexed PNG 変換失敗、RGBA PNG にフォールバック:', e);
        savedDataUrl = workingDataUrl;
      }
    }
    return {
      canceled: false,
      convertedDataUrl: savedDataUrl,
      originalDataUrl: read.dataUrl,
      warning,
    };
  }

  const quantized = await openQuantizeModal(workingDataUrl);
  if (!quantized.ok) {
    return {
      canceled: true,
      convertedDataUrl: '',
      originalDataUrl: read.dataUrl,
      warning: '減色変換をキャンセルしました',
    };
  }

  return {
    canceled: false,
    convertedDataUrl: quantized.dataUrl,
    originalDataUrl: read.dataUrl,
    warning: `${warning ? `${warning} / ` : ''}減色変換を適用: ${unique} colors -> 16 colors`,
  };
}

async function openAssetModal() {
  if (!state.rescomp.selectedFile) {
    await loadResDefinitions({ keepSelection: true });
  }
  if (!state.rescomp.selectedFile) {
    if (el.assetTableHint) el.assetTableHint.textContent = '.res ファイルを先に作成してください。';
    return;
  }

  const picked = await window.electronAPI.pickAssetSource();
  if (!picked || picked.canceled) return;

  state.rescomp.pendingAssetPick = picked;
  const initialType = inferTypeFromExtension(picked.ext);
  if (el.assetSourcePathInput) el.assetSourcePathInput.value = picked.sourcePath;
  if (el.assetTargetFileNameInput) el.assetTargetFileNameInput.value = picked.fileName;
  if (el.assetTargetSubdirInput) {
    el.assetTargetSubdirInput.value = defaultSubDirForType(initialType);
    delete el.assetTargetSubdirInput.dataset.userEdited;
  }
  if (el.assetSymbolNameInput) {
    el.assetSymbolNameInput.value = normalizeSymbolName(picked.fileName);
    delete el.assetSymbolNameInput.dataset.userEdited;
  }
  if (el.assetCommentInput) {
    el.assetCommentInput.value = '';
  }
  populateAssetTypeOptions(initialType);
  populateAssetResFileOptions();
  syncAssetModalForType();
  openModal(el.assetModal);
}

async function submitAssetModal() {
  const picked = state.rescomp.pendingAssetPick;
  if (!picked) {
    closeModal(el.assetModal);
    return;
  }

  const normalizedType = String(el.assetTypeInput?.value || '').trim().toUpperCase();
  if (!TYPE_OPTIONS.includes(normalizedType)) {
    if (el.assetTableHint) el.assetTableHint.textContent = `未対応タイプ: ${normalizedType}`;
    return;
  }

  const targetSubdir = el.assetTargetSubdirInput?.value.trim() || defaultSubDirForType(normalizedType);
  const targetFileName = el.assetTargetFileNameInput?.value.trim() || picked.fileName;
  if (!targetFileName) return;

  let convertedDataUrl = '';
  let warning = '';
  const isImageAsset = IMAGE_EXTS.includes((picked.ext || '').toLowerCase());
  if (isImageAsset && ['PALETTE', 'IMAGE', 'BITMAP', 'SPRITE', 'MAP', 'TILEMAP', 'TILESET'].includes(normalizedType)) {
    const converted = await maybeConvertImageToIndexed16(picked.sourcePath);
    if (converted.canceled) {
      closeModal(el.assetModal);
      if (el.assetTableHint) {
        el.assetTableHint.textContent = converted.warning || '画像登録をキャンセルしました';
      }
      return;
    }
    convertedDataUrl = converted.convertedDataUrl || '';
    warning = converted.warning || '';
  }

  const copyResult = await window.electronAPI.writeAssetFile({
    sourcePath: picked.sourcePath,
    targetSubdir,
    targetFileName,
    dataUrl: convertedDataUrl || '',
  });

  if (!copyResult?.ok) {
    if (el.assetTableHint) el.assetTableHint.textContent = `コピー失敗: ${copyResult?.error || 'unknown'}`;
    return;
  }

  const defaultEntry = createDefaultEntry(normalizedType, copyResult.relativePath, targetFileName);
  const symbol = el.assetSymbolNameInput?.value.trim() || defaultEntry.name;
  defaultEntry.name = normalizeSymbolName(symbol);
  defaultEntry.comment = el.assetCommentInput?.value.trim() || '';

  const addResult = await window.electronAPI.addResEntry({
    file: el.assetResFileInput?.value || state.rescomp.selectedFile,
    entry: defaultEntry,
  });

  if (!addResult?.ok) {
    if (el.assetTableHint) el.assetTableHint.textContent = `定義追加失敗: ${addResult?.error || 'unknown'}`;
    return;
  }

  state.rescomp.selectedFile = el.assetResFileInput?.value || state.rescomp.selectedFile;
  await loadResDefinitions({ keepSelection: true });

  const file = getSelectedFile();
  const matched = file?.entries.find((e) => e.name === defaultEntry.name && e.type === normalizedType && e.sourcePath === defaultEntry.sourcePath);
  if (matched) {
    state.rescomp.selectedEntryLine = matched.lineNumber;
    renderAssetTable();
  }

  if (el.assetTableHint) {
    el.assetTableHint.textContent = warning || `追加しました: ${defaultEntry.type} ${defaultEntry.name}`;
  }
  state.rescomp.pendingAssetPick = null;
  closeModal(el.assetModal);
}

function openProjectModal() {
  if (el.projectSystemNameInput) el.projectSystemNameInput.value = 'my_md_game';
  if (el.projectTitleInput) el.projectTitleInput.value = state.projectConfig.title || 'MY GAME';
  if (el.projectAuthorInput) el.projectAuthorInput.value = state.projectConfig.author || 'AUTHOR';
  if (el.projectSerialInput) el.projectSerialInput.value = state.projectConfig.serial || 'GM 00000000-00';
  openModal(el.projectModal);
}

async function submitProjectModal() {
  const projectName = el.projectSystemNameInput?.value.trim();
  if (!projectName) {
    if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = 'プロジェクトフォルダ名を入力してください。';
    return;
  }
  const payload = {
    projectName,
    config: {
      title: el.projectTitleInput?.value.trim() || 'MY GAME',
      author: el.projectAuthorInput?.value.trim() || 'AUTHOR',
      serial: (el.projectSerialInput?.value.trim() || 'GM 00000000-00').toUpperCase(),
      region: 'JUE',
    },
  };
  const result = await window.electronAPI.createNewProject(payload);
  if (!result?.ok) {
    if (!result?.canceled && el.settingsSavedMsg) {
      el.settingsSavedMsg.textContent = `プロジェクト作成失敗: ${result?.error || 'unknown'}`;
    }
    return;
  }
  closeModal(el.projectModal);
  await loadProjectConfig();
  await loadResDefinitions({ keepSelection: false });
  await refreshProjectList();
  if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = `✓ プロジェクトを作成しました: ${result.projectDir}`;
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
    if (el.aboutTitle) el.aboutTitle.textContent = info.appName || 'MD Game Editor';
    if (el.aboutDescription) el.aboutDescription.textContent = info.appDescription || 'Embedded emulator information';
    if (el.aboutAppVersion) el.aboutAppVersion.textContent = info.appVersion || 'unknown';
    if (el.aboutWasmBuildVersion) el.aboutWasmBuildVersion.textContent = wasm.buildVersion || 'unknown';
    if (el.aboutWasmPackageVersion) el.aboutWasmPackageVersion.textContent = wasm.packageVersion || 'unknown';
    if (el.aboutElectronVersion) el.aboutElectronVersion.textContent = info.electronVersion || 'unknown';
    if (el.aboutChromeVersion) el.aboutChromeVersion.textContent = info.chromeVersion || 'unknown';
    if (el.aboutNodeVersion) el.aboutNodeVersion.textContent = info.nodeVersion || 'unknown';
    if (el.aboutPlatform) el.aboutPlatform.textContent = info.platform || 'unknown';
    if (el.aboutArch) el.aboutArch.textContent = info.arch || 'unknown';
    if (el.aboutAppPath) el.aboutAppPath.textContent = info.appPath || 'unknown';
  } catch (_err) {
    if (el.aboutWasmBuildVersion) {
      el.aboutWasmBuildVersion.textContent = 'failed to load';
    }
  }
}

// ====================================================== EVENT BINDING ===

function bindEvents() {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      switchPage(btn.dataset.page);
      if (btn.dataset.page === 'plugins') loadPlugins();
    });
  });

  el.btnReloadPlugins?.addEventListener('click', () => loadPlugins());

  el.btnBuild?.addEventListener('click', runBuild);
  el.btnTestPlay?.addEventListener('click', openTestPlay);
  el.btnNewProject?.addEventListener('click', openProjectPicker);
  el.btnOpenProject?.addEventListener('click', openProjectPicker);
  $('btnOpenSetup')?.addEventListener('click', () => {
    window.electronAPI.openSetupWindow();
  });

  el.btnGenSample?.addEventListener('click', () => {
    loadSampleCode();
    switchPage('code');
  });
  el.btnSaveCode?.addEventListener('click', async () => {
    const code = el.codeEditor.value;
    try {
      await window.electronAPI.generateProject(code, state.projectConfig);
      el.codeStatus.textContent = '✓ コードを保存しました';
      setTimeout(() => { el.codeStatus.textContent = ''; }, 2000);
    } catch (err) {
      el.codeStatus.textContent = `保存エラー: ${err.message}`;
    }
  });
  el.btnCopyCode?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(el.codeEditor.value);
      el.codeStatus.textContent = '✓ クリップボードにコピーしました';
      setTimeout(() => { el.codeStatus.textContent = ''; }, 2000);
    } catch (_err) {
      el.codeStatus.textContent = 'コピーに失敗しました';
    }
  });

  el.btnSaveSettings?.addEventListener('click', saveSettings);
  el.settingTitle?.addEventListener('input', () => {
    state.projectConfig.title = el.settingTitle.value;
    updateProjectNameDisplay();
    collectAndValidateSettings({ showError: true });
  });
  el.settingAuthor?.addEventListener('input', () => collectAndValidateSettings({ showError: true }));
  el.settingSerial?.addEventListener('input', () => {
    el.settingSerial.value = el.settingSerial.value.toUpperCase();
    collectAndValidateSettings({ showError: true });
  });

  el.btnOpenOutputFolder?.addEventListener('click', async () => {
    if (!state.lastRomPath) {
      if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = 'ROM 出力先がまだありません。先にビルドしてください。';
      return;
    }
    const result = await window.electronAPI.openPathInExplorer(state.lastRomPath, { parentOnly: true });
    if (!result?.ok && el.settingsSavedMsg) {
      el.settingsSavedMsg.textContent = `フォルダを開けませんでした: ${result?.error || 'unknown'}`;
    }
  });

  el.btnDownloadRom?.addEventListener('click', async () => {
    if (!state.lastRomPath) return;
    const result = await window.electronAPI.saveRomAs(state.lastRomPath);
    if (result?.ok) {
      if (el.settingsSavedMsg) {
        el.settingsSavedMsg.textContent = `✓ 保存しました: ${result.path}`;
        setTimeout(() => { if (el.settingsSavedMsg) el.settingsSavedMsg.textContent = ''; }, 2500);
      }
    } else if (!result?.canceled && el.settingsSavedMsg) {
      el.settingsSavedMsg.textContent = `保存に失敗: ${result?.error || 'unknown'}`;
    }
  });

  el.btnOpenProjectDir?.addEventListener('click', async () => {
    if (!state.project.dir) {
      return;
    }
    const result = await window.electronAPI.openPathInExplorer(state.project.dir);
    if (!result?.ok && el.settingsSavedMsg) {
      el.settingsSavedMsg.textContent = `フォルダを開けませんでした: ${result?.error || 'unknown'}`;
    }
  });
  el.btnSettingsProjectPicker?.addEventListener('click', openProjectPicker);

  el.btnOpenResDir?.addEventListener('click', async () => {
    const r = await window.electronAPI.openResDirectory();
    if (!r?.ok && el.assetTableHint) {
      el.assetTableHint.textContent = `res ディレクトリを開けません: ${r?.error || 'unknown'}`;
    }
  });

  el.btnCreateResFile?.addEventListener('click', openResFileModal);
  el.btnAddAsset?.addEventListener('click', openAssetModal);

  el.btnResFileModalClose?.addEventListener('click', () => closeModal(el.resFileModal));
  el.btnResFileCancel?.addEventListener('click', () => closeModal(el.resFileModal));
  el.btnResFileCreate?.addEventListener('click', submitResFileModal);

  el.btnAssetModalClose?.addEventListener('click', () => closeModal(el.assetModal));
  el.btnAssetModalCancel?.addEventListener('click', () => closeModal(el.assetModal));
  el.btnAssetModalCreate?.addEventListener('click', submitAssetModal);

  el.btnAccordionParams?.addEventListener('click', () => {
    setAccordionOpen('params', !state.preview.paramsOpen);
  });

  el.btnAccordionPreview?.addEventListener('click', () => {
    setAccordionOpen('preview', !state.preview.previewOpen);
  });

  el.btnTogglePreviewPanel?.addEventListener('click', () => {
    setPreviewPanelOpen(!state.preview.panelOpen);
  });

  el.btnAudioPlay?.addEventListener('click', () => {
    const entry = getCurrentSelectedEntry();
    if (entry && isAudioEntry(entry)) {
      if (state.preview.audio && state.preview.audioEntryId === entry.id) {
        stopAudioPreview();
      } else {
        toggleAudioPreview(entry);
      }
    }
  });

  el.audioSeek?.addEventListener('input', () => {
    if (state.preview.audio && state.preview.audio.duration) {
      state.preview.audio.currentTime = (parseFloat(el.audioSeek.value) / 100) * state.preview.audio.duration;
    }
  });

  el.inlineImageZoom?.addEventListener('change', () => {
    state.preview.imageZoom = el.inlineImageZoom.value || 'fit';
    applyInlineImageZoom();
  });
  el.inlineImageFrame?.addEventListener('wheel', (event) => {
    event.preventDefault();
    const step = event.deltaY < 0 ? 1 : -1;
    stepInlineImageZoom(step);
  }, { passive: false });

  el.assetTypeInput?.addEventListener('change', syncAssetModalForType);
  el.assetTargetSubdirInput?.addEventListener('input', () => {
    el.assetTargetSubdirInput.dataset.userEdited = '1';
  });
  el.assetTargetFileNameInput?.addEventListener('input', () => {
    if (el.assetSymbolNameInput) {
      delete el.assetSymbolNameInput.dataset.userEdited;
    }
    syncAssetModalForType();
  });
  el.assetSymbolNameInput?.addEventListener('input', () => {
    el.assetSymbolNameInput.dataset.userEdited = '1';
  });

  el.btnProjectModalClose?.addEventListener('click', () => closeModal(el.projectModal));
  el.btnProjectModalCancel?.addEventListener('click', () => closeModal(el.projectModal));
  el.btnProjectModalCreate?.addEventListener('click', submitProjectModal);
  el.btnProjectPickerClose?.addEventListener('click', () => closeModal(el.projectPickerModal));
  el.btnProjectPickerCancel?.addEventListener('click', () => closeModal(el.projectPickerModal));

  document.querySelectorAll('[data-modal-close]').forEach((node) => {
    node.addEventListener('click', () => {
      const modalId = node.getAttribute('data-modal-close');
      closeModal($(modalId));
    });
  });

  el.resFileSelect?.addEventListener('change', () => {
    state.rescomp.selectedFile = el.resFileSelect.value;
    state.rescomp.selectedEntryLine = null;
    renderAssetTable();
  });

  el.assetSearchInput?.addEventListener('input', () => {
    state.rescomp.searchText = el.assetSearchInput.value || '';
    renderAssetTable();
  });

  el.btnDeleteAssetEntry?.addEventListener('click', async () => {
    const entry = getEntryByLine(state.rescomp.selectedEntryLine);
    if (entry) await deleteEntry(entry);
  });

  el.resizeMode?.addEventListener('change', () => {
    const mode = el.resizeMode.value;
    if (el.resizePreviewCanvas) {
      el.resizePreviewCanvas.style.cursor = mode === 'clip' ? 'crosshair' : 'default';
    }
    ensureCropRect();
    renderResizePreview();
  });
  [el.resizeWidth, el.resizeHeight].forEach((inp) => {
    inp?.addEventListener('input', () => {
      updateResizeValidation();
      ensureCropRect();
      renderResizePreview();
    });
  });
  el.resizePreviewCanvas?.addEventListener('pointerdown', beginResizeCropDrag);
  el.resizePreviewCanvas?.addEventListener('pointermove', (e) => {
    // ドラッグ中はカーソルを window の pointermove ハンドラに任せる
    if (resizeState.drag?.active) return;
    if ((el.resizeMode?.value || 'resize') !== 'clip' || !resizeState.renderMap || !resizeState.cropRect) return;
    const b = el.resizePreviewCanvas.getBoundingClientRect();
    const scaleX = b.width ? el.resizePreviewCanvas.width / b.width : 1;
    const scaleY = b.height ? el.resizePreviewCanvas.height / b.height : 1;
    const canvasX = (e.clientX - b.left) * scaleX;
    const canvasY = (e.clientY - b.top) * scaleY;
    const mode = detectCropDragMode(canvasX, canvasY);
    const cursorMap = {
      'resize-nw': 'nwse-resize',
      'resize-ne': 'nesw-resize',
      'resize-se': 'nwse-resize',
      'resize-sw': 'nesw-resize',
      'move': 'move',
      'none': 'crosshair',
    };
    el.resizePreviewCanvas.style.cursor = cursorMap[mode] || 'crosshair';
  });
  window.addEventListener('pointermove', updateResizeCropDrag);
  window.addEventListener('pointerup', endResizeCropDrag);
  window.addEventListener('pointercancel', endResizeCropDrag);
  el.btnResizeApply?.addEventListener('click', () => {
    if (resizeState.onApply) resizeState.onApply('apply');
    else closeResizeModal();
  });
  el.btnResizeSkip?.addEventListener('click', () => {
    if (resizeState.onApply) resizeState.onApply('skip');
  });
  el.btnResizeCancel?.addEventListener('click', () => {
    if (resizeState.onApply) resizeState.onApply('cancel');
    else closeResizeModal();
  });
  el.btnResizeModalClose?.addEventListener('click', () => {
    if (resizeState.onApply) resizeState.onApply('cancel');
    else closeResizeModal();
  });

  el.btnQuantizeClose?.addEventListener('click', () => {
    if (quantizeState.onApply) quantizeState.onApply(false);
    else closeQuantizeModal();
  });
  el.btnQuantizeCancel?.addEventListener('click', () => {
    if (quantizeState.onApply) quantizeState.onApply(false);
    else closeQuantizeModal();
  });
  el.quantizeBackdrop?.addEventListener('click', () => {
    if (quantizeState.onApply) quantizeState.onApply(false);
    else closeQuantizeModal();
  });
  el.btnQuantizeApply?.addEventListener('click', () => {
    if (quantizeState.onApply) quantizeState.onApply(true);
    else closeQuantizeModal();
  });

  [
    el.quantizeTransparencyMode,
    el.quantizeTransparencyColor,
    el.quantizeUseSharedCustomColor,
    el.quantizeDitheringEnabled,
    el.quantizeDitheringWeight,
    el.quantizePattern,
  ].forEach((control) => {
    control?.addEventListener('input', rerenderQuantizePreview);
    control?.addEventListener('change', rerenderQuantizePreview);
  });

  if (el.btnAboutClose) el.btnAboutClose.addEventListener('click', closeAboutDialog);
  if (el.aboutBackdrop) el.aboutBackdrop.addEventListener('click', closeAboutDialog);

  el.buildLogHeader?.addEventListener('click', () => setLogOpen(!state.logOpen));
  el.btnCopyLog?.addEventListener('click', async (e) => {
    e.stopPropagation();
    await copyBuildLog();
  });
  el.btnClearLog?.addEventListener('click', (e) => { e.stopPropagation(); clearBuildLog(); });
  el.btnToggleLog?.addEventListener('click', (e) => { e.stopPropagation(); setLogOpen(!state.logOpen); });

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
      if (!state.logOpen) return;
      event.preventDefault();
      dragStartY = event.clientY;
      dragStartHeight = state.logOpenHeight;
      el.buildLogResizer.classList.add('dragging');
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });
  }

  window.electronAPI.onBuildLog((payload) => {
    appendBuildLog(payload.text || '', payload.level);
    setLogOpen(true);
  });

  window.electronAPI.onBuildEnd((payload) => {
    if (payload.success) {
      state.lastRomPath = payload.romPath;
      if (payload.romPath && el.settingOutputPath) el.settingOutputPath.value = payload.romPath;
      updateRomOutputActions();
      const sizeKb = payload.romSize != null ? `${(payload.romSize / 1024).toFixed(1)} KB` : '';
      if (el.buildRomSize) el.buildRomSize.textContent = sizeKb ? `ROM: ${sizeKb}` : '';
      setBuildStatus('success', '✓ ビルド成功');
    } else {
      setBuildStatus('error', '✕ ビルド失敗');
    }
  });

  window.electronAPI.onMenuOpenSetup?.(() => {
    switchPage('settings');
    window.electronAPI.openSetupWindow();
  });

  window.electronAPI.onMenuOpenAbout?.(() => {
    openAboutDialog();
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (el.aboutModal?.classList.contains('open')) {
        e.preventDefault();
        closeAboutDialog();
        return;
      }
      if (el.quantizeModal?.classList.contains('open')) {
        e.preventDefault();
        if (quantizeState.onApply) quantizeState.onApply(false);
        return;
      }
      if (el.assetModal?.classList.contains('open')) {
        e.preventDefault();
        closeModal(el.assetModal);
        return;
      }
      if (el.projectPickerModal?.classList.contains('open')) {
        e.preventDefault();
        closeModal(el.projectPickerModal);
        return;
      }
      if (el.resFileModal?.classList.contains('open')) {
        e.preventDefault();
        closeModal(el.resFileModal);
        return;
      }
      if (el.projectModal?.classList.contains('open')) {
        e.preventDefault();
        closeModal(el.projectModal);
        return;
      }
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
  switchPage('assets'); // nav-btn の active 状態を確定
  setPreviewPanelOpen(true);
  setAccordionOpen('params', true);
  setAccordionOpen('preview', true);
  await loadProjectConfig();
  await refreshProjectList();
  await loadResDefinitions({ keepSelection: false });
  await loadPlugins();

  if (!el.codeEditor?.value) {
    loadSampleCode();
  }
}

bootstrap();
