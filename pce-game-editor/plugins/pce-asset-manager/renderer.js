export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  root.innerHTML = `
    <div class="asset-plugin-layout">
      <aside class="asset-list-panel">
        <div class="pane-header">
          <h2>PCE Assets</h2>
          <button class="mini-btn" data-action="refresh" type="button">更新</button>
        </div>
        <div class="asset-list" data-role="list"></div>
      </aside>
      <section class="asset-detail-panel">
        <div class="asset-toolbar">
          <button class="mini-btn" data-action="new-image" type="button">画像</button>
          <button class="mini-btn" data-action="new-sound" type="button">PSG</button>
          <button class="mini-btn" data-action="save" type="button" disabled>保存</button>
          <button class="mini-btn" data-action="delete" type="button" disabled>削除</button>
        </div>
        <div class="asset-form">
          <label>ID</label><input class="input" data-field="id" />
          <label>Type</label>
          <select class="select" data-field="type">
            <option value="image">image</option>
            <option value="psg-sequence">psg-sequence</option>
            <option value="tileset">tileset</option>
            <option value="tilemap">tilemap</option>
            <option value="palette">palette</option>
          </select>
          <label>Name</label><input class="input" data-field="name" />
          <label>Source</label><input class="input" data-field="source" />
          <label>Options JSON</label><textarea class="input" data-field="options" rows="8"></textarea>
        </div>
        <pre class="asset-preview" data-role="preview">アセットを選択してください</pre>
      </section>
    </div>
  `;

  const list = root.querySelector('[data-role="list"]');
  const preview = root.querySelector('[data-role="preview"]');
  const fields = {
    id: root.querySelector('[data-field="id"]'),
    type: root.querySelector('[data-field="type"]'),
    name: root.querySelector('[data-field="name"]'),
    source: root.querySelector('[data-field="source"]'),
    options: root.querySelector('[data-field="options"]'),
  };
  const btnSave = root.querySelector('[data-action="save"]');
  const btnDelete = root.querySelector('[data-action="delete"]');
  let assets = [];
  let selectedId = '';

  function currentAssetFromForm() {
    let options = {};
    try {
      options = fields.options.value.trim() ? JSON.parse(fields.options.value) : {};
    } catch (err) {
      throw new Error(`Options JSON が不正です: ${err.message}`);
    }
    return {
      id: fields.id.value.trim(),
      type: fields.type.value,
      name: fields.name.value.trim() || fields.id.value.trim(),
      source: fields.source.value.trim(),
      options,
    };
  }

  function setForm(asset) {
    selectedId = asset?.id || '';
    fields.id.value = asset?.id || '';
    fields.type.value = asset?.type || 'image';
    fields.name.value = asset?.name || '';
    fields.source.value = asset?.source || '';
    fields.options.value = JSON.stringify(asset?.options || {}, null, 2);
    btnSave.disabled = false;
    btnDelete.disabled = !selectedId;
    preview.textContent = selectedId ? JSON.stringify(asset, null, 2) : '新規アセット';
    renderList();
  }

  function renderList() {
    list.innerHTML = assets.map((asset) => `
      <button class="asset-item ${asset.id === selectedId ? 'active' : ''}" data-id="${asset.id}" type="button">
        ${asset.name || asset.id}
        <small>${asset.type} / ${asset.source || '(generated)'}</small>
      </button>
    `).join('');
    list.querySelectorAll('.asset-item').forEach((button) => {
      button.addEventListener('click', () => setForm(assets.find((asset) => asset.id === button.dataset.id)));
    });
  }

  async function reload() {
    const result = await api.electronAPI.listAssets();
    if (!result.ok) {
      list.innerHTML = `<p class="meta">${result.error}</p>`;
      return;
    }
    assets = result.assets || [];
    if (selectedId) {
      const selected = assets.find((asset) => asset.id === selectedId);
      if (selected) setForm(selected);
      else selectedId = '';
    }
    renderList();
  }

  async function save() {
    try {
      const asset = currentAssetFromForm();
      const result = await api.electronAPI.upsertAsset(asset);
      if (!result.ok) throw new Error(result.error);
      selectedId = asset.id;
      logger.info(`保存しました: ${asset.id}`);
      await reload();
    } catch (err) {
      logger.error(err.message || err);
    }
  }

  async function remove() {
    if (!selectedId || !confirm(`${selectedId} を削除しますか？`)) return;
    const result = await api.electronAPI.deleteAsset(selectedId);
    if (!result.ok) {
      logger.error(result.error);
      return;
    }
    selectedId = '';
    setForm(null);
    await reload();
  }

  root.querySelector('[data-action="refresh"]').addEventListener('click', reload);
  root.querySelector('[data-action="new-image"]').addEventListener('click', () => setForm({
    id: `image_${Date.now()}`,
    type: 'image',
    name: 'Image',
    source: 'assets/images/sample.pceimg.json',
    options: { x: 2, y: 10 },
  }));
  root.querySelector('[data-action="new-sound"]').addEventListener('click', () => setForm({
    id: `beep_${Date.now()}`,
    type: 'psg-sequence',
    name: 'Beep',
    source: 'assets/sound/beep.json',
    options: { period: 512 },
  }));
  btnSave.addEventListener('click', save);
  btnDelete.addEventListener('click', remove);

  registerCapability('asset-manager', { pluginId: plugin.id, reload });
  registerCapability('asset-type-provider', {
    getTypeInfo(file = {}) {
      const ext = String(file.ext || '').toLowerCase();
      if (['.png', '.json', '.pceimg'].includes(ext)) {
        return { initialType: 'image', allowedTypes: ['image'], defaultSubdir: 'assets/images' };
      }
      if (['.wav', '.vgm', '.json'].includes(ext)) {
        return { initialType: 'psg-sequence', allowedTypes: ['psg-sequence'], defaultSubdir: 'assets/sound' };
      }
      return null;
    },
  });
  void reload();
  return { deactivate() {} };
}
