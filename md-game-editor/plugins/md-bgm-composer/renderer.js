const CHANNELS = ['FM1', 'FM2', 'FM3', 'FM4', 'FM5', 'PSG1', 'PSG2', 'PSG3', 'NOISE'];
const ROWS_PER_PATTERN = 64;
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

let audioContext = null;
let previewTimers = [];

export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  const state = {
    plugin,
    api,
    song: createDefaultSong(),
    selectedPattern: 0,
    selectedInstrument: 'fm_bell',
    undo: [],
    redo: [],
    diagnostics: [],
    allocations: [],
    midiSourcePath: '',
    status: '',
  };

  const wrapper = document.createElement('div');
  wrapper.className = 'md-bgm-composer-shell';
  wrapper.innerHTML = renderShell();
  api.mountElement(wrapper, 'page');

  const els = queryElements(wrapper);
  bindToolbar({ plugin, api, logger, state, els });
  bindSettings({ state, els });
  renderAll(state, els);

  registerCapability('md-bgm-composer', {
    getSong: () => structuredClone(state.song),
    setSong(song) {
      pushUndo(state);
      state.song = normalizeSong(song);
      state.selectedPattern = state.song.order[0] || 0;
      renderAll(state, els);
    },
    validate: () => validateViaMain(plugin, api, state, els),
  });

  registerCapability('music-import-handler', {
    async importMidi(sourcePath) {
      return importMidiFile({ plugin, api, state, els, sourcePath });
    },
  });

  logger.debug('md-bgm-composer renderer activated');
  return {
    deactivate() {
      stopPreview();
      wrapper.remove();
    },
  };
}

function renderShell() {
  return `
    <div class="md-bgm-toolbar" role="toolbar" aria-label="BGM composer toolbar">
      <button type="button" class="md-bgm-btn" data-action="import-midi" title="MIDIファイルを読み込む">Import MIDI</button>
      <button type="button" class="md-bgm-btn primary" data-action="export" title="VGM/XGMを書き出す">Export</button>
      <button type="button" class="md-bgm-icon" data-action="play" title="プレビュー再生" aria-label="プレビュー再生">▶</button>
      <button type="button" class="md-bgm-icon" data-action="stop" title="停止" aria-label="停止">■</button>
      <button type="button" class="md-bgm-icon" data-action="validate" title="検証" aria-label="検証">✓</button>
      <button type="button" class="md-bgm-icon" data-action="undo" title="Undo" aria-label="Undo">↶</button>
      <button type="button" class="md-bgm-icon" data-action="redo" title="Redo" aria-label="Redo">↷</button>
      <span class="md-bgm-status" data-role="status"></span>
    </div>
    <div class="md-bgm-layout">
      <aside class="md-bgm-sidebar left">
        <section>
          <div class="md-bgm-section-title">Songs</div>
          <button type="button" class="md-bgm-song active" data-action="select-song">New BGM</button>
        </section>
        <section>
          <div class="md-bgm-section-title">Instruments</div>
          <div class="md-bgm-instruments" data-role="instruments"></div>
        </section>
      </aside>
      <main class="md-bgm-main">
        <div class="md-bgm-pattern-strip" data-role="patterns"></div>
        <div class="md-bgm-tracker-wrap">
          <table class="md-bgm-tracker" data-role="tracker"></table>
        </div>
      </main>
      <aside class="md-bgm-sidebar right">
        <section class="md-bgm-form">
          <div class="md-bgm-section-title">Song</div>
          <label>Title<input data-field="title" type="text"></label>
          <label>Artist<input data-field="artist" type="text"></label>
          <label>Symbol<input data-field="symbol" type="text"></label>
          <div class="md-bgm-pair">
            <label>Tempo<input data-field="tempo" type="number" min="30" max="300"></label>
            <label>Speed<input data-field="speed" type="number" min="1" max="31"></label>
          </div>
        </section>
        <section class="md-bgm-form" data-role="instrument-editor"></section>
        <section>
          <div class="md-bgm-section-title">Import Mapping</div>
          <div class="md-bgm-allocations" data-role="allocations"></div>
        </section>
        <section>
          <div class="md-bgm-section-title">Diagnostics</div>
          <div class="md-bgm-diagnostics" data-role="diagnostics"></div>
        </section>
      </aside>
    </div>
  `;
}

function queryElements(root) {
  return {
    status: root.querySelector('[data-role="status"]'),
    patterns: root.querySelector('[data-role="patterns"]'),
    tracker: root.querySelector('[data-role="tracker"]'),
    instruments: root.querySelector('[data-role="instruments"]'),
    instrumentEditor: root.querySelector('[data-role="instrument-editor"]'),
    diagnostics: root.querySelector('[data-role="diagnostics"]'),
    allocations: root.querySelector('[data-role="allocations"]'),
    fields: Array.from(root.querySelectorAll('[data-field]')),
  };
}

function createDefaultSong() {
  return {
    version: 1,
    title: 'New BGM',
    artist: '',
    symbol: 'bgm_001',
    tempo: 150,
    speed: 6,
    rowsPerPattern: ROWS_PER_PATTERN,
    channels: CHANNELS.map((id) => ({ id, type: id.startsWith('FM') ? 'fm' : id === 'NOISE' ? 'noise' : 'psg', label: id })),
    order: [0],
    patterns: [{ id: 0, name: 'Pattern 00', rows: emptyRows() }],
    instruments: [
      { id: 'fm_bell', name: 'FM Bell', type: 'fm', algorithm: 4, feedback: 2, pan: 'center' },
      { id: 'psg_square', name: 'PSG Square', type: 'psg', volume: 10, envelope: 'hold' },
      { id: 'noise_kit', name: 'Noise Kit', type: 'noise', volume: 10, noiseFrequency: 'clocked' },
    ],
    metadata: { profile: 'xgm2-safe', createdBy: 'md-bgm-composer' },
  };
}

function emptyRows() {
  return Array.from({ length: ROWS_PER_PATTERN }, () => ({ cells: {} }));
}

function normalizeSong(song) {
  const base = createDefaultSong();
  const next = { ...base, ...(song || {}) };
  next.order = Array.isArray(next.order) && next.order.length ? next.order : [0];
  next.patterns = Array.isArray(next.patterns) && next.patterns.length ? next.patterns : base.patterns;
  next.instruments = Array.isArray(next.instruments) && next.instruments.length ? next.instruments : base.instruments;
  next.patterns.forEach((pattern) => {
    pattern.rows = Array.isArray(pattern.rows) ? pattern.rows : emptyRows();
    while (pattern.rows.length < ROWS_PER_PATTERN) pattern.rows.push({ cells: {} });
  });
  return next;
}

function bindToolbar({ plugin, api, logger, state, els }) {
  els.status.closest('.md-bgm-toolbar').addEventListener('click', async (event) => {
    const action = event.target?.dataset?.action;
    if (!action) return;
    if (action === 'import-midi') await pickAndImportMidi({ plugin, api, state, els });
    if (action === 'export') await exportSong({ plugin, api, logger, state, els });
    if (action === 'play') playPreview(state.song, state.selectedPattern);
    if (action === 'stop') stopPreview();
    if (action === 'validate') await validateViaMain(plugin, api, state, els);
    if (action === 'undo') restoreHistory(state, els, 'undo');
    if (action === 'redo') restoreHistory(state, els, 'redo');
  });
}

function bindSettings({ state, els }) {
  els.fields.forEach((field) => {
    field.addEventListener('change', () => {
      pushUndo(state);
      const key = field.dataset.field;
      state.song[key] = field.type === 'number' ? Number(field.value) : field.value;
      renderAll(state, els);
    });
  });
}

function renderAll(state, els) {
  renderStatus(state, els);
  renderSongFields(state, els);
  renderPatterns(state, els);
  renderTracker(state, els);
  renderInstruments(state, els);
  renderInstrumentEditor(state, els);
  renderDiagnostics(state, els);
  renderAllocations(state, els);
}

function renderStatus(state, els) {
  els.status.textContent = state.status || `${state.song.title} / ${state.song.symbol}`;
}

function renderSongFields(state, els) {
  els.fields.forEach((field) => {
    const value = state.song[field.dataset.field];
    if (String(field.value) !== String(value ?? '')) field.value = value ?? '';
  });
}

function renderPatterns(state, els) {
  els.patterns.innerHTML = '';
  state.song.order.forEach((patternId, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `md-bgm-pattern${patternId === state.selectedPattern ? ' active' : ''}`;
    button.textContent = `${String(index).padStart(2, '0')}: P${String(patternId).padStart(2, '0')}`;
    button.addEventListener('click', () => {
      state.selectedPattern = patternId;
      renderAll(state, els);
    });
    els.patterns.appendChild(button);
  });
}

function renderTracker(state, els) {
  const pattern = state.song.patterns.find((entry) => entry.id === state.selectedPattern) || state.song.patterns[0];
  const header = `<thead><tr><th>Row</th>${CHANNELS.map((id) => `<th>${id}</th>`).join('')}</tr></thead>`;
  const body = pattern.rows.map((row, rowIndex) => {
    const cells = CHANNELS.map((channelId) => {
      const cell = row.cells?.[channelId] || {};
      const value = cell.note ? `${cell.note} ${cell.instrument || ''} ${cell.effect || ''}`.trim() : '';
      return `<td><input data-row="${rowIndex}" data-channel="${channelId}" value="${escapeHtml(value)}" placeholder="---"></td>`;
    }).join('');
    return `<tr><th>${String(rowIndex).padStart(2, '0')}</th>${cells}</tr>`;
  }).join('');
  els.tracker.innerHTML = `${header}<tbody>${body}</tbody>`;
  els.tracker.querySelectorAll('input').forEach((input) => {
    input.addEventListener('change', () => {
      pushUndo(state);
      updateCellFromText(pattern, Number(input.dataset.row), input.dataset.channel, input.value, state.selectedInstrument);
      renderAll(state, els);
    });
  });
}

function updateCellFromText(pattern, rowIndex, channelId, text, selectedInstrument) {
  const row = pattern.rows[rowIndex];
  const tokens = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) {
    delete row.cells[channelId];
    return;
  }
  const note = tokens[0].toUpperCase();
  const instrument = tokens[1] || selectedInstrument;
  const effect = tokens[2] || '';
  row.cells[channelId] = {
    note,
    midiNote: note === 'N' ? null : noteNameToMidi(note),
    instrument,
    volume: 12,
    effect,
  };
}

function renderInstruments(state, els) {
  els.instruments.innerHTML = '';
  state.song.instruments.forEach((instrument) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `md-bgm-instrument${instrument.id === state.selectedInstrument ? ' active' : ''}`;
    button.textContent = `${instrument.name} (${instrument.type.toUpperCase()})`;
    button.addEventListener('click', () => {
      state.selectedInstrument = instrument.id;
      renderAll(state, els);
    });
    els.instruments.appendChild(button);
  });
}

function renderInstrumentEditor(state, els) {
  const instrument = state.song.instruments.find((entry) => entry.id === state.selectedInstrument) || state.song.instruments[0];
  if (!instrument) return;
  const fm = instrument.type === 'fm';
  els.instrumentEditor.innerHTML = `
    <div class="md-bgm-section-title">Instrument</div>
    <label>Name<input data-inst-field="name" type="text" value="${escapeHtml(instrument.name || '')}"></label>
    <label>Type<select data-inst-field="type">
      <option value="fm"${instrument.type === 'fm' ? ' selected' : ''}>FM</option>
      <option value="psg"${instrument.type === 'psg' ? ' selected' : ''}>PSG</option>
      <option value="noise"${instrument.type === 'noise' ? ' selected' : ''}>Noise</option>
    </select></label>
    ${fm ? `
      <div class="md-bgm-pair">
        <label>Algorithm<input data-inst-field="algorithm" type="number" min="0" max="7" value="${Number(instrument.algorithm) || 0}"></label>
        <label>Feedback<input data-inst-field="feedback" type="number" min="0" max="7" value="${Number(instrument.feedback) || 0}"></label>
      </div>
      <label>Pan<select data-inst-field="pan">
        ${['left', 'center', 'right'].map((pan) => `<option value="${pan}"${instrument.pan === pan ? ' selected' : ''}>${pan}</option>`).join('')}
      </select></label>
    ` : `
      <label>Volume<input data-inst-field="volume" type="range" min="0" max="15" value="${Number(instrument.volume) || 10}"></label>
      <label>Envelope<select data-inst-field="envelope">
        ${['hold', 'fade', 'pluck'].map((env) => `<option value="${env}"${instrument.envelope === env ? ' selected' : ''}>${env}</option>`).join('')}
      </select></label>
    `}
  `;
  els.instrumentEditor.querySelectorAll('[data-inst-field]').forEach((field) => {
    field.addEventListener('change', () => {
      pushUndo(state);
      instrument[field.dataset.instField] = field.type === 'number' || field.type === 'range' ? Number(field.value) : field.value;
      renderAll(state, els);
    });
  });
}

function renderDiagnostics(state, els) {
  if (!state.diagnostics.length) {
    els.diagnostics.innerHTML = '<p class="muted">問題はありません。</p>';
    return;
  }
  els.diagnostics.innerHTML = state.diagnostics.map((diag) => (
    `<div class="md-bgm-diagnostic ${escapeHtml(diag.level || 'info')}">
      <strong>${escapeHtml(diag.code || 'info')}</strong>
      <span>${escapeHtml(diag.message || '')}</span>
    </div>`
  )).join('');
}

function renderAllocations(state, els) {
  if (!state.allocations.length) {
    els.allocations.innerHTML = '<p class="muted">MIDI import 後に割当が表示されます。</p>';
    return;
  }
  els.allocations.innerHTML = `
    ${state.allocations.map((allocation, index) => `
    <label>${escapeHtml(allocation.trackName || allocation.key)}
      <select data-allocation="${index}">
        ${['FM1', 'FM2', 'FM3', 'FM4', 'FM5', 'PSG1', 'PSG2', 'PSG3', 'NOISE', 'ignore'].map((target) => (
          `<option value="${target}"${allocation.target === target ? ' selected' : ''}>${target}</option>`
        )).join('')}
      </select>
    </label>
    `).join('')}
    <button type="button" class="md-bgm-btn compact" data-action="apply-mapping">Apply Mapping</button>
  `;
  els.allocations.querySelectorAll('[data-allocation]').forEach((select) => {
    select.addEventListener('change', () => {
      state.allocations[Number(select.dataset.allocation)].target = select.value;
      state.status = '割当を変更しました。Apply Mapping で変換に反映します。';
      renderAll(state, els);
    });
  });
  els.allocations.querySelector('[data-action="apply-mapping"]')?.addEventListener('click', async () => {
    if (!state.midiSourcePath) return;
    await importMidiFile({
      plugin: state.plugin,
      api: state.api,
      state,
      els,
      sourcePath: state.midiSourcePath,
    });
  });
}

async function pickAndImportMidi(args) {
  const result = await args.api.electronAPI.pickFile({
    properties: ['openFile'],
    filters: [{ name: 'MIDI', extensions: ['mid', 'midi'] }],
  });
  if (result?.canceled || !result?.sourcePath) return;
  await importMidiFile({ ...args, sourcePath: result.sourcePath });
}

async function importMidiFile({ plugin, api, state, els, sourcePath }) {
  setBusy(state, els, 'MIDI を解析しています...');
  const result = await api.plugins.invokeHook(plugin.id, 'importMidi', {
    sourcePath,
    allocations: state.allocations,
  });
  if (!result?.ok) {
    state.status = result?.error || 'MIDI import に失敗しました。';
    renderAll(state, els);
    return result;
  }
  pushUndo(state);
  state.song = normalizeSong(result.song);
  state.selectedPattern = state.song.order[0] || 0;
  state.diagnostics = result.diagnostics || [];
  state.allocations = result.allocations || [];
  state.midiSourcePath = sourcePath;
  const converted = await convertImportedMidiFile({ api, state, sourcePath });
  if (converted?.diagnostics?.length) {
    state.diagnostics = [...state.diagnostics, ...converted.diagnostics];
  }
  state.status = converted?.ok
    ? `MIDI import と VGM/XGM 生成が完了しました: ${converted.files?.vgm || ''}${converted.files?.xgm ? ` / ${converted.files.xgm}` : ''}`
    : 'MIDI import が完了しました。';
  renderAll(state, els);
  return result;
}

async function convertImportedMidiFile({ api, state, sourcePath }) {
  const converter = api.capabilities.get('midi-convert-ui');
  if (!converter?.convertMidiMusic) {
    return {
      ok: false,
      diagnostics: [{
        level: 'info',
        code: 'midi-converter-unavailable',
        message: 'midi-converter が利用できないため、編集用 import のみ実行しました。',
      }],
    };
  }
  let result = null;
  try {
    result = await converter.convertMidiMusic({
      sourcePath,
      symbol: state.song.symbol,
      outputs: { vgm: true, xgm: true, registerAsset: false },
    });
  } catch (error) {
    result = { ok: false, error: String(error?.message || error) };
  }
  if (!result?.ok) {
    return {
      ok: false,
      diagnostics: [{
        level: 'warn',
        code: 'midi-converter-failed',
        message: result?.error || 'midi-converter による VGM/XGM 生成に失敗しました。',
      }],
    };
  }
  return {
    ok: true,
    files: result.files || {},
    diagnostics: [
      {
        level: 'info',
        code: 'midi-converter-output',
        message: `midi-converter で VGM${result.files?.xgm ? '/XGM' : ''} を生成しました。`,
      },
      ...(result.diagnostics || []),
    ],
  };
}

async function exportSong({ plugin, api, logger, state, els }) {
  setBusy(state, els, 'VGM/XGM を書き出しています...');
  const validation = await validateViaMain(plugin, api, state, els, { render: false });
  const hasErrors = (validation?.diagnostics || []).some((diag) => diag.level === 'error');
  if (hasErrors) {
    state.status = 'エラーがあるため export を中止しました。';
    renderAll(state, els);
    return;
  }
  const result = await api.plugins.invokeHook(plugin.id, 'exportMusic', {
    song: state.song,
    symbol: state.song.symbol,
    outputs: { vgm: true, xgm: true, registerAsset: true },
  });
  if (!result?.ok) {
    state.status = result?.error || 'export に失敗しました。';
    renderAll(state, els);
    return;
  }
  state.diagnostics = [...(result.diagnostics || []), ...(result.warnings || []).map((message) => ({ level: 'warn', code: 'xgm-export', message }))];
  if (result.asset) {
    await registerXgm2Asset(api, result.asset, logger, state);
  }
  state.status = `export 完了: ${result.files?.vgm || ''}${result.files?.xgm ? ` / ${result.files.xgm}` : ''}`;
  renderAll(state, els);
}

async function registerXgm2Asset(api, asset, logger, state) {
  const defs = await api.electronAPI.listResDefinitions();
  const entries = (defs?.files || []).flatMap((file) => file.entries || []);
  if (entries.some((entry) => entry.name === asset.name)) {
    state.diagnostics.push({ level: 'info', code: 'asset-exists', message: `${asset.name} は既に resources.res に登録済みです。` });
    return;
  }
  const add = await api.electronAPI.addResEntry({
    file: 'resources.res',
    entry: asset,
  });
  if (!add?.ok) {
    logger.warn(`XGM2 asset 登録失敗: ${add?.error || 'unknown'}`);
    state.diagnostics.push({ level: 'warn', code: 'asset-register-failed', message: add?.error || 'XGM2 asset 登録に失敗しました。' });
  }
}

async function validateViaMain(plugin, api, state, els, options = {}) {
  const result = await api.plugins.invokeHook(plugin.id, 'validateSong', { song: state.song });
  state.diagnostics = result?.diagnostics || result?.result?.diagnostics || [];
  state.status = state.diagnostics.length ? '検証が完了しました。診断を確認してください。' : '検証 OK です。';
  if (options.render !== false) renderAll(state, els);
  return { ok: true, diagnostics: state.diagnostics };
}

function pushUndo(state) {
  state.undo.push(JSON.stringify(state.song));
  if (state.undo.length > 50) state.undo.shift();
  state.redo = [];
}

function restoreHistory(state, els, direction) {
  const from = direction === 'undo' ? state.undo : state.redo;
  const to = direction === 'undo' ? state.redo : state.undo;
  const snapshot = from.pop();
  if (!snapshot) return;
  to.push(JSON.stringify(state.song));
  state.song = normalizeSong(JSON.parse(snapshot));
  state.selectedPattern = state.song.order[0] || 0;
  state.status = direction === 'undo' ? 'Undo' : 'Redo';
  renderAll(state, els);
}

function setBusy(state, els, message) {
  state.status = message;
  renderStatus(state, els);
}

function playPreview(song, patternId) {
  stopPreview();
  audioContext = audioContext || new AudioContext();
  const pattern = song.patterns.find((entry) => entry.id === patternId) || song.patterns[0];
  const secondsPerRow = Math.max(0.04, (60 / (Number(song.tempo) || 150)) / 4);
  pattern.rows.forEach((row, rowIndex) => {
    Object.entries(row.cells || {}).forEach(([channelId, cell]) => {
      const midi = cell.midiNote ?? noteNameToMidi(cell.note);
      if (midi == null && channelId !== 'NOISE') return;
      const timer = window.setTimeout(() => {
        playTone(channelId, midi || 48, secondsPerRow * 0.85, Number(cell.volume) || 10);
      }, rowIndex * secondsPerRow * 1000);
      previewTimers.push(timer);
    });
  });
}

function stopPreview() {
  previewTimers.forEach((timer) => window.clearTimeout(timer));
  previewTimers = [];
}

function playTone(channelId, midi, duration, volume) {
  if (!audioContext) return;
  const gain = audioContext.createGain();
  gain.gain.value = Math.max(0.02, Math.min(0.3, volume / 60));
  gain.connect(audioContext.destination);
  if (channelId === 'NOISE') {
    const buffer = audioContext.createBuffer(1, Math.max(1, audioContext.sampleRate * duration), audioContext.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(gain);
    source.start();
    source.stop(audioContext.currentTime + duration);
    return;
  }
  const osc = audioContext.createOscillator();
  osc.type = channelId.startsWith('FM') ? 'sine' : 'square';
  osc.frequency.value = 440 * (2 ** ((midi - 69) / 12));
  osc.connect(gain);
  osc.start();
  osc.stop(audioContext.currentTime + duration);
}

function noteNameToMidi(noteName) {
  const match = String(noteName || '').trim().match(/^([A-G])(#?)(-?\d+)$/i);
  if (!match) return null;
  const name = `${match[1].toUpperCase()}${match[2] || ''}`;
  const index = NOTE_NAMES.indexOf(name);
  if (index < 0) return null;
  return (Number(match[3]) + 1) * 12 + index;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
