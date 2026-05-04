export function activatePlugin({ plugin, api, logger, registerCapability }) {
  let modal = null;

  function normalizeSymbol(value) {
    const raw = String(value || 'midi_bgm')
      .replace(/\.[^.]+$/, '')
      .replace(/[^A-Za-z0-9_]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .toLowerCase();
    return /^[A-Za-z_]/.test(raw) ? raw : `bgm_${raw || 'midi'}`;
  }

  async function convertMidiMusic(payload = {}) {
    const result = await api.plugins.invokeHook(plugin.id, 'convertMidiMusic', {
      ...payload,
      outputs: {
        vgm: payload.outputs?.vgm !== false,
        xgm: payload.outputs?.xgm !== false,
        registerAsset: Boolean(payload.outputs?.registerAsset),
      },
    });
    const body = result?.result || result;
    return body || { ok: false, error: 'MIDI 変換に失敗しました。' };
  }

  async function pickMidiFile() {
    const result = await api.electronAPI.pickFile({
      properties: ['openFile'],
      filters: [{ name: 'MIDI', extensions: ['mid', 'midi'] }],
    });
    if (result?.canceled || !result?.sourcePath) return '';
    return result.sourcePath;
  }

  async function registerAsset(asset, statusEl) {
    if (!asset) return;
    const defs = await api.electronAPI.listResDefinitions();
    const entries = (defs?.files || []).flatMap((file) => file.entries || []);
    if (entries.some((entry) => entry.name === asset.name)) {
      statusEl.textContent = `${asset.name} は既に resources.res に登録済みです。`;
      return;
    }
    const add = await api.electronAPI.addResEntry({
      file: 'resources.res',
      entry: asset,
    });
    statusEl.textContent = add?.ok
      ? `${asset.name} を XGM2 アセットとして登録しました。`
      : (add?.error || 'XGM2 アセット登録に失敗しました。');
  }

  function createModal() {
    if (modal) return modal;
    modal = api.createModal({
      id: `${plugin.id}-modal`,
      html: `
        <div class="midi-converter-modal">
          <div class="midi-converter-head">
            <h2>MIDI Converter</h2>
            <button type="button" class="midi-converter-icon" data-action="close" title="Close" aria-label="Close">x</button>
          </div>
          <div class="midi-converter-grid">
            <label>
              MIDI
              <span class="midi-converter-file" data-role="source">未選択</span>
            </label>
            <button type="button" class="midi-converter-btn" data-action="pick-midi">Select</button>
            <label>
              Symbol
              <input type="text" data-role="symbol" value="midi_bgm">
            </label>
            <div class="midi-converter-options">
              <label><input type="checkbox" data-role="vgm" checked> VGM</label>
              <label><input type="checkbox" data-role="xgm" checked> XGM</label>
              <label><input type="checkbox" data-role="asset" checked> XGM2 asset</label>
            </div>
          </div>
          <div class="midi-converter-actions">
            <button type="button" class="midi-converter-btn primary" data-action="convert">Convert</button>
          </div>
          <pre class="midi-converter-status" data-role="status"></pre>
        </div>
      `,
    });

    const root = modal.panel || modal.modal || null;
    let sourcePath = '';
    const $ = (selector) => root?.querySelector(selector);
    $('[data-action="close"]')?.addEventListener('click', () => modal.close());
    $('[data-action="pick-midi"]')?.addEventListener('click', async () => {
      sourcePath = await pickMidiFile();
      if (!sourcePath) return;
      $('[data-role="source"]').textContent = sourcePath;
      $('[data-role="symbol"]').value = normalizeSymbol(sourcePath.split(/[\\/]/).pop() || 'midi_bgm');
    });
    $('[data-action="convert"]')?.addEventListener('click', async () => {
      const status = $('[data-role="status"]');
      if (!sourcePath) {
        status.textContent = 'MIDI ファイルを選択してください。';
        return;
      }
      status.textContent = '変換中...';
      const result = await convertMidiMusic({
        sourcePath,
        symbol: normalizeSymbol($('[data-role="symbol"]').value),
        outputs: {
          vgm: $('[data-role="vgm"]').checked,
          xgm: $('[data-role="xgm"]').checked,
          registerAsset: $('[data-role="asset"]').checked,
        },
      });
      if (!result?.ok) {
        status.textContent = result?.error || '変換に失敗しました。';
        return;
      }
      status.textContent = [
        `VGM: ${result.files?.vgm || 'なし'}`,
        `XGM: ${result.files?.xgm || 'なし'}`,
        ...(result.warnings || []),
      ].filter(Boolean).join('\n');
      if ($('[data-role="asset"]').checked) await registerAsset(result.asset, status);
    });
    return modal;
  }

  function openMidiConvertModal(pending = {}) {
    const instance = createModal();
    instance.open();
    return pending;
  }

  registerCapability('midi-convert-ui', {
    convertMidiMusic,
    openMidiConvertModal,
  });

  logger.debug('midi-converter renderer activated');
  return {
    deactivate() {
      modal?.destroy?.();
      modal = null;
    },
  };
}
