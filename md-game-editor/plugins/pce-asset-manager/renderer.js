const IMAGE_EXTS = ['.png', '.bmp'];
const SPRITE_CELL_SIZES = ['16x16', '16x32', '16x64', '32x16', '32x32', '32x64'];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}

function extname(filePath = '') {
  const match = String(filePath).toLowerCase().match(/(\.[^.\\/]+)$/);
  return match ? match[1] : '';
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function imageKind(asset = {}) {
  return asset.type === 'sprite' || asset.options?.kind === 'sprite' ? 'sprite' : 'background';
}

function isImageAsset(asset = {}) {
  return asset.type === 'image' || asset.type === 'sprite';
}

function generatedInfo(asset = {}) {
  return asset.data?.generated || {};
}

function dataUrlToPng(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth || image.width;
      canvas.height = image.naturalHeight || image.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0);
      resolve(canvas.toDataURL('image/png'));
    };
    image.onerror = () => reject(new Error('画像をPNGへ変換できませんでした'));
    image.src = dataUrl;
  });
}

export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  root.innerHTML = `
    <div class="pce-assets-layout assets-layout" data-plugin-root="${esc(plugin.id)}">
      <section class="asset-list-panel">
        <div class="asset-list-header">
          <div>
            <h2>PCE Assets</h2>
            <p class="pce-assets-subtitle">BG / Sprite / PSG を PC Engine 向けに管理します</p>
          </div>
          <div class="asset-list-header-actions">
            <button class="btn-primary" data-action="import" type="button">画像を取り込み</button>
            <button class="btn-sm" data-action="new-psg" type="button">PSG</button>
            <button class="icon-btn-xs" data-action="refresh" type="button" title="更新" aria-label="更新">R</button>
          </div>
        </div>

        <div class="assets-toolbar">
          <label class="assets-toolbar-item assets-search-item">
            検索
            <input class="form-input" data-role="search" placeholder="name / id / source" />
          </label>
          <label class="assets-toolbar-item">
            種別
            <select class="form-select" data-role="type-filter">
              <option value="all">すべて</option>
              <option value="image">BG image</option>
              <option value="sprite">Sprite sheet</option>
              <option value="psg-sequence">PSG</option>
            </select>
          </label>
        </div>

        <div class="asset-table-wrap">
          <table class="asset-table">
            <thead>
              <tr>
                <th class="asset-drag-th"></th>
                <th>Type</th>
                <th>Name</th>
                <th>Source</th>
                <th>Tiles</th>
                <th>Warn</th>
                <th class="asset-actions-cell"></th>
              </tr>
            </thead>
            <tbody data-role="asset-rows">
              <tr class="asset-row-empty"><td colspan="7">読み込み中...</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="asset-preview-resizer" role="separator" aria-orientation="vertical" data-role="resizer"></div>

      <aside class="asset-preview-panel">
        <div id="pceAssetEditorPanel" class="pce-assets-editor">
          <section class="accordion-section">
            <button class="accordion-header" type="button" aria-expanded="true" data-accordion="settings">
              <span class="accordion-title">設定</span><span class="accordion-chevron">⌃</span>
            </button>
            <div class="accordion-body" data-accordion-body="settings">
              <form class="asset-edit-form pce-assets-form" data-role="detail-form">
                <div class="asset-no-selection-hint" data-role="no-selection">アセットを選択してください</div>
                <div class="asset-edit-grid" data-role="detail-fields" hidden>
                  <label class="form-label">ID</label>
                  <input class="form-input form-input-mono" data-field="id" />
                  <label class="form-label">Type</label>
                  <select class="form-select" data-field="type">
                    <option value="image">BG image</option>
                    <option value="sprite">Sprite sheet</option>
                    <option value="psg-sequence">PSG sequence</option>
                    <option value="tileset">Tileset</option>
                    <option value="tilemap">Tilemap</option>
                    <option value="palette">Palette</option>
                  </select>
                  <label class="form-label">Name</label>
                  <input class="form-input" data-field="name" />
                  <label class="form-label">Source</label>
                  <input class="form-input form-input-mono" data-field="source" />
                  <label class="form-label">Palette bank</label>
                  <input class="form-input" data-field="paletteBank" type="number" min="0" max="15" />
                  <label class="form-label">Tile base</label>
                  <input class="form-input" data-field="tileBase" type="number" min="0" max="2047" />
                  <label class="form-label">Map base</label>
                  <input class="form-input" data-field="mapBase" type="number" min="0" max="2047" />
                  <label class="form-label">X / Y</label>
                  <div class="pce-assets-inline-fields">
                    <input class="form-input" data-field="x" type="number" min="0" max="255" />
                    <input class="form-input" data-field="y" type="number" min="0" max="255" />
                  </div>
                  <label class="form-label">Width / Height</label>
                  <div class="pce-assets-inline-fields">
                    <input class="form-input" data-field="width" type="number" min="0" max="1024" />
                    <input class="form-input" data-field="height" type="number" min="0" max="1024" />
                  </div>
                  <label class="form-label">Cell</label>
                  <select class="form-select" data-field="cellSize">
                    ${SPRITE_CELL_SIZES.map((size) => `<option value="${size}">${size}</option>`).join('')}
                  </select>
                  <label class="form-label">Transparent</label>
                  <input class="form-input" data-field="transparentIndex" type="number" min="0" max="15" />
                  <label class="form-label">PSG period</label>
                  <input class="form-input" data-field="period" type="number" min="1" max="4095" />
                </div>
                <div class="form-actions-inline">
                  <button class="btn-primary" data-action="save" type="submit" disabled>保存</button>
                  <button class="btn-sm" data-action="delete" type="button" disabled>削除</button>
                </div>
                <div class="form-error" data-role="form-error"></div>
              </form>
            </div>
          </section>

          <section class="accordion-section">
            <button class="accordion-header" type="button" aria-expanded="true" data-accordion="preview">
              <span class="accordion-title">プレビュー</span><span class="accordion-chevron">⌃</span>
            </button>
            <div class="accordion-body" data-accordion-body="preview">
              <div class="image-preview-frame pce-assets-preview-frame">
                <img data-role="source-preview" alt="PCE asset preview" hidden />
                <div class="inline-no-preview" data-role="no-preview">プレビューできる画像がありません</div>
              </div>
              <div class="inline-preview-info" data-role="preview-info"></div>
            </div>
          </section>

          <section class="accordion-section">
            <button class="accordion-header" type="button" aria-expanded="true" data-accordion="generated">
              <span class="accordion-title">PCE 変換結果</span><span class="accordion-chevron">⌃</span>
            </button>
            <div class="accordion-body" data-accordion-body="generated">
              <div class="pce-assets-stats" data-role="generated-stats"></div>
              <div class="image-preview-palette" data-role="palette"></div>
              <div class="pce-assets-generated-files" data-role="generated-files"></div>
            </div>
          </section>

          <section class="accordion-section">
            <button class="accordion-header" type="button" aria-expanded="true" data-accordion="diagnostics">
              <span class="accordion-title">警告 / 診断</span><span class="accordion-chevron">⌃</span>
            </button>
            <div class="accordion-body" data-accordion-body="diagnostics">
              <div data-role="diagnostics"></div>
            </div>
          </section>
        </div>
      </aside>
    </div>
  `;

  const rowsEl = root.querySelector('[data-role="asset-rows"]');
  const searchEl = root.querySelector('[data-role="search"]');
  const typeFilterEl = root.querySelector('[data-role="type-filter"]');
  const formEl = root.querySelector('[data-role="detail-form"]');
  const detailFieldsEl = root.querySelector('[data-role="detail-fields"]');
  const noSelectionEl = root.querySelector('[data-role="no-selection"]');
  const formErrorEl = root.querySelector('[data-role="form-error"]');
  const previewImgEl = root.querySelector('[data-role="source-preview"]');
  const noPreviewEl = root.querySelector('[data-role="no-preview"]');
  const previewInfoEl = root.querySelector('[data-role="preview-info"]');
  const generatedStatsEl = root.querySelector('[data-role="generated-stats"]');
  const generatedFilesEl = root.querySelector('[data-role="generated-files"]');
  const paletteEl = root.querySelector('[data-role="palette"]');
  const diagnosticsEl = root.querySelector('[data-role="diagnostics"]');
  const saveButton = root.querySelector('[data-action="save"]');
  const deleteButton = root.querySelector('[data-action="delete"]');
  const fields = {
    id: root.querySelector('[data-field="id"]'),
    type: root.querySelector('[data-field="type"]'),
    name: root.querySelector('[data-field="name"]'),
    source: root.querySelector('[data-field="source"]'),
    paletteBank: root.querySelector('[data-field="paletteBank"]'),
    tileBase: root.querySelector('[data-field="tileBase"]'),
    mapBase: root.querySelector('[data-field="mapBase"]'),
    x: root.querySelector('[data-field="x"]'),
    y: root.querySelector('[data-field="y"]'),
    width: root.querySelector('[data-field="width"]'),
    height: root.querySelector('[data-field="height"]'),
    cellSize: root.querySelector('[data-field="cellSize"]'),
    transparentIndex: root.querySelector('[data-field="transparentIndex"]'),
    period: root.querySelector('[data-field="period"]'),
  };

  let assets = [];
  let selectedId = '';
  let draggedId = '';

  function selectedAsset() {
    return assets.find((asset) => asset.id === selectedId) || null;
  }

  function typeLabel(asset = {}) {
    if (asset.type === 'image') return 'BG';
    if (asset.type === 'sprite') return 'SPR';
    if (asset.type === 'psg-sequence') return 'PSG';
    return String(asset.type || '').toUpperCase();
  }

  function filteredAssets() {
    const query = searchEl.value.trim().toLowerCase();
    const filter = typeFilterEl.value;
    return assets.filter((asset) => {
      if (filter !== 'all' && asset.type !== filter) return false;
      if (!query) return true;
      return [asset.id, asset.name, asset.source, asset.type].some((value) => String(value || '').toLowerCase().includes(query));
    });
  }

  function renderRows() {
    const visible = filteredAssets();
    if (!visible.length) {
      rowsEl.innerHTML = '<tr class="asset-row-empty"><td colspan="7">アセットがありません</td></tr>';
      return;
    }
    rowsEl.innerHTML = visible.map((asset) => {
      const generated = generatedInfo(asset);
      const warnings = [...(generated.warnings || []), asset.pathError].filter(Boolean);
      const tileText = isImageAsset(asset)
        ? `${generated.tileCount || 0} / ${generated.paletteCount || 0} pal`
        : asset.type === 'psg-sequence' ? `${asset.options?.period || 512} Hz` : '-';
      return `
        <tr class="asset-row ${asset.id === selectedId ? 'active' : ''}" data-id="${esc(asset.id)}" draggable="true">
          <td class="asset-drag-cell"><span class="drag-handle" title="並び替え">&#8942;&#8942;</span></td>
          <td><span class="asset-type-pill type-${esc(asset.type)}">${esc(typeLabel(asset))}</span></td>
          <td><strong>${esc(asset.name || asset.id)}</strong><div class="pce-assets-muted">${esc(asset.id)}</div></td>
          <td class="asset-path-cell">${esc(asset.source || '(generated)')}</td>
          <td>${esc(tileText)}</td>
          <td>${warnings.length ? `<span class="asset-warning">${warnings.length}</span>` : '<span class="pce-assets-muted">0</span>'}</td>
          <td class="asset-actions-cell"><button class="icon-btn-xs" type="button" data-row-delete="${esc(asset.id)}" title="削除" aria-label="削除">Del</button></td>
        </tr>
      `;
    }).join('');
    rowsEl.querySelectorAll('.asset-row').forEach((row) => {
      row.addEventListener('click', (event) => {
        if (event.target?.closest?.('[data-row-delete]')) return;
        selectAsset(row.dataset.id);
      });
      row.addEventListener('dragstart', (event) => {
        draggedId = row.dataset.id || '';
        row.classList.add('drag-source');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', draggedId);
      });
      row.addEventListener('dragover', (event) => {
        if (!draggedId || draggedId === row.dataset.id) return;
        event.preventDefault();
        row.classList.add('drag-over');
      });
      row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
      row.addEventListener('drop', async (event) => {
        event.preventDefault();
        row.classList.remove('drag-over');
        await moveAsset(draggedId, row.dataset.id);
      });
      row.addEventListener('dragend', () => {
        row.classList.remove('drag-source');
        rowsEl.querySelectorAll('.drag-over').forEach((entry) => entry.classList.remove('drag-over'));
        draggedId = '';
      });
    });
    rowsEl.querySelectorAll('[data-row-delete]').forEach((button) => {
      button.addEventListener('click', () => deleteAsset(button.dataset.rowDelete));
    });
  }

  function setFieldVisibility(asset) {
    const isImage = isImageAsset(asset);
    const isSprite = imageKind(asset) === 'sprite';
    const isPsg = asset?.type === 'psg-sequence';
    ['paletteBank', 'tileBase', 'mapBase', 'x', 'y', 'width', 'height', 'cellSize', 'transparentIndex'].forEach((key) => {
      const input = fields[key];
      const label = input?.closest?.('.asset-edit-grid') ? null : null;
      if (!input) return;
      const labelEl = input.parentElement?.classList.contains('pce-assets-inline-fields')
        ? input.parentElement.previousElementSibling
        : input.previousElementSibling;
      const container = input.parentElement?.classList.contains('pce-assets-inline-fields') ? input.parentElement : input;
      const show = isImage && (key !== 'cellSize' || isSprite) && (key !== 'mapBase' || !isSprite);
      container.hidden = !show;
      if (labelEl) labelEl.hidden = !show;
    });
    fields.period.hidden = !isPsg;
    fields.period.previousElementSibling.hidden = !isPsg;
  }

  function fillForm(asset) {
    const options = asset?.options || {};
    noSelectionEl.hidden = Boolean(asset);
    detailFieldsEl.hidden = !asset;
    saveButton.disabled = !asset;
    deleteButton.disabled = !asset;
    formErrorEl.textContent = '';
    if (!asset) {
      previewImgEl.hidden = true;
      noPreviewEl.hidden = false;
      previewInfoEl.textContent = '';
      generatedStatsEl.innerHTML = '';
      generatedFilesEl.innerHTML = '';
      paletteEl.innerHTML = '';
      diagnosticsEl.innerHTML = '<p class="asset-no-selection-hint">診断対象がありません</p>';
      return;
    }
    fields.id.value = asset.id || '';
    fields.type.value = asset.type || 'image';
    fields.name.value = asset.name || '';
    fields.source.value = asset.source || '';
    fields.paletteBank.value = options.paletteBank ?? 0;
    fields.tileBase.value = options.tileBase ?? (asset.type === 'sprite' ? 384 : 32);
    fields.mapBase.value = options.mapBase ?? 0;
    fields.x.value = options.x ?? 0;
    fields.y.value = options.y ?? 0;
    fields.width.value = options.width ?? 0;
    fields.height.value = options.height ?? 0;
    fields.cellSize.value = `${options.cellWidth || 16}x${options.cellHeight || 16}`;
    fields.transparentIndex.value = options.transparentIndex ?? 0;
    fields.period.value = options.period ?? 512;
    setFieldVisibility(asset);
    renderGenerated(asset);
    void loadPreview(asset);
  }

  function collectFormAsset() {
    const current = selectedAsset() || {};
    const type = fields.type.value;
    const [cellWidth, cellHeight] = String(fields.cellSize.value || '16x16').split('x').map((value) => asNumber(value, 16));
    const options = type === 'psg-sequence'
      ? { ...(current.options || {}), period: asNumber(fields.period.value, 512) }
      : {
          ...(current.options || {}),
          kind: type === 'sprite' ? 'sprite' : 'background',
          paletteBank: asNumber(fields.paletteBank.value, 0),
          tileBase: asNumber(fields.tileBase.value, type === 'sprite' ? 384 : 32),
          mapBase: asNumber(fields.mapBase.value, 0),
          x: asNumber(fields.x.value, 0),
          y: asNumber(fields.y.value, 0),
          width: asNumber(fields.width.value, 0),
          height: asNumber(fields.height.value, 0),
          cellWidth,
          cellHeight,
          transparentIndex: asNumber(fields.transparentIndex.value, 0),
        };
    return {
      ...current,
      id: fields.id.value.trim(),
      type,
      name: fields.name.value.trim() || fields.id.value.trim(),
      source: fields.source.value.trim(),
      options,
      data: current.data || {},
    };
  }

  async function loadPreview(asset) {
    previewImgEl.hidden = true;
    noPreviewEl.hidden = false;
    previewInfoEl.textContent = '';
    if (!asset?.source || !IMAGE_EXTS.includes(extname(asset.source))) return;
    const result = await api.electronAPI.previewAssetSource(asset.source);
    if (!result?.ok || !result.dataUrl) {
      previewInfoEl.textContent = result?.error || 'プレビューを取得できませんでした';
      return;
    }
    previewImgEl.src = result.dataUrl;
    previewImgEl.hidden = false;
    noPreviewEl.hidden = true;
    previewInfoEl.textContent = `${result.mime || ''} / ${Math.round((result.size || 0) / 1024)} KB`;
  }

  function renderGenerated(asset) {
    const generated = generatedInfo(asset);
    generatedStatsEl.innerHTML = `
      <div class="pce-assets-stat"><span>Tile / Pattern</span><strong>${esc(generated.tileCount || 0)}</strong></div>
      <div class="pce-assets-stat"><span>Palette</span><strong>${esc(generated.paletteCount || 0)}</strong></div>
      <div class="pce-assets-stat"><span>VRAM bytes</span><strong>${esc(generated.vramBytes || 0)}</strong></div>
    `;
    const files = [
      ['palette', generated.paletteFile],
      [asset.type === 'sprite' ? 'patterns' : 'tiles', generated.tilesFile],
      ['map', generated.mapFile],
      ['preview', generated.previewFile],
    ].filter((entry) => entry[1]);
    generatedFilesEl.innerHTML = files.length
      ? files.map(([label, file]) => `<div><span>${esc(label)}</span><code>${esc(file)}</code></div>`).join('')
      : '<p class="asset-no-selection-hint">まだ変換結果がありません</p>';
    const colors = generated.paletteColors || [];
    paletteEl.innerHTML = colors.length
      ? colors.slice(0, 64).map((color, index) => `<span class="palette-swatch ${index % 16 === 0 ? 'is-transparent' : ''}" style="background:${esc(color)}" title="${index}: ${esc(color)}"></span>`).join('')
      : Array.from({ length: 16 }, (_unused, index) => `<span class="palette-swatch is-empty ${index === 0 ? 'is-transparent' : ''}" title="${index}"></span>`).join('');
    const warnings = [...(generated.warnings || []), asset.pathError].filter(Boolean);
    diagnosticsEl.innerHTML = warnings.length
      ? warnings.map((warning) => `<div class="asset-warning">${esc(warning)}</div>`).join('')
      : '<p class="pce-assets-muted">警告はありません</p>';
  }

  function selectAsset(id) {
    selectedId = id || '';
    fillForm(selectedAsset());
    renderRows();
  }

  async function reload() {
    const result = await api.electronAPI.listAssets();
    if (!result?.ok) {
      rowsEl.innerHTML = `<tr class="asset-row-empty"><td colspan="7">${esc(result?.error || 'PCE assets を読み込めません')}</td></tr>`;
      return;
    }
    assets = result.assets || [];
    if (selectedId && !assets.some((asset) => asset.id === selectedId)) selectedId = '';
    renderRows();
    fillForm(selectedAsset());
  }

  async function saveSelected(event) {
    event.preventDefault();
    try {
      const asset = collectFormAsset();
      const result = await api.electronAPI.upsertAsset(asset);
      if (!result?.ok) throw new Error(result?.error || '保存に失敗しました');
      selectedId = asset.id;
      logger.info(`PCE asset saved: ${asset.id}`);
      await reload();
    } catch (err) {
      formErrorEl.textContent = err.message || String(err);
    }
  }

  function askDelete(assetId) {
    return new Promise((resolve) => {
      const modal = api.createModal({
        id: `${plugin.id}-delete-modal-${Date.now()}`,
        panelClassName: 'app-panel app-panel-sm',
        html: `
          <div class="page-header modal-header">
            <h2>アセット削除</h2>
            <button class="icon-btn" type="button" data-decision="cancel">✕</button>
          </div>
          <div class="settings-form compact-form pce-assets-modal">
            <p><code>${esc(assetId)}</code> を削除します。</p>
            <div class="form-actions-inline modal-actions-end">
              <button class="btn-sm" type="button" data-decision="cancel">キャンセル</button>
              <button class="btn-primary" type="button" data-decision="delete">削除</button>
            </div>
          </div>
        `,
      });
      modal.panel.querySelectorAll('[data-decision]').forEach((button) => {
        button.addEventListener('click', () => {
          const decision = button.dataset.decision;
          modal.close();
          modal.destroy?.();
          resolve(decision === 'delete');
        }, { once: true });
      });
      modal.open();
    });
  }

  async function deleteAsset(assetId = selectedId) {
    if (!assetId) return;
    if (!(await askDelete(assetId))) return;
    const result = await api.electronAPI.deleteAsset(assetId);
    if (!result?.ok) {
      formErrorEl.textContent = result?.error || '削除に失敗しました';
      return;
    }
    if (selectedId === assetId) selectedId = '';
    await reload();
  }

  async function moveAsset(sourceId, targetId) {
    if (!sourceId || !targetId || sourceId === targetId) return;
    const ids = assets.map((asset) => asset.id);
    const from = ids.indexOf(sourceId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    const result = await api.electronAPI.reorderAssets(ids);
    if (!result?.ok) {
      formErrorEl.textContent = result?.error || '並び替えに失敗しました';
      return;
    }
    assets = result.assets || assets;
    renderRows();
  }

  async function openImportWizard(defaultKind = 'background', importFile = null) {
    return new Promise((resolve) => {
      const modal = api.createModal({
        id: `${plugin.id}-import-modal-${Date.now()}`,
        panelClassName: 'app-panel pce-assets-import-panel',
        html: `
          <div class="page-header modal-header">
            <h2>PCE 画像取り込み</h2>
            <button class="icon-btn" type="button" data-import-cancel>✕</button>
          </div>
          <form class="settings-form compact-form pce-assets-import-form">
            <div class="pce-assets-import-grid">
              <label class="form-group">
                <span class="form-label">種別</span>
                <select class="form-select" name="kind">
                  <option value="background" ${defaultKind !== 'sprite' ? 'selected' : ''}>BG image</option>
                  <option value="sprite" ${defaultKind === 'sprite' ? 'selected' : ''}>Sprite sheet</option>
                </select>
              </label>
              <label class="form-group">
                <span class="form-label">ID</span>
                <input class="form-input form-input-mono" name="id" />
              </label>
              <label class="form-group">
                <span class="form-label">Name</span>
                <input class="form-input" name="name" />
              </label>
              <label class="form-group">
                <span class="form-label">Palette bank</span>
                <input class="form-input" name="paletteBank" type="number" min="0" max="15" value="0" />
              </label>
              <label class="form-group">
                <span class="form-label">Tile base</span>
                <input class="form-input" name="tileBase" type="number" min="0" max="2047" value="${defaultKind === 'sprite' ? '384' : '32'}" />
              </label>
              <label class="form-group">
                <span class="form-label">Map base</span>
                <input class="form-input" name="mapBase" type="number" min="0" max="2047" value="0" />
              </label>
              <label class="form-group">
                <span class="form-label">Cell size</span>
                <select class="form-select" name="cellSize">
                  ${SPRITE_CELL_SIZES.map((size) => `<option value="${size}">${size}</option>`).join('')}
                </select>
              </label>
              <label class="form-group">
                <span class="form-label">Transparent index</span>
                <input class="form-input" name="transparentIndex" type="number" min="0" max="15" value="0" />
              </label>
            </div>
            <div class="pce-assets-import-source">
              <button class="btn-sm" type="button" data-pick-image>画像を選択</button>
              <code data-source-label>未選択</code>
            </div>
            <div class="image-preview-frame pce-assets-import-preview">
              <img data-import-preview alt="Import preview" hidden />
              <div class="inline-no-preview" data-import-no-preview>PNG / BMP を選択してください</div>
            </div>
            <div class="form-hint" data-import-hint>BG は SuperFamiconv `pce`、Sprite は `pce_sprite` で変換します。</div>
            <div class="form-error" data-import-error></div>
            <div class="form-actions-inline modal-actions-end">
              <button class="btn-sm" type="button" data-import-cancel>キャンセル</button>
              <button class="btn-primary" type="submit">変換して保存</button>
            </div>
          </form>
        `,
      });
      const form = modal.panel.querySelector('form');
      const sourceLabel = modal.panel.querySelector('[data-source-label]');
      const preview = modal.panel.querySelector('[data-import-preview]');
      const noPreview = modal.panel.querySelector('[data-import-no-preview]');
      const error = modal.panel.querySelector('[data-import-error]');
      const kindSelect = form.elements.kind;
      const tileBaseInput = form.elements.tileBase;
      const mapBaseInput = form.elements.mapBase;
      const cellSizeSelect = form.elements.cellSize;
      let sourcePath = importFile?.sourcePath || '';
      let sourceFileName = importFile?.fileName || '';
      let sourceDataUrl = '';

      function syncKind() {
        const isSprite = kindSelect.value === 'sprite';
        cellSizeSelect.disabled = !isSprite;
        mapBaseInput.disabled = isSprite;
        if (!tileBaseInput.dataset.touched) tileBaseInput.value = isSprite ? '384' : '32';
      }

      async function setSource(filePath) {
        sourcePath = filePath || '';
        sourceFileName = sourcePath.split(/[\\/]/).pop() || '';
        form.elements.id.value = sourceFileName.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]+/g, '_');
        form.elements.name.value = sourceFileName.replace(/\.[^.]+$/, '');
        sourceLabel.textContent = sourcePath || '未選択';
        sourceDataUrl = '';
        preview.hidden = true;
        noPreview.hidden = false;
        if (!sourcePath) return;
        const read = await api.electronAPI.readFileAsDataUrl(sourcePath);
        if (!read?.ok) {
          error.textContent = read?.error || '画像を読み込めません';
          return;
        }
        sourceDataUrl = read.dataUrl;
        preview.src = sourceDataUrl;
        preview.hidden = false;
        noPreview.hidden = true;
      }

      modal.panel.querySelector('[data-pick-image]').addEventListener('click', async () => {
        error.textContent = '';
        const picked = await api.electronAPI.pickFile({
          properties: ['openFile'],
          filters: [{ name: 'PNG / BMP', extensions: ['png', 'bmp'] }],
        });
        const filePath = picked?.sourcePath || picked?.filePath || picked?.filePaths?.[0] || '';
        if (picked?.canceled || !filePath) return;
        await setSource(filePath);
      });
      tileBaseInput.addEventListener('input', () => { tileBaseInput.dataset.touched = '1'; });
      kindSelect.addEventListener('change', syncKind);
      modal.panel.querySelectorAll('[data-import-cancel]').forEach((button) => {
        button.addEventListener('click', () => {
          modal.close();
          modal.destroy?.();
          resolve(null);
        }, { once: true });
      });
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        error.textContent = '';
        if (!sourcePath) {
          error.textContent = '画像を選択してください';
          return;
        }
        try {
          const [cellWidth, cellHeight] = String(form.elements.cellSize.value || '16x16').split('x').map((value) => asNumber(value, 16));
          const ext = extname(sourcePath);
          const convertedDataUrl = ext === '.bmp' ? await dataUrlToPng(sourceDataUrl) : '';
          const result = await api.electronAPI.importAssetImage({
            sourcePath,
            sourceFileName,
            convertedDataUrl,
            kind: form.elements.kind.value,
            id: form.elements.id.value,
            name: form.elements.name.value,
            paletteBank: asNumber(form.elements.paletteBank.value, 0),
            tileBase: asNumber(form.elements.tileBase.value, form.elements.kind.value === 'sprite' ? 384 : 32),
            mapBase: asNumber(form.elements.mapBase.value, 0),
            cellWidth,
            cellHeight,
            transparentIndex: asNumber(form.elements.transparentIndex.value, 0),
          });
          if (!result?.ok) throw new Error(result?.error || '取り込みに失敗しました');
          logger.info(`PCE image imported: ${result.asset?.id || form.elements.id.value}`);
          modal.close();
          modal.destroy?.();
          resolve(result.asset || null);
        } catch (err) {
          error.textContent = err.message || String(err);
        }
      });
      syncKind();
      if (sourcePath) void setSource(sourcePath);
      modal.open();
    }).then(async (asset) => {
      if (asset) {
        selectedId = asset.id;
        await reload();
      }
      return asset;
    });
  }

  root.querySelectorAll('[data-accordion]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.accordion;
      const body = root.querySelector(`[data-accordion-body="${key}"]`);
      const expanded = button.getAttribute('aria-expanded') !== 'false';
      button.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      body?.classList.toggle('is-collapsed', expanded);
    });
  });

  searchEl.addEventListener('input', renderRows);
  typeFilterEl.addEventListener('change', renderRows);
  fields.type.addEventListener('change', () => setFieldVisibility(collectFormAsset()));
  formEl.addEventListener('submit', saveSelected);
  deleteButton.addEventListener('click', () => deleteAsset());
  root.querySelector('[data-action="refresh"]').addEventListener('click', reload);
  root.querySelector('[data-action="import"]').addEventListener('click', () => openImportWizard('background'));
  root.querySelector('[data-action="new-psg"]').addEventListener('click', () => {
    const id = `beep_${Date.now()}`;
    assets.push({
      id,
      type: 'psg-sequence',
      name: 'Beep',
      source: 'assets/sound/beep.json',
      options: { period: 512 },
      data: {},
    });
    selectedId = id;
    renderRows();
    fillForm(selectedAsset());
  });

  registerCapability('asset-manager', { pluginId: plugin.id, reload, openImportWizard });
  registerCapability('asset-import-handler', {
    pluginId: plugin.id,
    openImportWizard,
    async handleImport(file = {}) {
      const ext = String(file.ext || extname(file.sourcePath || file.path || '')).toLowerCase();
      if (!IMAGE_EXTS.includes(ext)) return null;
      return openImportWizard(file.kind === 'sprite' ? 'sprite' : 'background', {
        sourcePath: file.sourcePath || file.path,
        fileName: file.fileName || '',
      });
    },
  });
  registerCapability('asset-type-provider', {
    priority: 10,
    getTypeInfo(file = {}) {
      const ext = String(file.ext || '').toLowerCase();
      if (IMAGE_EXTS.includes(ext)) {
        return {
          initialType: 'image',
          allowedTypes: ['image', 'sprite'],
          defaultSubdir: 'assets/images',
          isImageInput: true,
        };
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
