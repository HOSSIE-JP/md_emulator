export const DEFAULT_TILEMAP = {
  name: 'map001',
  width: 40,
  height: 28,
  tileWidth: 8,
  tileHeight: 8,
  tilesetName: 'tileset001',
  tilesetImage: 'tileset001.png',
  tilesetColumns: 1,
  tilesetTileCount: 1,
  layers: [
    { name: 'Ground', visible: true, opacity: 1, priority: false, data: [] },
  ],
};

export function normalizeSymbolName(value, fallback = 'map001') {
  return String(value || '')
    .replace(/\.[^.]+$/, '')
    .replace(/[^A-Za-z0-9_]/g, '_')
    .replace(/^[^A-Za-z_]+/, '')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase() || fallback;
}

export function createBlankTilemap(options = {}) {
  const width = clampInt(options.width, 1, 512, DEFAULT_TILEMAP.width);
  const height = clampInt(options.height, 1, 512, DEFAULT_TILEMAP.height);
  const tileWidth = clampInt(options.tileWidth, 8, 64, DEFAULT_TILEMAP.tileWidth);
  const tileHeight = clampInt(options.tileHeight, 8, 64, DEFAULT_TILEMAP.tileHeight);
  const name = normalizeSymbolName(options.name, DEFAULT_TILEMAP.name);
  const tilesetName = normalizeSymbolName(options.tilesetName || `${name}_tiles`, 'tileset001');
  const baseLayer = {
    name: String(options.layerName || 'Ground'),
    visible: true,
    opacity: 1,
    priority: false,
    data: new Array(width * height).fill(0),
  };
  return {
    ...DEFAULT_TILEMAP,
    name,
    width,
    height,
    tileWidth,
    tileHeight,
    tilesetName,
    tilesetImage: `${tilesetName}.png`,
    tilesetColumns: 1,
    tilesetTileCount: 1,
    layers: [baseLayer],
    warnings: [],
  };
}

export function escapeXml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function unescapeXml(value) {
  return String(value ?? '')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&');
}

export function buildTsx(map) {
  const tileWidth = clampInt(map.tileWidth, 1, 1024, DEFAULT_TILEMAP.tileWidth);
  const tileHeight = clampInt(map.tileHeight, 1, 1024, DEFAULT_TILEMAP.tileHeight);
  const columns = Math.max(1, Number(map.tilesetColumns) || 1);
  const tileCount = Math.max(1, Number(map.tilesetTileCount) || columns);
  const image = String(map.tilesetImage || `${map.tilesetName || 'tileset001'}.png`);
  const width = Math.max(tileWidth, Number(map.tilesetImageWidth) || columns * tileWidth);
  const rows = Math.max(1, Math.ceil(tileCount / columns));
  const height = Math.max(tileHeight, Number(map.tilesetImageHeight) || rows * tileHeight);

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<tileset version="1.10" tiledversion="1.10.2" name="${escapeXml(map.tilesetName || 'tileset001')}" tilewidth="${tileWidth}" tileheight="${tileHeight}" tilecount="${tileCount}" columns="${columns}">`,
    ` <image source="${escapeXml(image)}" width="${width}" height="${height}"/>`,
    '</tileset>',
    '',
  ].join('\n');
}

export function buildTmx(map) {
  const width = clampInt(map.width, 1, 4096, DEFAULT_TILEMAP.width);
  const height = clampInt(map.height, 1, 4096, DEFAULT_TILEMAP.height);
  const tileWidth = clampInt(map.tileWidth, 1, 1024, DEFAULT_TILEMAP.tileWidth);
  const tileHeight = clampInt(map.tileHeight, 1, 1024, DEFAULT_TILEMAP.tileHeight);
  const tilesetSource = String(map.tilesetSource || `../tilesets/${map.tilesetName || 'tileset001'}.tsx`);
  const layers = normalizeLayers(map.layers, width, height);
  const parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="${width}" height="${height}" tilewidth="${tileWidth}" tileheight="${tileHeight}" infinite="0" nextlayerid="${layers.length + 1}" nextobjectid="1">`,
    ` <tileset firstgid="1" source="${escapeXml(tilesetSource)}"/>`,
  ];

  layers.forEach((layer, index) => {
    const visible = layer.visible === false ? ' visible="0"' : '';
    const opacity = Number(layer.opacity);
    const opacityAttr = Number.isFinite(opacity) && opacity >= 0 && opacity < 1 ? ` opacity="${opacity}"` : '';
    parts.push(` <layer id="${index + 1}" name="${escapeXml(layer.name)}" width="${width}" height="${height}"${visible}${opacityAttr}>`);
    parts.push('  <data encoding="csv">');
    parts.push(formatCsvLayer(layer.data, width, height));
    parts.push('  </data>');
    parts.push(' </layer>');
  });

  parts.push('</map>', '');
  return parts.join('\n');
}

export function parseTsx(text) {
  const root = matchTag(text, 'tileset');
  if (!root) throw new Error('TSX tileset element not found');
  const attrs = parseAttrs(root.attrs);
  const imageTag = matchSelfClosingTag(root.body, 'image');
  const imageAttrs = imageTag ? parseAttrs(imageTag.attrs) : {};
  return {
    tilesetName: attrs.name || 'tileset001',
    tileWidth: clampInt(attrs.tilewidth, 1, 1024, DEFAULT_TILEMAP.tileWidth),
    tileHeight: clampInt(attrs.tileheight, 1, 1024, DEFAULT_TILEMAP.tileHeight),
    tilesetTileCount: clampInt(attrs.tilecount, 1, 65535, 1),
    tilesetColumns: clampInt(attrs.columns, 1, 4096, 1),
    tilesetImage: imageAttrs.source || '',
    tilesetImageWidth: clampInt(imageAttrs.width, 1, 65535, 0),
    tilesetImageHeight: clampInt(imageAttrs.height, 1, 65535, 0),
  };
}

export function parseTmx(text) {
  const warnings = [];
  const root = matchTag(text, 'map');
  if (!root) throw new Error('TMX map element not found');
  const attrs = parseAttrs(root.attrs);
  if (attrs.orientation && attrs.orientation !== 'orthogonal') {
    warnings.push(`未対応 orientation: ${attrs.orientation}`);
  }
  if (attrs.infinite === '1') {
    warnings.push('infinite map は v1 では保存対象外です');
  }
  if (/<chunk\b/i.test(root.body)) {
    warnings.push('chunked layer data は v1 では保存対象外です');
  }
  if (/<objectgroup\b/i.test(root.body)) {
    warnings.push('object layer は v1.1 候補です。読み込み時は保持しません');
  }
  if (/<imagelayer\b/i.test(root.body) || /<group\b/i.test(root.body)) {
    warnings.push('image/group layer は v1 では保存対象外です');
  }

  const tilesetTag = matchSelfClosingTag(root.body, 'tileset') || matchTag(root.body, 'tileset');
  const tilesetAttrs = tilesetTag ? parseAttrs(tilesetTag.attrs) : {};
  const width = clampInt(attrs.width, 1, 4096, DEFAULT_TILEMAP.width);
  const height = clampInt(attrs.height, 1, 4096, DEFAULT_TILEMAP.height);
  const layers = [];
  const layerRe = /<layer\b([^>]*)>([\s\S]*?)<\/layer>/gi;
  let layerMatch;
  while ((layerMatch = layerRe.exec(root.body))) {
    const layerAttrs = parseAttrs(layerMatch[1]);
    const dataTag = matchTag(layerMatch[2], 'data');
    if (!dataTag) {
      warnings.push(`layer '${layerAttrs.name || ''}' に data がありません`);
      continue;
    }
    const dataAttrs = parseAttrs(dataTag.attrs);
    if (String(dataAttrs.encoding || '').toLowerCase() !== 'csv') {
      warnings.push(`layer '${layerAttrs.name || ''}' は CSV encoding ではありません`);
      continue;
    }
    if (dataAttrs.compression) {
      warnings.push(`layer '${layerAttrs.name || ''}' は compressed data です`);
      continue;
    }
    layers.push({
      name: layerAttrs.name || `Layer ${layers.length + 1}`,
      visible: layerAttrs.visible !== '0',
      opacity: Number(layerAttrs.opacity || 1),
      priority: /\s(priority|prio)$/i.test(layerAttrs.name || ''),
      data: normalizeLayerData(parseCsvLayer(dataTag.body), width, height),
    });
  }

  if (layers.length === 0) {
    layers.push({ name: 'Ground', visible: true, opacity: 1, priority: false, data: new Array(width * height).fill(0) });
  }

  return {
    name: 'map001',
    width,
    height,
    tileWidth: clampInt(attrs.tilewidth, 1, 1024, DEFAULT_TILEMAP.tileWidth),
    tileHeight: clampInt(attrs.tileheight, 1, 1024, DEFAULT_TILEMAP.tileHeight),
    tilesetSource: tilesetAttrs.source || '',
    tilesetName: sourceBaseName(tilesetAttrs.source || 'tileset001'),
    layers,
    warnings,
  };
}

export function formatCsvLayer(data, width, height) {
  const normalized = normalizeLayerData(data, width, height);
  const lines = [];
  for (let y = 0; y < height; y += 1) {
    const row = normalized.slice(y * width, y * width + width);
    lines.push(`   ${row.join(',')}${y === height - 1 ? '' : ','}`);
  }
  return lines.join('\n');
}

export function parseCsvLayer(text) {
  return String(text || '')
    .split(',')
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((value) => Number.isFinite(value) && value >= 0);
}

export function normalizeLayerData(data, width, height) {
  const size = Math.max(1, Number(width) || 1) * Math.max(1, Number(height) || 1);
  const out = new Array(size).fill(0);
  (Array.isArray(data) ? data : []).slice(0, size).forEach((value, index) => {
    out[index] = Math.max(0, Number.parseInt(value, 10) || 0);
  });
  return out;
}

export function normalizeLayers(layers, width, height) {
  const source = Array.isArray(layers) && layers.length ? layers : DEFAULT_TILEMAP.layers;
  return source.map((layer, index) => ({
    name: String(layer?.name || `Layer ${index + 1}`),
    visible: layer?.visible !== false,
    opacity: Number.isFinite(Number(layer?.opacity)) ? Number(layer.opacity) : 1,
    priority: !!layer?.priority,
    data: normalizeLayerData(layer?.data || [], width, height),
  }));
}

export function sourceBaseName(source) {
  return normalizeSymbolName(String(source || '').split(/[\\/]/).pop() || '', 'tileset001');
}

function parseAttrs(text) {
  const attrs = {};
  const re = /([A-Za-z_:][\w:.-]*)\s*=\s*"([^"]*)"/g;
  let match;
  while ((match = re.exec(String(text || '')))) {
    attrs[match[1]] = unescapeXml(match[2]);
  }
  return attrs;
}

function matchTag(text, tagName) {
  const re = new RegExp(`<${tagName}\\b([^>]*)>([\\s\\S]*?)<\\/${tagName}>`, 'i');
  const match = re.exec(String(text || ''));
  return match ? { attrs: match[1], body: match[2] } : null;
}

function matchSelfClosingTag(text, tagName) {
  const re = new RegExp(`<${tagName}\\b([^>]*)\\/>`, 'i');
  const match = re.exec(String(text || ''));
  return match ? { attrs: match[1], body: '' } : null;
}

function clampInt(value, min, max, fallback) {
  const n = Number.parseInt(value, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}
