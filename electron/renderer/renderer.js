import MdEmulator from '../md-emulator.js';

const WASM_JS_URL = new URL('../pkg/md_wasm.js', import.meta.url).href;

const state = {
  mode: 'wasm',
  emu: null,
  muted: false,
  wasmRunning: false,
  apiRunning: false,
  apiPort: 8080,
  screenScale: 2.0,
  logCollapsed: false,
};

const el = {
  modeTabs: Array.from(document.querySelectorAll('.mode-tab')),
  modeOnly: Array.from(document.querySelectorAll('[data-mode-only]')),
  content: document.querySelector('.content'),
  screen: document.querySelector('#screen'),
  screenPanel: document.querySelector('#screenPanel'),
  apiPanel: document.querySelector('#apiPanel'),
  apiModeStatus: document.querySelector('#apiModeStatus'),
  screenScaleSelect: document.querySelector('#screenScaleSelect'),
  openRom: document.querySelector('#openRomButton'),
  playPause: document.querySelector('#playPauseButton'),
  reset: document.querySelector('#resetButton'),
  mute: document.querySelector('#muteButton'),
  apiPower: document.querySelector('#apiPowerButton'),
  apiStep: document.querySelector('#apiStepButton'),
  openDebug: document.querySelector('#openDebugButton'),
  logSection: document.querySelector('#logSection'),
  copyLog: document.querySelector('#copyLogButton'),
  toggleLog: document.querySelector('#toggleLogButton'),
  status: document.querySelector('#statusLine'),
  log: document.querySelector('#logPanel'),
};

function setButtonIcon(button, iconId, title) {
  const use = button.querySelector('use');
  if (use) {
    use.setAttribute('href', `#${iconId}`);
  }
  button.title = title;
  button.setAttribute('aria-label', title);
}

function normalizeJsonPayload(value) {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value);
    } catch (_err) {
      return value;
    }
  }
  return value;
}

function appendLog(message, level = 'info') {
  const timestamp = new Date().toLocaleTimeString();
  el.log.textContent += `[${timestamp}] [${level.toUpperCase()}] ${message}\n`;
  el.log.scrollTop = el.log.scrollHeight;
}

function setStatus(text) {
  el.status.textContent = text;
}

function updateModeTabs() {
  for (const tab of el.modeTabs) {
    const active = tab.dataset.mode === state.mode;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  }
}

function applyModeView() {
  const isWasm = state.mode === 'wasm';

  el.screenPanel.classList.toggle('hidden', !isWasm);
  el.apiPanel.classList.toggle('hidden', isWasm);
  el.screenScaleSelect.disabled = !isWasm;

  for (const node of el.modeOnly) {
    node.classList.toggle('hidden', node.dataset.modeOnly !== state.mode);
  }

  if (!isWasm) {
    el.apiModeStatus.textContent = `REST API モードです (port=${state.apiPort})。ROM をロードすると md-api 側で再生を開始します。`;
  }
}

function updateRunButtons() {
  setButtonIcon(el.playPause, state.wasmRunning ? 'icon-pause' : 'icon-play', state.wasmRunning ? 'Pause' : 'Play');
  el.playPause.classList.toggle('active-toggle', state.wasmRunning);

  setButtonIcon(el.mute, state.muted ? 'icon-mute' : 'icon-volume', state.muted ? 'Unmute' : 'Mute');
  el.mute.classList.toggle('active-toggle', !state.muted);

  setButtonIcon(el.apiPower, 'icon-power', state.apiRunning ? 'Stop API' : 'Start API');
  el.apiPower.classList.toggle('danger-toggle', state.apiRunning);

  el.apiModeStatus.textContent = `REST API モードです (port=${state.apiPort})。API は ${state.apiRunning ? '稼働中' : '停止中'} です。ROM をロードすると md-api 側で再生を開始します。`;
}

function applyLogCollapsed() {
  el.logSection.classList.toggle('collapsed', state.logCollapsed);
  el.toggleLog.setAttribute('aria-expanded', String(!state.logCollapsed));
  el.toggleLog.title = state.logCollapsed ? 'Expand Log' : 'Collapse Log';
  el.toggleLog.setAttribute('aria-label', state.logCollapsed ? 'Expand Log' : 'Collapse Log');
}

function applyScreenScale(scale) {
  const allowed = [0.5, 1, 2];
  const numeric = Number(scale);
  const next = allowed.includes(numeric) ? numeric : 2;
  state.screenScale = next;
  el.screen.style.setProperty('--screen-scale', String(state.screenScale));
  el.screenScaleSelect.value = String(state.screenScale);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureWasmEmulator() {
  if (state.emu) {
    return state.emu;
  }

  const emu = new MdEmulator({
    wasmJsUrl: WASM_JS_URL,
    audio: true,
    sram: true,
  });

  emu.attachCanvas(el.screen);
  emu.addEventListener('ready', () => appendLog(`WASM ready (build=${emu.buildVersion})`));
  emu.addEventListener('romloaded', () => appendLog('ROM loaded')); 
  emu.addEventListener('error', (ev) => appendLog(ev?.detail?.message || 'unknown error', 'error'));

  appendLog(`WASM module URL: ${WASM_JS_URL}`);

  await emu.init();
  state.emu = emu;

  return emu;
}

async function loadRomInWasm(filePath) {
  const bytes = await window.electronAPI.readRomFile(filePath);
  const data = new Uint8Array(bytes);
  const emu = await ensureWasmEmulator();

  await emu.loadRom(data, filePath.split(/[\\/]/).pop());
  emu.play();
  state.wasmRunning = true;
  updateRunButtons();
  appendLog('Auto play started (WASM)');
  setStatus(`Loaded (WASM): ${filePath}`);
}

async function loadRomInApi(filePath) {
  const endpoint = `http://127.0.0.1:${state.apiPort}/api/v1/emulator/load-rom-path`;
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: filePath }),
  });

  if (!res.ok) {
    throw new Error(`API load-rom-path failed (${res.status})`);
  }

  await callApi('/api/v1/emulator/resume', {
    method: 'POST',
  });
  appendLog('Auto play started (API resume)');

  setStatus(`Loaded (API): ${filePath}`);
}

async function waitForApiHealth(maxRetries = 20, intervalMs = 250) {
  for (let i = 0; i < maxRetries; i += 1) {
    try {
      await callApi('/api/v1/health');
      return true;
    } catch (_err) {
      await sleep(intervalMs);
    }
  }
  return false;
}

async function ensureApiReady() {
  const running = await window.electronAPI.isApiServerRunning();
  if (running?.port) {
    state.apiPort = Number(running.port);
  }

  if (!running?.running) {
    await startApi();
  }

  const ok = await waitForApiHealth();
  if (!ok) {
    throw new Error(`md-api health check timed out (port=${state.apiPort})`);
  }
}

async function handleOpenRom(filePathFromMenu) {
  try {
    let filePath = filePathFromMenu;

    if (!filePath) {
      const result = await window.electronAPI.openRomDialog();
      if (result.canceled || !result.filePath) {
        return;
      }
      filePath = result.filePath;
    }

    appendLog(`Selected ROM: ${filePath}`);

    if (state.mode === 'wasm') {
      await loadRomInWasm(filePath);
      appendLog('ROM loaded in WASM mode');
    } else {
      await ensureApiReady();
      await loadRomInApi(filePath);
      appendLog('ROM loaded via REST API mode');
    }
  } catch (err) {
    appendLog(err.message || String(err), 'error');
    setStatus('ROM load failed');
  }
}

async function callApi(path, options = {}) {
  const url = `http://127.0.0.1:${state.apiPort}${path}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`API ${path} failed (${res.status})`);
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }

  return res.text();
}

async function startApi() {
  try {
    const result = await window.electronAPI.startApiServer({ port: state.apiPort });
    if (result?.port) {
      state.apiPort = Number(result.port);
    }

    if (result?.alreadyRunning) {
      appendLog(`md-api is already running on port ${state.apiPort}`);
    } else {
      appendLog(`md-api start requested on port ${state.apiPort}`);
      if (result?.fallbackUsed) {
        appendLog(`Requested port ${result.requestedPort} was busy. Switched to ${result.port}.`, 'warn');
      }
    }

    await callApi('/api/v1/health');
    state.apiRunning = true;
    updateRunButtons();
    setStatus(`API healthy (127.0.0.1:${state.apiPort})`);
    appendLog(`API health check ok on port ${state.apiPort}`);
  } catch (err) {
    appendLog(err.message || String(err), 'error');
  }
}

async function stopApi() {
  const result = await window.electronAPI.stopApiServer();
  state.apiRunning = false;
  updateRunButtons();
  appendLog(result?.stopped ? 'md-api stopped' : 'md-api was not running');
}

async function onPlay() {
  try {
    if (state.mode === 'wasm') {
      const emu = await ensureWasmEmulator();
      if (state.wasmRunning) {
        emu.pause();
        state.wasmRunning = false;
        setStatus('Paused');
      } else {
        emu.play();
        state.wasmRunning = true;
        setStatus('Running (WASM)');
      }
      updateRunButtons();
      return;
    }

    await callApi('/api/v1/emulator/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ frames: 1 }),
    });
    setStatus('Stepped 1 frame (API)');
  } catch (err) {
    appendLog(err.message || String(err), 'error');
  }
}

async function onApiStep() {
  try {
    await ensureApiReady();
    await callApi('/api/v1/emulator/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ frames: 1 }),
    });
    setStatus('Stepped 1 frame (API)');
  } catch (err) {
    appendLog(err.message || String(err), 'error');
  }
}

function onPause() {
  if (state.mode !== 'wasm') {
    setStatus('Pause is WASM-only in this scaffold');
    return;
  }

  if (state.emu) {
    state.emu.pause();
    setStatus('Paused');
  }
}

async function onReset() {
  try {
    if (state.mode === 'wasm') {
      if (state.emu) {
        state.emu.reset();
        setStatus('Reset (WASM)');
      }
      return;
    }

    await callApi('/api/v1/emulator/reset', { method: 'POST' });
    setStatus('Reset (API)');
  } catch (err) {
    appendLog(err.message || String(err), 'error');
  }
}

async function onMuteToggle() {
  state.muted = !state.muted;

  if (state.mode === 'wasm' && state.emu) {
    state.emu.setMuted(state.muted);
  }

  updateRunButtons();
  setStatus(state.muted ? 'Muted' : 'Unmuted');
}

async function copyRuntimeLog() {
  const text = el.log.textContent || '';
  if (!text.trim()) {
    setStatus('Runtime Log is empty');
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus('Runtime Log copied');
    appendLog('Runtime Log copied to clipboard');
  } catch (_err) {
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    document.body.removeChild(area);
    setStatus('Runtime Log copied (fallback)');
    appendLog('Runtime Log copied via fallback');
  }
}

async function openDebugWindow() {
  try {
    await window.electronAPI.openDebugWindow({ mode: state.mode, apiPort: state.apiPort });
    appendLog('Debug subwindow opened');
  } catch (err) {
    appendLog(err.message || String(err), 'error');
  }
}

function isRomPath(filePath) {
  return /\.(bin|md|gen|smd|sms|zip)$/i.test(filePath || '');
}

function bindDragAndDrop() {
  const getDropTarget = () => (state.mode === 'wasm' ? el.screenPanel : el.apiPanel);
  const activate = () => getDropTarget().classList.add('drag-over');
  const deactivate = () => {
    el.screenPanel.classList.remove('drag-over');
    el.apiPanel.classList.remove('drag-over');
  };

  window.addEventListener('dragover', (ev) => {
    ev.preventDefault();
    activate();
  });

  window.addEventListener('dragleave', (ev) => {
    if (ev.relatedTarget == null) {
      deactivate();
    }
  });

  window.addEventListener('drop', async (ev) => {
    ev.preventDefault();
    deactivate();

    const file = ev.dataTransfer?.files?.[0];
    if (!file?.path) {
      appendLog('Drop ignored: no file path found', 'warn');
      return;
    }

    if (!isRomPath(file.path)) {
      appendLog(`Drop ignored: unsupported file type (${file.path})`, 'warn');
      return;
    }

    appendLog(`Dropped ROM: ${file.path}`);
    await handleOpenRom(file.path);
  });
}

function bindEvents() {
  for (const tab of el.modeTabs) {
    tab.addEventListener('click', () => {
      state.mode = tab.dataset.mode;
      updateModeTabs();
      applyModeView();
      setStatus(`Mode: ${state.mode}`);
      appendLog(`Mode switched to ${state.mode}`);
    });
  }

  el.screenScaleSelect.addEventListener('change', (ev) => {
    applyScreenScale(ev.target.value);
  });

  el.openRom.addEventListener('click', () => handleOpenRom());
  el.playPause.addEventListener('click', onPlay);
  el.reset.addEventListener('click', onReset);
  el.mute.addEventListener('click', onMuteToggle);
  el.apiPower.addEventListener('click', () => {
    if (state.apiRunning) {
      stopApi();
    } else {
      startApi();
    }
  });
  el.apiStep.addEventListener('click', onApiStep);
  el.openDebug.addEventListener('click', openDebugWindow);
  el.copyLog.addEventListener('click', copyRuntimeLog);
  el.toggleLog.addEventListener('click', () => {
    state.logCollapsed = !state.logCollapsed;
    applyLogCollapsed();
  });

  window.electronAPI.onRomSelected((payload) => {
    if (payload?.filePath) {
      handleOpenRom(payload.filePath);
    }
  });

  window.electronAPI.onApiLog((payload) => {
    appendLog(payload?.message?.trim?.() || String(payload?.message || ''), payload?.level || 'info');
  });

  window.electronAPI.onApiExit((payload) => {
    state.apiRunning = false;
    updateRunButtons();
    appendLog(`md-api exited (code=${payload?.code}, signal=${payload?.signal})`, 'warn');
  });
}

async function bootstrap() {
  bindEvents();
  bindDragAndDrop();
  updateModeTabs();
  applyModeView();
  applyLogCollapsed();
  applyScreenScale(state.screenScale);
  updateRunButtons();
  setStatus('Bootstrapping...');

  try {
    await ensureWasmEmulator();
    setStatus('Ready (WASM mode)');
  } catch (err) {
    appendLog(err.message || String(err), 'error');
    setStatus('WASM init failed');
  }

  const running = await window.electronAPI.isApiServerRunning();
  if (running?.port) {
    state.apiPort = Number(running.port);
  }
  state.apiRunning = !!running?.running;
  updateRunButtons();
  appendLog(running?.running ? `md-api already running (port=${state.apiPort})` : 'md-api not running');

  window.__mdDebugBridge = {
    getWasmDebugSnapshot: async (palette = 0) => {
      if (!state.emu || !state.emu.handle) {
        return { ok: false, error: 'WASM emulator is not initialized' };
      }

      try {
        const h = state.emu.handle;
        const registers = normalizeJsonPayload(h.get_vdp_registers_json());
        const planeA = normalizeJsonPayload(h.debug_render_plane('A'));
        const planeB = normalizeJsonPayload(h.debug_render_plane('B'));
        const planeW = normalizeJsonPayload(h.debug_render_plane('W'));
        const tiles = normalizeJsonPayload(h.debug_render_tiles(Number(palette) || 0));
        const cram = normalizeJsonPayload(h.debug_cram_colors_json());
        const sprites = normalizeJsonPayload(h.debug_sprites_json());
        const framePixels = Array.from(h.get_framebuffer_argb());

        return {
          ok: true,
          source: 'wasm',
          palette: Number(palette) || 0,
          registers,
          planes: { A: planeA, B: planeB, W: planeW },
          tiles,
          cram,
          sprites,
          frame: {
            width: 320,
            height: 224,
            pixels_argb: framePixels,
          },
        };
      } catch (err) {
        return { ok: false, error: String(err?.message || err) };
      }
    },
  };
}

bootstrap();
