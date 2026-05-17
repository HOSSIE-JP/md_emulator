import {
  clearPluginRuntime,
  createPluginRuntime,
  getRuntimeCapabilities,
  getRuntimeCapability,
  listRuntimeCapabilities,
  registerRuntimeCapability,
  waitForRuntimeCapability,
} from './plugin-runtime.mjs';

const api = window.pceAPI;
const runtime = createPluginRuntime();
const state = {
  plugins: [],
  currentPage: '',
  project: null,
  setupCatalog: null,
  setupVersions: {},
  setupVersionErrors: {},
};

const $ = (id) => document.getElementById(id);
const el = {
  pluginTabs: $('pluginTabs'),
  editorArea: $('editorArea'),
  projectChip: $('projectChip'),
  btnSetup: $('btnSetup'),
  btnBuild: $('btnBuild'),
  btnTestPlay: $('btnTestPlay'),
  btnRefreshSetup: $('btnRefreshSetup'),
  setupStatus: $('setupStatus'),
  downloadKind: $('downloadKind'),
  downloadVersion: $('downloadVersion'),
  btnRefreshVersions: $('btnRefreshVersions'),
  btnDownloadTool: $('btnDownloadTool'),
  downloadInfo: $('downloadInfo'),
  setupProgress: $('setupProgress'),
  setupProgressBar: $('setupProgressBar'),
  setupProgressLabel: $('setupProgressLabel'),
  setupProgressMeta: $('setupProgressMeta'),
  projectList: $('projectList'),
  newProjectName: $('newProjectName'),
  btnCreateSample: $('btnCreateSample'),
  btnOpenProjectFolder: $('btnOpenProjectFolder'),
  btnOpenPlugins: $('btnOpenPlugins'),
  pluginList: $('pluginList'),
  logList: $('logList'),
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

function log(message, level = 'info') {
  const div = document.createElement('div');
  div.className = `log-entry ${level || ''}`.trim();
  div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  el.logList.appendChild(div);
  el.logList.scrollTop = el.logList.scrollHeight;
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function resetSetupProgress(message = '待機中') {
  el.setupProgress.hidden = true;
  el.setupProgressLabel.textContent = message;
  el.setupProgressMeta.textContent = '';
  el.setupProgressBar.style.width = '0%';
  el.setupProgress.querySelector('.progress-track')?.classList.remove('indeterminate');
  el.setupProgress.querySelector('.progress-track')?.setAttribute('aria-valuenow', '0');
}

function updateSetupProgress(entry = {}) {
  const phase = String(entry.phase || 'setup');
  const total = Number(entry.total || 0);
  const received = Number(entry.received || 0);
  const percent = Number.isFinite(Number(entry.percent)) ? Number(entry.percent) : (total > 0 ? (received / total) * 80 : null);
  const track = el.setupProgress.querySelector('.progress-track');

  el.setupProgress.hidden = false;
  el.setupProgressLabel.textContent = entry.message || (phase === 'download' ? '受信中...' : phase);
  if (total > 0) {
    el.setupProgressMeta.textContent = `${formatBytes(received)} / ${formatBytes(total)}`;
  } else if (received > 0) {
    el.setupProgressMeta.textContent = `${formatBytes(received)} 受信済み`;
  } else {
    el.setupProgressMeta.textContent = '';
  }

  if (percent == null || !Number.isFinite(percent)) {
    track?.classList.add('indeterminate');
    track?.removeAttribute('aria-valuenow');
    return;
  }

  const safePercent = Math.max(0, Math.min(100, percent));
  track?.classList.remove('indeterminate');
  track?.setAttribute('aria-valuenow', String(Math.round(safePercent)));
  el.setupProgressBar.style.width = `${safePercent}%`;
}

function iconId(name) {
  const candidate = `icon-${String(name || '').toLowerCase()}`;
  return document.getElementById(candidate) ? candidate : 'icon-puzzle';
}

function pluginEnabled(id) {
  return state.plugins.find((plugin) => plugin.id === id)?.enabled !== false;
}

function ensurePluginPage(plugin) {
  const page = String(plugin.renderer?.page || plugin.tab?.page || plugin.id).trim();
  const pageId = `page-${page}`;
  let section = document.getElementById(pageId);
  if (!section) {
    section = document.createElement('section');
    section.className = 'editor-page';
    section.id = pageId;
    section.dataset.pluginPageOwner = plugin.id;
    el.editorArea.appendChild(section);
  }
  return { section, page };
}

function switchPage(page) {
  const next = String(page || '').trim();
  document.querySelectorAll('.editor-page').forEach((section) => {
    section.classList.toggle('active', section.id === `page-${next}`);
  });
  document.querySelectorAll('.nav-btn').forEach((button) => {
    button.classList.toggle('active', button.dataset.page === next);
  });
  state.currentPage = next;
}

function createHostApi(plugin, roots) {
  const on = (eventName, handler) => {
    const type = String(eventName || '').trim();
    if (!type || typeof handler !== 'function') return () => {};
    const listener = (event) => handler(event.detail, event);
    runtime.eventTarget.addEventListener(type, listener);
    return () => runtime.eventTarget.removeEventListener(type, listener);
  };
  return {
    electronAPI: api,
    roots,
    capabilities: {
      get: (name) => getRuntimeCapability(runtime, name, pluginEnabled),
      all: (name) => getRuntimeCapabilities(runtime, name, pluginEnabled),
      list: () => listRuntimeCapabilities(runtime, pluginEnabled),
      require: (name, timeoutMs = 3000) => waitForRuntimeCapability(runtime, name, timeoutMs, (current) => getRuntimeCapability(runtime, current, pluginEnabled)),
    },
    events: {
      emit: (eventName, detail) => runtime.eventTarget.dispatchEvent(new CustomEvent(eventName, { detail })),
      on,
      off: (unsubscribe) => unsubscribe?.(),
    },
    plugins: {
      invokeHook: (id, hook, payload) => api.invokePluginHook(id, hook, payload),
    },
    refreshProject: refreshAll,
  };
}

async function activatePluginRenderers() {
  clearPluginRuntime(runtime, (err) => log(`プラグイン停止失敗: ${err?.message || err}`, 'warn'));
  document.querySelectorAll('.editor-page[data-plugin-page-owner]').forEach((page) => page.remove());

  for (const plugin of state.plugins) {
    if (!plugin.enabled || !plugin.hasRenderer || !plugin.rendererAssets?.scriptUrl) continue;
    const { section } = ensurePluginPage(plugin);
    section.innerHTML = '';
    for (const styleUrl of plugin.rendererAssets.styleUrls || []) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = styleUrl;
      link.dataset.pluginStyle = plugin.id;
      document.head.appendChild(link);
      runtime.styleLinks.push(link);
    }
    try {
      const module = await import(`${plugin.rendererAssets.scriptUrl}?v=${Date.now()}`);
      const activation = await module.activatePlugin({
        plugin,
        root: section,
        pageRoot: section,
        hostRoot: document.body,
        api: createHostApi(plugin, { root: section, pageRoot: section, hostRoot: document.body }),
        logger: {
          info: (message) => log(`${plugin.id}: ${message}`, 'info'),
          warn: (message) => log(`${plugin.id}: ${message}`, 'warn'),
          error: (message) => log(`${plugin.id}: ${message}`, 'error'),
          debug: (message) => log(`${plugin.id}: ${message}`, 'info'),
        },
        registerCapability: (name, implementation) => registerRuntimeCapability(runtime, plugin, name, implementation),
      });
      if (activation?.deactivate) runtime.activations.set(plugin.id, activation);
    } catch (err) {
      log(`${plugin.id} renderer 読み込み失敗: ${err?.message || err}`, 'error');
    }
  }
}

function renderTabs() {
  const tabs = state.plugins
    .filter((plugin) => plugin.enabled && plugin.tab)
    .sort((a, b) => Number(a.tab?.order ?? 1000) - Number(b.tab?.order ?? 1000))
    .map((plugin) => {
      const page = String(plugin.renderer?.page || plugin.tab?.page || plugin.id).trim();
      return `
        <button class="nav-btn" data-page="${esc(page)}" title="${esc(plugin.name)}">
          <svg class="icon"><use href="#${esc(iconId(plugin.icon || plugin.tab?.icon))}"></use></svg>
          <span>${esc(plugin.tab?.label || plugin.name)}</span>
        </button>
      `;
    });
  el.pluginTabs.innerHTML = tabs.join('');
  document.querySelectorAll('.nav-btn[data-page]').forEach((button) => {
    button.addEventListener('click', () => switchPage(button.dataset.page));
  });
}

async function loadPlugins() {
  state.plugins = await api.listPlugins();
  await activatePluginRenderers();
  renderTabs();
  renderPluginList();
  if (!state.currentPage) {
    const first = state.plugins.find((plugin) => plugin.enabled && plugin.tab);
    switchPage(String(first?.renderer?.page || first?.tab?.page || 'setup'));
  } else {
    switchPage(state.currentPage);
  }
}

function getCatalogTool(kind) {
  return state.setupCatalog?.tools?.find((tool) => tool.kind === kind) || null;
}

async function ensureSetupCatalog() {
  if (state.setupCatalog) return state.setupCatalog;
  const catalog = await api.getSetupCatalog();
  if (!catalog?.ok) throw new Error(catalog?.error || 'setup catalog を取得できませんでした');
  state.setupCatalog = catalog;
  renderDownloadKindOptions();
  return catalog;
}

function renderDownloadKindOptions() {
  if (!state.setupCatalog?.tools?.length) return;
  const current = el.downloadKind.value;
  el.downloadKind.innerHTML = state.setupCatalog.tools.map((tool) => (
    `<option value="${esc(tool.kind)}">${esc(tool.label)}</option>`
  )).join('');
  if (state.setupCatalog.tools.some((tool) => tool.kind === current)) {
    el.downloadKind.value = current;
  }
}

function selectedSetupVersion(kind = el.downloadKind.value) {
  const versions = state.setupVersions[kind] || [];
  return versions.find((version) => version.id === el.downloadVersion.value) || null;
}

function renderDownloadInfo(kind = el.downloadKind.value) {
  const tool = getCatalogTool(kind);
  const version = selectedSetupVersion(kind);
  const errors = state.setupVersionErrors[kind] || [];
  const rows = [];
  if (tool?.note) rows.push(['note', tool.note]);
  if (version) {
    rows.push(['source', `${version.source || ''}${version.assetName ? ` / ${version.assetName}` : ''}`.trim()]);
    rows.push(['license', version.license || tool?.license || '']);
    if (version.note) rows.push([version.available ? 'note' : 'warn', version.note]);
    if (!version.available) rows.push(['warn', 'この候補は現在のOS/CPUではDL対象外です。']);
  }
  for (const error of errors) rows.push(['warn', error]);
  el.downloadInfo.innerHTML = rows
    .filter(([, text]) => text)
    .map(([type, text]) => `<div class="${esc(type)}">${esc(text)}</div>`)
    .join('');
}

function renderDownloadVersions(kind = el.downloadKind.value) {
  const versions = state.setupVersions[kind] || [];
  if (versions.length === 0) {
    el.downloadVersion.innerHTML = '<option value="">候補なし</option>';
    el.btnDownloadTool.disabled = true;
    renderDownloadInfo(kind);
    return;
  }

  const previous = el.downloadVersion.value;
  const firstAvailable = versions.find((version) => version.available);
  const selected = versions.find((version) => version.id === previous) || firstAvailable || versions[0];
  el.downloadVersion.innerHTML = versions.map((version) => `
    <option value="${esc(version.id)}" ${version.available ? '' : 'disabled'}>
      ${esc(version.label)}${version.prerelease ? ' / pre-release' : ''}${version.available ? '' : ' / DL不可'}
    </option>
  `).join('');
  el.downloadVersion.value = selected?.id || '';
  el.btnDownloadTool.disabled = !selected?.available;
  renderDownloadInfo(kind);
}

async function loadSetupVersions(kind = el.downloadKind.value, { force = false } = {}) {
  await ensureSetupCatalog();
  if (!force && state.setupVersions[kind]) {
    renderDownloadVersions(kind);
    return;
  }
  el.downloadVersion.innerHTML = '<option value="">候補取得中...</option>';
  el.btnDownloadTool.disabled = true;
  el.downloadInfo.innerHTML = '<div class="note">GitHub Releases / CDN から候補を取得しています。</div>';
  const result = await api.listSetupVersions(kind);
  state.setupVersions[kind] = result?.versions || [];
  state.setupVersionErrors[kind] = result?.errors || (result?.ok === false ? [result.error || '候補取得に失敗しました'] : []);
  renderDownloadVersions(kind);
}

async function renderSetup() {
  await ensureSetupCatalog();
  const status = await api.getSetupStatus();
  renderDownloadKindOptions();
  await loadSetupVersions(el.downloadKind.value);
  const rows = [
    ['cc65', 'cc65', status.cc65],
    ['llvmMos', 'llvm-mos-sdk', status.llvmMos],
    ['superfamiconv', 'SuperFamiconv', status.superfamiconv],
    ['emulatorJs', 'EmulatorJS pce core', status.emulatorJs],
  ];
  el.setupStatus.innerHTML = rows.map(([kind, label, item]) => `
    <div class="status-row">
      <div>${esc(label)}</div>
      <div class="${item?.configured ? 'ok' : 'err'}">${item?.configured ? esc(item.path) : '未設定'}</div>
      <button class="mini-btn" data-tool-kind="${esc(kind)}">指定</button>
    </div>
  `).join('') + `
    <p class="meta">EmulatorJS / mednafen_pce は GPL 系のため、このリポジトリには同梱しません。上のDLまたはローカル指定で data/tools 配下に配置します。</p>
  `;
  el.setupStatus.querySelectorAll('[data-tool-kind]').forEach((button) => {
    button.addEventListener('click', async () => {
      const result = await api.pickFile({
        properties: button.dataset.toolKind === 'emulatorJs' ? ['openDirectory'] : ['openFile'],
        filters: [{ name: 'All Files', extensions: ['*'] }],
      });
      if (!result.canceled && result.filePath) {
        await api.setToolPath(button.dataset.toolKind, result.filePath);
        await renderSetup();
      }
    });
  });
}

async function renderProjects() {
  const result = await api.listProjects();
  el.projectList.innerHTML = (result.projects || []).map((project) => `
    <div class="project-row">
      <div>${esc(project.projectName)}</div>
      <div class="meta">${esc(project.toolchain)} ${project.current ? ' / current' : ''}</div>
      <button class="mini-btn" data-open-project="${esc(project.projectDir)}">開く</button>
    </div>
  `).join('');
  el.projectList.querySelectorAll('[data-open-project]').forEach((button) => {
    button.addEventListener('click', async () => {
      await api.openProject({ projectDir: button.dataset.openProject });
      await refreshAll();
    });
  });
}

function renderPluginList() {
  el.pluginList.innerHTML = state.plugins.map((plugin) => `
    <div class="plugin-row">
      <div>${esc(plugin.name)}</div>
      <div class="meta">${esc(plugin.id)} / ${esc((plugin.pluginTypes || []).join(', '))}</div>
      <label><input type="checkbox" data-plugin-enabled="${esc(plugin.id)}" ${plugin.enabled ? 'checked' : ''} /> 有効</label>
    </div>
  `).join('');
  el.pluginList.querySelectorAll('[data-plugin-enabled]').forEach((input) => {
    input.addEventListener('change', async () => {
      await api.setPluginEnabled(input.dataset.pluginEnabled, input.checked);
      await loadPlugins();
    });
  });
}

async function refreshProjectHeader() {
  const current = await api.getCurrentProject();
  state.project = current;
  el.projectChip.textContent = `${current.title}  ${current.toolchain}  ${current.projectDir}`;
}

async function refreshAll() {
  await refreshProjectHeader();
  await renderSetup();
  await renderProjects();
  await loadPlugins();
}

async function runBuild() {
  el.btnBuild.disabled = true;
  log('Build を開始します');
  const result = await api.runBuild();
  el.btnBuild.disabled = false;
  if (result.success) {
    log(`Build 成功: ${result.romPath} (${result.romSize} bytes)`, 'info');
  } else {
    log(`Build 失敗: ${result.error}`, 'error');
  }
}

async function runTestPlay() {
  el.btnTestPlay.disabled = true;
  log('Test Play 用に最新ROMをビルドします');
  const build = await api.runBuild();
  el.btnTestPlay.disabled = false;
  if (!build.success) {
    log(`Test Play 起動前ビルド失敗: ${build.error}`, 'error');
    return;
  }
  log(`Test Play ROM: ${build.romPath} (${build.romSize} bytes)`, 'info');
  const result = await api.openTestPlay(build.romPath);
  if (!result.ok) {
    log(`Test Play 起動失敗: ${result.error}`, 'error');
    switchPage('setup');
  } else if (result.needsSetup) {
    log(result.error, 'warn');
    switchPage('setup');
  }
}

el.btnSetup.addEventListener('click', () => switchPage('setup'));
el.btnBuild.addEventListener('click', runBuild);
el.btnTestPlay.addEventListener('click', runTestPlay);
el.btnRefreshSetup.addEventListener('click', renderSetup);
el.downloadKind.addEventListener('change', () => loadSetupVersions(el.downloadKind.value).catch((err) => log(`候補取得失敗: ${err?.message || err}`, 'error')));
el.downloadVersion.addEventListener('change', () => renderDownloadVersions(el.downloadKind.value));
el.btnRefreshVersions.addEventListener('click', () => loadSetupVersions(el.downloadKind.value, { force: true }).catch((err) => log(`候補更新失敗: ${err?.message || err}`, 'error')));
el.btnDownloadTool.addEventListener('click', async () => {
  const kind = el.downloadKind.value;
  const version = selectedSetupVersion(kind);
  if (!version?.available || !version.downloadUrl) {
    log('この環境でDLできる候補を選択してください', 'warn');
    return;
  }
  el.btnDownloadTool.disabled = true;
  updateSetupProgress({ phase: 'download', message: `${version.label} を開始しています`, percent: 0 });
  try {
    const result = await api.downloadTool({
      url: version.downloadUrl,
      destName: version.archiveName || version.assetName,
      settingKind: kind,
      targetDir: version.targetDir,
    });
    if (!result.ok) {
      log(`DL 失敗: ${result.error}`, 'error');
      updateSetupProgress({ phase: 'error', message: 'DL に失敗しました', percent: 100 });
    } else {
      log(`DL 完了: ${result.configuredPath || result.path}`, 'info');
      updateSetupProgress({ phase: 'done', message: 'DL 完了', percent: 100 });
    }
    await renderSetup();
  } catch (err) {
    log(`DL 失敗: ${err?.message || err}`, 'error');
    updateSetupProgress({ phase: 'error', message: 'DL に失敗しました', percent: 100 });
  } finally {
    el.btnDownloadTool.disabled = false;
  }
});
el.btnOpenPlugins.addEventListener('click', () => api.openPluginsFolder());
el.btnOpenProjectFolder.addEventListener('click', async () => {
  const current = await api.getCurrentProject();
  await api.openPath(current.projectDir);
});
el.btnCreateSample.addEventListener('click', async () => {
  const name = el.newProjectName.value.trim() || 'sample_pce_game';
  const result = await api.createSampleProject({ projectName: name });
  if (!result.ok) log(`サンプル作成失敗: ${result.error}`, 'error');
  await refreshAll();
});

api.onBuildLog((entry) => log(entry.text, entry.level));
api.onBuildEnd((result) => log(result.success ? 'build-end: success' : `build-end: ${result.error}`, result.success ? 'info' : 'error'));
api.onPluginLog((entry) => log(`${entry.pluginId}: ${entry.message}`, entry.level));
api.onSetupProgress((entry) => updateSetupProgress(entry));

resetSetupProgress();
refreshAll().catch((err) => log(`起動処理失敗: ${err?.message || err}`, 'error'));
