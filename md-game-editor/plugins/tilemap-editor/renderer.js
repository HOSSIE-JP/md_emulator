import {
  buildTmx,
  buildTsx,
  createBlankTilemap,
  normalizeLayerData,
  normalizeSymbolName,
  parseTmx,
  parseTsx,
} from './tilemap-core.mjs';

const IMAGE_FILTERS = [
  { name: 'Images', extensions: ['png', 'bmp'] },
  { name: 'All Files', extensions: ['*'] },
];

const TMX_FILTERS = [
  { name: 'Tiled Map', extensions: ['tmx'] },
  { name: 'All Files', extensions: ['*'] },
];

const TOOL_LABELS = {
  pen: 'ペン',
  eraser: '消しゴム',
  fill: '塗りつぶし',
  rect: '矩形',
  eyedropper: 'スポイト',
};

export function activatePlugin({ plugin, root, api, logger, registerCapability }) {
  if (!root) return null;
  root.classList.add('tilemap-editor-page');

  const state = {
    map: createBlankTilemap(),
    selectedLayer: 0,
    selectedTile: 1,
    tool: 'pen',
    showGrid: true,
    showPriority: true,
    zoom: 2,
    tilesetImage: null,
    tilesetDataUrl: '',
    tilesetImageAbsolutePath: '',
    dirty: false,
    dragStart: null,
    hoverCell: null,
    warnings: [],
    resFile: 'resources.res',
    resourceType: 'MAP',
  };

  root.innerHTML = buildShell();
  const ui = bindUi(root);
  syncInputsFromMap();
  bindEvents();
  renderAll();

  registerCapability('tilemap-editor', {
    pluginId: plugin.id,
    root,
    getMap: () => structuredCloneSafe(state.map),
    save: () => saveFiles(),
    registerResources: () => registerResources(),
  });

  logger.debug('tilemap-editor renderer activated');
  return {
    deactivate() {
      root.innerHTML = '';
      root.classList.remove('tilemap-editor-page');
    },
  };

  function bindEvents() {
    ui.newMap.addEventListener('click', () => newMapFromInputs());
    ui.loadTmx.addEventListener('click', () => void loadTmx());
    ui.save.addEventListener('click', () => void saveFiles());
    ui.register.addEventListener('click', () => void registerResources());
    ui.importTileset.addEventListener('click', () => void importTileset());

    [ui.mapName, ui.tilesetName, ui.mapWidth, ui.mapHeight, ui.tileWidth, ui.tileHeight].forEach((input) => {
      input.addEventListener('change', () => {
        applySettingsInputs();
        renderAll();
      });
    });

    ui.resourceType.addEventListener('change', () => {
      state.resourceType = ui.resourceType.value;
    });
    ui.resFile.addEventListener('change', () => {
      state.resFile = ui.resFile.value.trim() || 'resources.res';
    });
    ui.layerSelect.addEventListener('change', () => {
      state.selectedLayer = clamp(Number(ui.layerSelect.value) || 0, 0, state.map.layers.length - 1);
      renderAll();
    });
    ui.addLayer.addEventListener('click', () => addLayer(false));
    ui.addPriorityLayer.addEventListener('click', () => addLayer(true));
    ui.deleteLayer.addEventListener('click', () => deleteLayer());
    ui.layerUp.addEventListener('click', () => moveLayer(-1));
    ui.layerDown.addEventListener('click', () => moveLayer(1));
    ui.layerName.addEventListener('change', () => renameLayer());
    ui.layerVisible.addEventListener('change', () => {
      const layer = getActiveLayer();
      if (layer) layer.visible = ui.layerVisible.checked;
      state.dirty = true;
      renderAll();
    });
    ui.gridToggle.addEventListener('change', () => {
      state.showGrid = ui.gridToggle.checked;
      drawMap();
    });
    ui.priorityToggle.addEventListener('change', () => {
      state.showPriority = ui.priorityToggle.checked;
      drawMap();
    });
    ui.zoom.addEventListener('input', () => {
      state.zoom = clamp(Number(ui.zoom.value) || 2, 1, 8);
      drawMap();
    });

    ui.toolButtons.forEach((button) => {
      button.addEventListener('click', () => {
        state.tool = button.dataset.tool;
        syncToolButtons();
      });
    });

    ui.tilesetCanvas.addEventListener('click', (event) => {
      const pos = canvasPoint(event, ui.tilesetCanvas);
      const col = Math.floor(pos.x / state.map.tileWidth);
      const row = Math.floor(pos.y / state.map.tileHeight);
      const tile = row * Math.max(1, state.map.tilesetColumns) + col + 1;
      if (tile > 0 && tile <= Math.max(1, state.map.tilesetTileCount)) {
        state.selectedTile = tile;
        renderTileset();
        syncStatus();
      }
    });

    ui.mapCanvas.addEventListener('pointerdown', (event) => {
      ui.mapCanvas.setPointerCapture(event.pointerId);
      const cell = eventToCell(event);
      if (!cell) return;
      state.dragStart = cell;
      applyTool(cell, cell);
    });
    ui.mapCanvas.addEventListener('pointermove', (event) => {
      const cell = eventToCell(event);
      state.hoverCell = cell;
      if (cell && state.dragStart && state.tool === 'rect') {
        drawMap({ rectEnd: cell });
      } else if (cell && event.buttons === 1 && state.dragStart && ['pen', 'eraser'].includes(state.tool)) {
        applyTool(cell, state.dragStart);
      } else {
        syncStatus();
      }
    });
    ui.mapCanvas.addEventListener('pointerup', (event) => {
      const cell = eventToCell(event);
      if (cell && state.dragStart && state.tool === 'rect') {
        applyTool(cell, state.dragStart);
      }
      state.dragStart = null;
      drawMap();
    });
    ui.mapCanvas.addEventListener('pointerleave', () => {
      state.hoverCell = null;
      syncStatus();
    });
  }

  function newMapFromInputs() {
    const next = createBlankTilemap({
      name: ui.mapName.value,
      width: ui.mapWidth.value,
      height: ui.mapHeight.value,
      tileWidth: ui.tileWidth.value,
      tileHeight: ui.tileHeight.value,
      tilesetName: ui.tilesetName.value,
    });
    if (state.tilesetImage) {
      next.tilesetImage = state.map.tilesetImage;
      next.tilesetImageWidth = state.map.tilesetImageWidth;
      next.tilesetImageHeight = state.map.tilesetImageHeight;
      next.tilesetColumns = state.map.tilesetColumns;
      next.tilesetTileCount = state.map.tilesetTileCount;
    }
    state.map = next;
    state.selectedLayer = 0;
    state.selectedTile = 1;
    state.warnings = [];
    state.dirty = true;
    syncInputsFromMap();
    renderAll();
  }

  async function loadTmx() {
    const picked = await api.electronAPI.pickFile({ properties: ['openFile'], filters: TMX_FILTERS });
    if (!picked?.ok || picked.canceled || !picked.filePath) return;
    const project = await api.electronAPI.getCurrentProject?.();
    const projectDir = project?.dir || '';
    const rel = projectDir ? toProjectRelative(picked.filePath, projectDir) : '';
    if (!rel) {
      setStatus('プロジェクト配下の TMX を選んでください。');
      return;
    }
    const read = await api.electronAPI.readCodeFile({ path: rel });
    if (!read?.ok) {
      setStatus(`TMX 読み込み失敗: ${read?.error || 'unknown'}`);
      return;
    }
    try {
      const parsed = parseTmx(read.content);
      parsed.name = normalizeSymbolName(rel.split(/[\\/]/).pop(), state.map.name);
      state.map = { ...state.map, ...parsed };
      state.warnings = parsed.warnings || [];
      state.selectedLayer = 0;
      state.dirty = false;
      syncInputsFromMap();
      await tryLoadTsxForMap(rel, projectDir);
      renderAll();
      setStatus(`読み込みました: ${rel}`);
    } catch (err) {
      setStatus(`TMX parse 失敗: ${String(err?.message || err)}`);
    }
  }

  async function tryLoadTsxForMap(tmxRelPath, projectDir) {
    if (!state.map.tilesetSource) return;
    const tmxDir = dirname(tmxRelPath);
    const tsxRel = normalizeRelPath(`${tmxDir}/${state.map.tilesetSource}`);
    const read = await api.electronAPI.readCodeFile({ path: `res/${tsxRel.replace(/^res\//, '')}` }).catch(() => null);
    const fallbackRead = read?.ok ? read : await api.electronAPI.readCodeFile({ path: tsxRel }).catch(() => null);
    if (!fallbackRead?.ok) {
      state.warnings.push(`TSX を読めません: ${state.map.tilesetSource}`);
      return;
    }
    try {
      const tsx = parseTsx(fallbackRead.content);
      state.map = { ...state.map, ...tsx };
      const imageRelFromTsx = normalizeRelPath(`${dirname(tsxRel)}/${tsx.tilesetImage}`);
      const imageAbs = projectDir ? `${projectDir.replace(/\\/g, '/')}/${imageRelFromTsx}` : '';
      if (imageAbs) await loadTilesetImage(imageAbs);
    } catch (err) {
      state.warnings.push(`TSX parse 失敗: ${String(err?.message || err)}`);
    }
  }

  async function importTileset() {
    const picked = await api.electronAPI.pickFile({ properties: ['openFile'], filters: IMAGE_FILTERS });
    if (!picked?.ok || picked.canceled || !picked.filePath) return;
    const pipeline = api.capabilities.get('image-import-pipeline');
    if (!pipeline?.convertToIndexed16) {
      setStatus('image-import-pipeline が無効です。asset-manager と converter を有効にしてください。');
      return;
    }
    applySettingsInputs();
    setStatus('tileset 画像を 16 色 indexed PNG に変換中...');
    const converted = await pipeline.convertToIndexed16({
      sourcePath: picked.filePath,
      targetSize: null,
    });
    if (converted?.canceled) {
      setStatus(converted.warning || 'tileset import をキャンセルしました');
      return;
    }
    const base = normalizeSymbolName(ui.tilesetName.value || state.map.tilesetName, 'tileset001');
    const copy = await api.electronAPI.writeAssetFile({
      sourcePath: picked.filePath,
      targetSubdir: 'tilesets',
      targetFileName: `${base}.png`,
      dataUrl: converted.convertedDataUrl || '',
    });
    if (!copy?.ok) {
      setStatus(`tileset コピー失敗: ${copy?.error || 'unknown'}`);
      return;
    }
    state.map.tilesetName = base;
    state.map.tilesetImage = `${base}.png`;
    state.tilesetImageAbsolutePath = copy.absolutePath || '';
    await loadTilesetImage(copy.absolutePath);
    state.dirty = true;
    syncInputsFromMap();
    renderAll();
    setStatus(converted.warning || `tileset を登録しました: ${copy.relativePath}`);
  }

  async function saveFiles() {
    applySettingsInputs();
    const mapName = normalizeSymbolName(state.map.name, 'map001');
    const tilesetName = normalizeSymbolName(state.map.tilesetName, `${mapName}_tiles`);
    state.map.name = mapName;
    state.map.tilesetName = tilesetName;
    state.map.tilesetSource = `../tilesets/${tilesetName}.tsx`;
    const tmxRel = `res/maps/${mapName}.tmx`;
    const tsxRel = `res/tilesets/${tilesetName}.tsx`;
    const tmx = buildTmx(state.map);
    const tsx = buildTsx(state.map);
    const tsxResult = await api.electronAPI.writeCodeFile({ path: tsxRel, content: tsx });
    if (!tsxResult?.ok) {
      setStatus(`TSX 保存失敗: ${tsxResult?.error || 'unknown'}`);
      return false;
    }
    const tmxResult = await api.electronAPI.writeCodeFile({ path: tmxRel, content: tmx });
    if (!tmxResult?.ok) {
      setStatus(`TMX 保存失敗: ${tmxResult?.error || 'unknown'}`);
      return false;
    }
    state.dirty = false;
    syncInputsFromMap();
    setStatus(`保存しました: ${tmxRel}, ${tsxRel}`);
    return true;
  }

  async function registerResources() {
    const saved = await saveFiles();
    if (!saved) return;
    const mapName = normalizeSymbolName(state.map.name, 'map001');
    const tilesetName = normalizeSymbolName(state.map.tilesetName, `${mapName}_tiles`);
    const layer = getActiveLayer() || state.map.layers[0];
    const resFile = ui.resFile.value.trim() || 'resources.res';
    const type = ui.resourceType.value === 'TILEMAP' ? 'TILEMAP' : 'MAP';
    const tsxPath = `tilesets/${tilesetName}.tsx`;
    const tmxPath = `maps/${mapName}.tmx`;
    const defs = await api.electronAPI.listResDefinitions();
    const entries = (defs?.files || []).flatMap((file) => (file.entries || []).map((entry) => ({ ...entry, file: file.file })));
    if (!entries.some((entry) => entry.type === 'TILESET' && entry.name === tilesetName && entry.sourcePath === tsxPath)) {
      const addTileset = await api.electronAPI.addResEntry({
        file: resFile,
        entry: {
          type: 'TILESET',
          name: tilesetName,
          sourcePath: tsxPath,
          compression: 'NONE',
          opt: 'ALL',
          ordering: 'ROW',
          export: 'FALSE',
          comment: 'Generated by tilemap-editor',
        },
      });
      if (!addTileset?.ok) {
        setStatus(`TILESET 登録失敗: ${addTileset?.error || 'unknown'}`);
        return;
      }
    }
    if (!entries.some((entry) => entry.type === type && entry.name === mapName && entry.sourcePath === tmxPath && entry.tileset === layer.name)) {
      const entry = {
        type,
        name: mapName,
        sourcePath: tmxPath,
        tileset: layer.name,
        compression: 'NONE',
        mapCompression: 'NONE',
        mapBase: '0',
        ordering: 'ROW',
        comment: 'TMX input: tileset_id field is used as layer_id for SGDK ResComp',
      };
      const addMap = await api.electronAPI.addResEntry({ file: resFile, entry });
      if (!addMap?.ok) {
        setStatus(`${type} 登録失敗: ${addMap?.error || 'unknown'}`);
        return;
      }
    }
    await api.assets?.reloadResources?.({ keepSelection: true });
    setStatus(`resources.res に登録しました: TILESET ${tilesetName}, ${type} ${mapName} (${layer.name})`);
  }

  function addLayer(priority) {
    applySettingsInputs();
    const base = priority ? `${getActiveLayer()?.name || 'Ground'} priority` : `Layer ${state.map.layers.length + 1}`;
    state.map.layers.push({
      name: uniqueLayerName(base),
      visible: true,
      opacity: 1,
      priority,
      data: new Array(state.map.width * state.map.height).fill(0),
    });
    state.selectedLayer = state.map.layers.length - 1;
    state.dirty = true;
    renderAll();
  }

  function deleteLayer() {
    if (state.map.layers.length <= 1) {
      setStatus('layer は最低 1 つ必要です。');
      return;
    }
    state.map.layers.splice(state.selectedLayer, 1);
    state.selectedLayer = clamp(state.selectedLayer, 0, state.map.layers.length - 1);
    state.dirty = true;
    renderAll();
  }

  function moveLayer(delta) {
    const next = state.selectedLayer + delta;
    if (next < 0 || next >= state.map.layers.length) return;
    const [layer] = state.map.layers.splice(state.selectedLayer, 1);
    state.map.layers.splice(next, 0, layer);
    state.selectedLayer = next;
    state.dirty = true;
    renderAll();
  }

  function renameLayer() {
    const layer = getActiveLayer();
    if (!layer) return;
    layer.name = ui.layerName.value.trim() || layer.name;
    layer.priority = /\s(priority|prio)$/i.test(layer.name);
    state.dirty = true;
    renderAll();
  }

  function applySettingsInputs() {
    const oldW = state.map.width;
    const oldH = state.map.height;
    const nextW = clamp(Number(ui.mapWidth.value) || oldW, 1, 512);
    const nextH = clamp(Number(ui.mapHeight.value) || oldH, 1, 512);
    state.map.name = normalizeSymbolName(ui.mapName.value, 'map001');
    state.map.tilesetName = normalizeSymbolName(ui.tilesetName.value, `${state.map.name}_tiles`);
    state.map.tileWidth = clamp(Number(ui.tileWidth.value) || state.map.tileWidth, 8, 64);
    state.map.tileHeight = clamp(Number(ui.tileHeight.value) || state.map.tileHeight, 8, 64);
    if (nextW !== oldW || nextH !== oldH) {
      state.map.layers = state.map.layers.map((layer) => ({
        ...layer,
        data: resizeLayerData(layer.data, oldW, oldH, nextW, nextH),
      }));
      state.map.width = nextW;
      state.map.height = nextH;
    }
    updateTilesetMetrics();
    state.dirty = true;
  }

  function applyTool(cell, startCell) {
    const layer = getActiveLayer();
    if (!layer) return;
    const index = cell.y * state.map.width + cell.x;
    if (state.tool === 'eyedropper') {
      state.selectedTile = Math.max(1, layer.data[index] || 1);
      renderTileset();
      syncStatus();
      return;
    }
    if (state.tool === 'fill') {
      floodFill(layer, cell.x, cell.y, layer.data[index], state.selectedTile);
    } else if (state.tool === 'rect') {
      const minX = Math.min(startCell.x, cell.x);
      const maxX = Math.max(startCell.x, cell.x);
      const minY = Math.min(startCell.y, cell.y);
      const maxY = Math.max(startCell.y, cell.y);
      for (let y = minY; y <= maxY; y += 1) {
        for (let x = minX; x <= maxX; x += 1) layer.data[y * state.map.width + x] = state.selectedTile;
      }
    } else {
      layer.data[index] = state.tool === 'eraser' ? 0 : state.selectedTile;
    }
    state.dirty = true;
    drawMap();
  }

  function floodFill(layer, x, y, fromTile, toTile) {
    if (fromTile === toTile) return;
    const w = state.map.width;
    const h = state.map.height;
    const queue = [[x, y]];
    while (queue.length) {
      const [cx, cy] = queue.pop();
      if (cx < 0 || cy < 0 || cx >= w || cy >= h) continue;
      const idx = cy * w + cx;
      if (layer.data[idx] !== fromTile) continue;
      layer.data[idx] = toTile;
      queue.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }
  }

  function renderAll() {
    renderLayerControls();
    renderWarnings();
    renderTileset();
    drawMap();
    syncToolButtons();
    syncStatus();
  }

  function renderLayerControls() {
    ui.layerSelect.innerHTML = '';
    state.map.layers.forEach((layer, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = `${index + 1}. ${layer.name}${layer.priority ? ' [priority]' : ''}`;
      ui.layerSelect.appendChild(option);
    });
    ui.layerSelect.value = String(state.selectedLayer);
    const layer = getActiveLayer();
    ui.layerName.value = layer?.name || '';
    ui.layerVisible.checked = layer?.visible !== false;
  }

  function renderWarnings() {
    const warnings = state.warnings || [];
    ui.warningList.hidden = warnings.length === 0;
    ui.warningList.innerHTML = warnings.map((warning) => `<div>${esc(warning)}</div>`).join('');
  }

  function renderTileset() {
    const canvas = ui.tilesetCanvas;
    const ctx = canvas.getContext('2d');
    const tw = state.map.tileWidth;
    const th = state.map.tileHeight;
    const columns = Math.max(1, state.map.tilesetColumns || 1);
    const rows = Math.max(1, Math.ceil((state.map.tilesetTileCount || 1) / columns));
    canvas.width = Math.max(tw, columns * tw);
    canvas.height = Math.max(th, rows * th);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#101722';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (state.tilesetImage) {
      ctx.drawImage(state.tilesetImage, 0, 0);
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.2)';
    for (let x = 0; x <= canvas.width; x += tw) line(ctx, x, 0, x, canvas.height);
    for (let y = 0; y <= canvas.height; y += th) line(ctx, 0, y, canvas.width, y);
    const selected = Math.max(1, state.selectedTile) - 1;
    const sx = (selected % columns) * tw;
    const sy = Math.floor(selected / columns) * th;
    ctx.strokeStyle = '#f2c94c';
    ctx.lineWidth = 2;
    ctx.strokeRect(sx + 1, sy + 1, Math.max(1, tw - 2), Math.max(1, th - 2));
  }

  function drawMap(options = {}) {
    const canvas = ui.mapCanvas;
    const ctx = canvas.getContext('2d');
    const scale = state.zoom;
    const tw = state.map.tileWidth;
    const th = state.map.tileHeight;
    const w = state.map.width;
    const h = state.map.height;
    canvas.width = Math.max(1, w * tw * scale);
    canvas.height = Math.max(1, h * th * scale);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#0b0f17';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    state.map.layers.forEach((layer, layerIndex) => {
      if (layer.visible === false) return;
      const alpha = clamp(Number(layer.opacity) || 1, 0, 1);
      ctx.globalAlpha = alpha;
      drawLayer(ctx, layer, scale, layerIndex === state.selectedLayer);
      ctx.globalAlpha = 1;
    });
    if (state.showGrid) {
      ctx.strokeStyle = 'rgba(255,255,255,0.11)';
      ctx.lineWidth = 1;
      for (let x = 0; x <= w; x += 1) line(ctx, x * tw * scale, 0, x * tw * scale, h * th * scale);
      for (let y = 0; y <= h; y += 1) line(ctx, 0, y * th * scale, w * tw * scale, y * th * scale);
    }
    if (options.rectEnd && state.dragStart) {
      const minX = Math.min(state.dragStart.x, options.rectEnd.x);
      const maxX = Math.max(state.dragStart.x, options.rectEnd.x);
      const minY = Math.min(state.dragStart.y, options.rectEnd.y);
      const maxY = Math.max(state.dragStart.y, options.rectEnd.y);
      ctx.strokeStyle = '#f2c94c';
      ctx.lineWidth = 2;
      ctx.strokeRect(minX * tw * scale + 1, minY * th * scale + 1, (maxX - minX + 1) * tw * scale - 2, (maxY - minY + 1) * th * scale - 2);
    }
    syncStatus();
  }

  function drawLayer(ctx, layer, scale, selectedLayer) {
    const tw = state.map.tileWidth;
    const th = state.map.tileHeight;
    const columns = Math.max(1, state.map.tilesetColumns || 1);
    for (let y = 0; y < state.map.height; y += 1) {
      for (let x = 0; x < state.map.width; x += 1) {
        const gid = layer.data[y * state.map.width + x] || 0;
        if (gid <= 0) continue;
        const tile = gid - 1;
        const sx = (tile % columns) * tw;
        const sy = Math.floor(tile / columns) * th;
        const dx = x * tw * scale;
        const dy = y * th * scale;
        if (state.tilesetImage) {
          ctx.drawImage(state.tilesetImage, sx, sy, tw, th, dx, dy, tw * scale, th * scale);
        } else {
          ctx.fillStyle = colorForTile(gid);
          ctx.fillRect(dx, dy, tw * scale, th * scale);
        }
        if (state.showPriority && layer.priority) {
          ctx.fillStyle = 'rgba(242,201,76,0.28)';
          ctx.fillRect(dx, dy, tw * scale, th * scale);
        }
        if (selectedLayer) {
          ctx.strokeStyle = 'rgba(74,163,255,0.18)';
          ctx.strokeRect(dx + 0.5, dy + 0.5, tw * scale - 1, th * scale - 1);
        }
      }
    }
  }

  async function loadTilesetImage(absPath) {
    if (!absPath) return;
    const read = await api.electronAPI.readFileAsDataUrl(absPath);
    if (!read?.ok || !read.dataUrl) {
      state.warnings.push(`tileset image を読めません: ${read?.error || absPath}`);
      return;
    }
    const img = new Image();
    img.src = read.dataUrl;
    await img.decode();
    state.tilesetImage = img;
    state.tilesetDataUrl = read.dataUrl;
    state.tilesetImageAbsolutePath = absPath;
    state.map.tilesetImageWidth = img.naturalWidth || img.width;
    state.map.tilesetImageHeight = img.naturalHeight || img.height;
    updateTilesetMetrics();
  }

  function updateTilesetMetrics() {
    const tw = Math.max(1, state.map.tileWidth);
    const th = Math.max(1, state.map.tileHeight);
    const imageW = Math.max(tw, Number(state.map.tilesetImageWidth) || tw);
    const imageH = Math.max(th, Number(state.map.tilesetImageHeight) || th);
    state.map.tilesetColumns = Math.max(1, Math.floor(imageW / tw));
    state.map.tilesetTileCount = Math.max(1, state.map.tilesetColumns * Math.floor(imageH / th));
  }

  function syncInputsFromMap() {
    ui.mapName.value = state.map.name || 'map001';
    ui.tilesetName.value = state.map.tilesetName || 'tileset001';
    ui.mapWidth.value = String(state.map.width || 40);
    ui.mapHeight.value = String(state.map.height || 28);
    ui.tileWidth.value = String(state.map.tileWidth || 8);
    ui.tileHeight.value = String(state.map.tileHeight || 8);
    ui.resourceType.value = state.resourceType;
    ui.resFile.value = state.resFile;
    ui.gridToggle.checked = state.showGrid;
    ui.priorityToggle.checked = state.showPriority;
    ui.zoom.value = String(state.zoom);
  }

  function syncToolButtons() {
    ui.toolButtons.forEach((button) => {
      const active = button.dataset.tool === state.tool;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function syncStatus() {
    const cell = state.hoverCell ? ` x:${state.hoverCell.x} y:${state.hoverCell.y}` : '';
    const dirty = state.dirty ? ' / 未保存' : '';
    const layer = getActiveLayer()?.name || '-';
    ui.status.textContent = `${state.map.width}x${state.map.height} tiles / tile ${state.selectedTile} / layer ${layer} / ${TOOL_LABELS[state.tool]}${cell}${dirty}`;
  }

  function setStatus(text) {
    ui.status.textContent = text;
  }

  function getActiveLayer() {
    return state.map.layers[state.selectedLayer] || null;
  }

  function eventToCell(event) {
    const pos = canvasPoint(event, ui.mapCanvas);
    const scale = state.zoom;
    const x = Math.floor(pos.x / (state.map.tileWidth * scale));
    const y = Math.floor(pos.y / (state.map.tileHeight * scale));
    if (x < 0 || y < 0 || x >= state.map.width || y >= state.map.height) return null;
    return { x, y };
  }

  function uniqueLayerName(base) {
    const names = new Set(state.map.layers.map((layer) => layer.name));
    if (!names.has(base)) return base;
    let index = 2;
    while (names.has(`${base} ${index}`)) index += 1;
    return `${base} ${index}`;
  }
}

function buildShell() {
  return `
    <div class="tilemap-editor-shell">
      <aside class="tilemap-sidebar">
        <div class="tilemap-toolbar">
          <h2>TileMap</h2>
          <button class="icon-btn" type="button" data-action="new" title="新規"><svg class="icon"><use href="#icon-add"></use></svg></button>
          <button class="icon-btn" type="button" data-action="load" title="TMX 読込"><svg class="icon"><use href="#icon-folder"></use></svg></button>
          <button class="icon-btn" type="button" data-action="save" title="保存"><svg class="icon"><use href="#icon-save"></use></svg></button>
        </div>
        <div class="tilemap-form">
          ${field('Map', 'mapName', 'map001')}
          <div class="tilemap-form-row">
            ${field('W', 'mapWidth', '40', 'number')}
            ${field('H', 'mapHeight', '28', 'number')}
          </div>
          <div class="tilemap-form-row">
            ${field('Tile W', 'tileWidth', '8', 'number')}
            ${field('Tile H', 'tileHeight', '8', 'number')}
          </div>
          ${field('Tileset', 'tilesetName', 'tileset001')}
          <button class="secondary-btn" type="button" data-action="import-tileset">Tileset 画像を読み込み</button>
        </div>
        <div class="tilemap-section">
          <div class="tilemap-section-title">Layers</div>
          <select class="tilemap-input" data-ui="layerSelect"></select>
          ${field('Layer name', 'layerName', 'Ground')}
          <label class="tilemap-check"><input type="checkbox" data-ui="layerVisible" checked> 表示</label>
          <div class="tilemap-button-row">
            <button class="icon-btn" type="button" data-action="add-layer" title="Layer 追加"><svg class="icon"><use href="#icon-add"></use></svg></button>
            <button class="icon-btn" type="button" data-action="add-priority-layer" title="Priority layer 追加"><svg class="icon"><use href="#icon-grid"></use></svg></button>
            <button class="icon-btn" type="button" data-action="layer-up" title="上へ"><svg class="icon"><use href="#icon-chevron-up"></use></svg></button>
            <button class="icon-btn" type="button" data-action="layer-down" title="下へ"><svg class="icon"><use href="#icon-chevron-down"></use></svg></button>
            <button class="icon-btn" type="button" data-action="delete-layer" title="削除"><svg class="icon"><use href="#icon-trash"></use></svg></button>
          </div>
        </div>
        <div class="tilemap-section">
          <div class="tilemap-section-title">ResComp</div>
          <select class="tilemap-input" data-ui="resourceType"><option>MAP</option><option>TILEMAP</option></select>
          ${field('res file', 'resFile', 'resources.res')}
          <button class="primary-btn" type="button" data-action="register">保存して .res 登録</button>
        </div>
        <div class="tilemap-warnings" data-ui="warningList" hidden></div>
      </aside>
      <main class="tilemap-main">
        <div class="tilemap-toolbar">
          <div class="tilemap-tool-group">
            ${toolButton('pen', '鉛筆')}
            ${toolButton('eraser', '消去')}
            ${toolButton('fill', '塗りつぶし')}
            ${toolButton('rect', '矩形')}
            ${toolButton('eyedropper', 'スポイト')}
          </div>
          <label class="tilemap-check"><input type="checkbox" data-ui="gridToggle" checked> Grid</label>
          <label class="tilemap-check"><input type="checkbox" data-ui="priorityToggle" checked> Priority</label>
          <label class="tilemap-zoom">Zoom <input type="range" min="1" max="8" value="2" data-ui="zoom"></label>
        </div>
        <div class="tilemap-canvas-wrap">
          <canvas data-ui="mapCanvas"></canvas>
        </div>
        <div class="tilemap-status" data-ui="status"></div>
      </main>
      <aside class="tilemap-tileset">
        <div class="tilemap-toolbar"><h2>Tiles</h2></div>
        <div class="tilemap-tileset-wrap"><canvas data-ui="tilesetCanvas"></canvas></div>
      </aside>
    </div>
  `;
}

function field(label, name, value, type = 'text') {
  return `<label class="tilemap-field"><span>${label}</span><input class="tilemap-input" type="${type}" data-ui="${name}" value="${value}"></label>`;
}

function toolButton(tool, label) {
  return `<button class="tilemap-tool" type="button" data-tool="${tool}" title="${label}" aria-pressed="false">${label}</button>`;
}

function bindUi(root) {
  const byAction = (name) => root.querySelector(`[data-action="${name}"]`);
  const byUi = (name) => root.querySelector(`[data-ui="${name}"]`);
  return {
    newMap: byAction('new'),
    loadTmx: byAction('load'),
    save: byAction('save'),
    register: byAction('register'),
    importTileset: byAction('import-tileset'),
    addLayer: byAction('add-layer'),
    addPriorityLayer: byAction('add-priority-layer'),
    deleteLayer: byAction('delete-layer'),
    layerUp: byAction('layer-up'),
    layerDown: byAction('layer-down'),
    mapName: byUi('mapName'),
    mapWidth: byUi('mapWidth'),
    mapHeight: byUi('mapHeight'),
    tileWidth: byUi('tileWidth'),
    tileHeight: byUi('tileHeight'),
    tilesetName: byUi('tilesetName'),
    layerSelect: byUi('layerSelect'),
    layerName: byUi('layerName'),
    layerVisible: byUi('layerVisible'),
    resourceType: byUi('resourceType'),
    resFile: byUi('resFile'),
    gridToggle: byUi('gridToggle'),
    priorityToggle: byUi('priorityToggle'),
    zoom: byUi('zoom'),
    mapCanvas: byUi('mapCanvas'),
    tilesetCanvas: byUi('tilesetCanvas'),
    status: byUi('status'),
    warningList: byUi('warningList'),
    toolButtons: Array.from(root.querySelectorAll('[data-tool]')),
  };
}

function canvasPoint(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / Math.max(1, rect.width)) * canvas.width,
    y: ((event.clientY - rect.top) / Math.max(1, rect.height)) * canvas.height,
  };
}

function resizeLayerData(data, oldW, oldH, nextW, nextH) {
  const next = new Array(nextW * nextH).fill(0);
  const source = normalizeLayerData(data, oldW, oldH);
  for (let y = 0; y < Math.min(oldH, nextH); y += 1) {
    for (let x = 0; x < Math.min(oldW, nextW); x += 1) {
      next[y * nextW + x] = source[y * oldW + x] || 0;
    }
  }
  return next;
}

function toProjectRelative(absPath, projectDir) {
  const normalizedProject = projectDir.replace(/\\/g, '/').replace(/\/+$/, '');
  const normalizedPath = String(absPath || '').replace(/\\/g, '/');
  if (!normalizedPath.startsWith(`${normalizedProject}/`)) return '';
  return normalizedPath.slice(normalizedProject.length + 1);
}

function dirname(path) {
  const text = String(path || '').replace(/\\/g, '/');
  const idx = text.lastIndexOf('/');
  return idx >= 0 ? text.slice(0, idx) : '';
}

function normalizeRelPath(path) {
  const parts = [];
  String(path || '').replace(/\\/g, '/').split('/').forEach((part) => {
    if (!part || part === '.') return;
    if (part === '..') parts.pop();
    else parts.push(part);
  });
  return parts.join('/');
}

function line(ctx, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1 + 0.5, y1 + 0.5);
  ctx.lineTo(x2 + 0.5, y2 + 0.5);
  ctx.stroke();
}

function colorForTile(gid) {
  const hue = (gid * 47) % 360;
  return `hsl(${hue} 52% 46%)`;
}

function structuredCloneSafe(value) {
  try {
    return structuredClone(value);
  } catch (_) {
    return JSON.parse(JSON.stringify(value));
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
