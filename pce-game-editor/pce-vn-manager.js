'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const assetManager = require('./pce-asset-manager');

const VN_SCENE_FILE = path.join('assets', 'pce-vn-scenes.json');
const GLYPH_END = 0xff;
const DEFAULT_FONT_TILE_BASE = 168;

function ensureDirSync(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function normalizeRelativePath(value) {
  return String(value || '').replace(/\\/g, '/').replace(/^\/+/, '');
}

function getSceneFilePath(projectDir) {
  return path.join(projectDir, VN_SCENE_FILE);
}

function safeId(value, fallback) {
  const id = String(value || '').trim().replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '');
  return id || fallback;
}

function firstAssetId(assets, type) {
  const found = assets.find((asset) => asset.type === type);
  return found ? found.id : '';
}

function defaultSceneDocument(assetDoc = { assets: [] }) {
  const assets = Array.isArray(assetDoc.assets) ? assetDoc.assets : [];
  const backgroundAssetId = firstAssetId(assets, 'image');
  const characterAssetId = firstAssetId(assets, 'sprite');
  const bgmAssetId = firstAssetId(assets, 'cdda-track') || firstAssetId(assets, 'psg-song');
  const voiceAssetId = firstAssetId(assets, 'adpcm');
  return {
    version: 1,
    startScene: 'opening',
    scenes: [
      {
        id: 'opening',
        backgroundAssetId,
        characters: characterAssetId ? [{ assetId: characterAssetId, x: 176, y: 72, pose: 'default' }] : [],
        bgmAssetId,
        nextSceneId: '',
        messages: [
          {
            speaker: 'アカリ',
            text: 'こんにちは、PCエンジンの世界へ。',
            voiceAssetId,
            advanceMode: 'button',
          },
          {
            speaker: 'アカリ',
            text: 'CD-DAとADPCMを再生中です。',
            voiceAssetId: '',
            advanceMode: 'button',
          },
          {
            speaker: 'アカリ',
            text: 'ボタンでメッセージを送ります。',
            voiceAssetId: '',
            advanceMode: 'button',
          },
        ],
      },
    ],
  };
}

function assetIdsByType(assetDoc = { assets: [] }) {
  const result = {
    image: new Set(),
    sprite: new Set(),
    'psg-song': new Set(),
    'psg-sfx': new Set(),
    adpcm: new Set(),
    'cdda-track': new Set(),
  };
  (assetDoc.assets || []).forEach((asset) => {
    if (result[asset.type]) result[asset.type].add(asset.id);
  });
  return result;
}

function normalizeMessage(message = {}, index = 0, valid = assetIdsByType()) {
  const raw = message && typeof message === 'object' ? message : {};
  const voiceAssetId = String(raw.voiceAssetId || '').trim();
  return {
    speaker: String(raw.speaker || '').trim().slice(0, 16),
    text: String(raw.text || (index === 0 ? 'メッセージを入力してください。' : '')).trim().slice(0, 96),
    voiceAssetId: valid.adpcm?.has(voiceAssetId) ? voiceAssetId : '',
    advanceMode: String(raw.advanceMode || 'button') === 'auto' ? 'auto' : 'button',
  };
}

function normalizeCharacter(character = {}, valid = assetIdsByType()) {
  const raw = character && typeof character === 'object' ? character : {};
  const assetId = String(raw.assetId || '').trim();
  if (!valid.sprite?.has(assetId)) return null;
  const x = Math.max(0, Math.min(255, Math.round(Number(raw.x) || 176)));
  const y = Math.max(0, Math.min(255, Math.round(Number(raw.y) || 72)));
  return {
    assetId,
    x,
    y,
    pose: String(raw.pose || 'default').trim().slice(0, 32) || 'default',
  };
}

function normalizeScene(scene = {}, index = 0, valid = assetIdsByType(), assetDoc = { assets: [] }) {
  const raw = scene && typeof scene === 'object' ? scene : {};
  const backgroundAssetId = String(raw.backgroundAssetId || '').trim();
  const bgmAssetId = String(raw.bgmAssetId || '').trim();
  const fallback = defaultSceneDocument(assetDoc).scenes[0];
  const messages = Array.isArray(raw.messages) && raw.messages.length
    ? raw.messages.map((message, msgIndex) => normalizeMessage(message, msgIndex, valid)).filter((message) => message.text)
    : fallback.messages.map((message, msgIndex) => normalizeMessage(message, msgIndex, valid));
  const characters = (Array.isArray(raw.characters) ? raw.characters : fallback.characters)
    .map((character) => normalizeCharacter(character, valid))
    .filter(Boolean)
    .slice(0, 4);
  return {
    id: safeId(raw.id, index === 0 ? 'opening' : `scene_${index + 1}`),
    backgroundAssetId: valid.image?.has(backgroundAssetId) ? backgroundAssetId : firstAssetId(assetDoc.assets || [], 'image'),
    characters,
    messages,
    bgmAssetId: valid['cdda-track']?.has(bgmAssetId) || valid['psg-song']?.has(bgmAssetId) ? bgmAssetId : firstAssetId(assetDoc.assets || [], 'cdda-track'),
    nextSceneId: safeId(raw.nextSceneId, ''),
  };
}

function normalizeSceneDocument(doc = {}, assetDoc = { assets: [] }) {
  const raw = doc && typeof doc === 'object' ? doc : {};
  const valid = assetIdsByType(assetDoc);
  const scenes = Array.isArray(raw.scenes) && raw.scenes.length
    ? raw.scenes.map((scene, index) => normalizeScene(scene, index, valid, assetDoc))
    : defaultSceneDocument(assetDoc).scenes.map((scene, index) => normalizeScene(scene, index, valid, assetDoc));
  const ids = new Set();
  const deduped = scenes.map((scene, index) => {
    let id = scene.id;
    if (ids.has(id)) id = `${id}_${index + 1}`;
    ids.add(id);
    return { ...scene, id };
  });
  const startScene = deduped.some((scene) => scene.id === raw.startScene)
    ? raw.startScene
    : (deduped[0]?.id || 'opening');
  const sceneIds = new Set(deduped.map((scene) => scene.id));
  const normalizedScenes = deduped.map((scene) => ({
    ...scene,
    nextSceneId: scene.nextSceneId && sceneIds.has(scene.nextSceneId) ? scene.nextSceneId : '',
  }));
  return {
    version: 1,
    startScene,
    scenes: normalizedScenes,
  };
}

function readSceneDocument(projectDir) {
  const assetDoc = assetManager.readAssetDocument(projectDir);
  const scenePath = getSceneFilePath(projectDir);
  if (!fs.existsSync(scenePath)) return normalizeSceneDocument(defaultSceneDocument(assetDoc), assetDoc);
  try {
    return normalizeSceneDocument(JSON.parse(fs.readFileSync(scenePath, 'utf-8')), assetDoc);
  } catch (_) {
    return normalizeSceneDocument(defaultSceneDocument(assetDoc), assetDoc);
  }
}

function writeSceneDocument(projectDir, doc) {
  const assetDoc = assetManager.readAssetDocument(projectDir);
  const normalized = normalizeSceneDocument(doc, assetDoc);
  const scenePath = getSceneFilePath(projectDir);
  ensureDirSync(path.dirname(scenePath));
  fs.writeFileSync(scenePath, JSON.stringify(normalized, null, 2), 'utf-8');
  return normalized;
}

function ensureSceneFile(projectDir) {
  const scenePath = getSceneFilePath(projectDir);
  if (fs.existsSync(scenePath)) return readSceneDocument(projectDir);
  return writeSceneDocument(projectDir, defaultSceneDocument(assetManager.readAssetDocument(projectDir)));
}

function messageDisplayText(message) {
  const speaker = String(message.speaker || '').trim();
  const text = String(message.text || '').trim();
  return speaker ? `${speaker}「${text}」` : text;
}

function collectGlyphs(doc) {
  const glyphs = [' '];
  const seen = new Set(glyphs);
  (doc.scenes || []).forEach((scene) => {
    (scene.messages || []).forEach((message) => {
      for (const char of messageDisplayText(message)) {
        if (!seen.has(char)) {
          seen.add(char);
          glyphs.push(char);
        }
      }
    });
  });
  return glyphs.slice(0, 254);
}

function fontCandidates() {
  const candidates = [
    path.join('/Library', 'Fonts', 'Arial Unicode.ttf'),
    path.join('/System', 'Library', 'Fonts', 'Hiragino Sans GB.ttc'),
    path.join('/System', 'Library', 'Fonts', 'CJKSymbolsFallback.ttc'),
    'C:\\Windows\\Fonts\\msgothic.ttc',
    'C:\\Windows\\Fonts\\meiryo.ttc',
  ];
  try {
    const systemFonts = path.join('/System', 'Library', 'Fonts');
    fs.readdirSync(systemFonts)
      .filter((fileName) => /ヒラ.*角|Hiragino/i.test(fileName))
      .forEach((fileName) => candidates.unshift(path.join(systemFonts, fileName)));
  } catch (_) {}
  return Array.from(new Set(candidates)).filter((candidate) => fs.existsSync(candidate));
}

function fallbackGlyphBitmap(glyph, glyphIndex) {
  const bitmap = new Array(256).fill(0);
  if (glyph === ' ') return bitmap;
  for (let y = 1; y < 15; y += 1) {
    for (let x = 1; x < 15; x += 1) {
      const border = x === 1 || x === 14 || y === 1 || y === 14;
      const pattern = ((x * 17 + y * 31 + glyph.charCodeAt(0) + glyphIndex) % 7) === 0;
      bitmap[(y * 16) + x] = border || pattern ? 1 : 0;
    }
  }
  return bitmap;
}

function renderGlyphBitmapsWithPython(glyphs) {
  const candidates = fontCandidates();
  if (!candidates.length) return null;
  const script = String.raw`
import json, sys
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    raise SystemExit(0)

payload = json.load(sys.stdin)
font = None
for font_path in payload.get("fontPaths", []):
    try:
        font = ImageFont.truetype(font_path, 16)
        break
    except Exception:
        pass
if font is None:
    print(json.dumps({"ok": False, "error": "font not found"}))
    raise SystemExit(0)

bitmaps = []
for glyph in payload.get("glyphs", []):
    img = Image.new("L", (16, 16), 0)
    if glyph != " ":
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), glyph, font=font)
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        x = (16 - width) // 2 - bbox[0]
        y = (16 - height) // 2 - bbox[1]
        draw.text((x, y), glyph, fill=255, font=font)
    bitmaps.append([1 if value >= 96 else 0 for value in img.getdata()])
print(json.dumps({"ok": True, "bitmaps": bitmaps}, ensure_ascii=False))
`;
  const proc = spawnSync('python3', ['-c', script], {
    input: JSON.stringify({ glyphs, fontPaths: candidates }),
    encoding: 'utf-8',
    maxBuffer: 1024 * 1024 * 4,
  });
  if (proc.status !== 0 || !proc.stdout) return null;
  try {
    const parsed = JSON.parse(proc.stdout);
    if (parsed.ok && Array.isArray(parsed.bitmaps) && parsed.bitmaps.length === glyphs.length) {
      return parsed.bitmaps;
    }
  } catch (_) {}
  return null;
}

function encode8x8Tile(bitmap, offsetX, offsetY) {
  const bytes = [];
  for (let y = 0; y < 8; y += 1) {
    const planes = [0, 0, 0, 0];
    for (let x = 0; x < 8; x += 1) {
      const value = bitmap[((offsetY + y) * 16) + offsetX + x] ? 15 : 0;
      for (let plane = 0; plane < 4; plane += 1) {
        if (value & (1 << plane)) planes[plane] |= (1 << (7 - x));
      }
    }
    bytes.push(planes[0], planes[1], planes[2], planes[3]);
  }
  return bytes;
}

function encodeGlyphTileData(bitmaps) {
  const bytes = [];
  bitmaps.forEach((bitmap) => {
    bytes.push(...encode8x8Tile(bitmap, 0, 0));
    bytes.push(...encode8x8Tile(bitmap, 8, 0));
    bytes.push(...encode8x8Tile(bitmap, 0, 8));
    bytes.push(...encode8x8Tile(bitmap, 8, 8));
  });
  return Buffer.from(bytes);
}

function renderGlyphTileData(glyphs) {
  const rendered = renderGlyphBitmapsWithPython(glyphs)
    || glyphs.map((glyph, index) => fallbackGlyphBitmap(glyph, index));
  return encodeGlyphTileData(rendered);
}

function toCIdentifier(value) {
  return String(value || 'vn')
    .replace(/[^a-zA-Z0-9_]+/g, '_')
    .replace(/^([0-9])/, '_$1') || 'vn';
}

function bytesToCArray(name, buffer, qualifier = 'static const unsigned char') {
  const lines = [`${qualifier} ${name}[] = {`];
  for (let i = 0; i < buffer.length; i += 14) {
    const chunk = Array.from(buffer.subarray(i, i + 14)).map((value) => `0x${value.toString(16).padStart(2, '0')}`);
    lines.push(`  ${chunk.join(', ')}${i + 14 < buffer.length ? ',' : ''}`);
  }
  lines.push('};');
  return lines;
}

function indexAssets(assets, type) {
  const map = new Map();
  assets.filter((asset) => asset.type === type).forEach((asset, index) => map.set(asset.id, index));
  return map;
}

function psgOrCddaTrack(assetDoc, assetId) {
  const asset = (assetDoc.assets || []).find((entry) => entry.id === assetId);
  if (!asset) return 0;
  if (asset.type === 'cdda-track') return Math.max(2, Math.min(99, Number(asset.options?.track) || 2));
  return 0;
}

function generateVnSources(projectDir, options = {}) {
  const assetDoc = assetManager.readAssetDocument(projectDir);
  const doc = writeSceneDocument(projectDir, readSceneDocument(projectDir));
  const glyphs = collectGlyphs(doc);
  const glyphIndex = new Map(glyphs.map((glyph, index) => [glyph, index]));
  const fontTiles = renderGlyphTileData(glyphs);
  const imageIndex = indexAssets(assetDoc.assets || [], 'image');
  const spriteIndex = indexAssets(assetDoc.assets || [], 'sprite');
  const adpcmIndex = indexAssets(assetDoc.assets || [], 'adpcm');
  const sceneIndex = new Map(doc.scenes.map((scene, index) => [scene.id, index]));
  const generatedDir = path.join(projectDir, 'src', 'generated');
  ensureDirSync(generatedDir);

  const messageArrays = [];
  const messageMeta = [];
  const characterArrays = [];
  const sceneMeta = [];
  let messageCount = 0;

  doc.scenes.forEach((scene, sceneIdx) => {
    const sceneMessages = scene.messages || [];
    const firstMessage = messageCount;
    sceneMessages.forEach((message) => {
      const bytes = [];
      for (const glyph of messageDisplayText(message)) {
        bytes.push(glyphIndex.get(glyph) ?? 0);
      }
      bytes.push(GLYPH_END);
      const name = `pce_vn_message_${messageCount}_glyphs`;
      messageArrays.push(...bytesToCArray(name, Buffer.from(bytes)));
      messageArrays.push('');
      const voiceIndex = message.voiceAssetId && adpcmIndex.has(message.voiceAssetId)
        ? adpcmIndex.get(message.voiceAssetId)
        : -1;
      messageMeta.push(`  { ${name}, ${Math.max(0, bytes.length - 1)}u, ${voiceIndex} }${messageCount + 1 < 255 ? ',' : ''}`);
      messageCount += 1;
    });
    const chars = (scene.characters || []).filter((character) => spriteIndex.has(character.assetId)).slice(0, 4);
    const charArrayName = `pce_vn_scene_${sceneIdx}_characters`;
    if (chars.length) {
      characterArrays.push(`static const pce_vn_character_t ${charArrayName}[] = {`);
      chars.forEach((character, index) => {
        characterArrays.push(`  { ${spriteIndex.get(character.assetId)}u, ${character.x}u, ${character.y}u }${index + 1 < chars.length ? ',' : ''}`);
      });
      characterArrays.push('};');
      characterArrays.push('');
    }
    const next = scene.nextSceneId && sceneIndex.has(scene.nextSceneId) ? sceneIndex.get(scene.nextSceneId) : -1;
    const bgIndex = imageIndex.has(scene.backgroundAssetId) ? imageIndex.get(scene.backgroundAssetId) : 0;
    const cddaTrack = psgOrCddaTrack(assetDoc, scene.bgmAssetId);
    sceneMeta.push(`  { ${bgIndex}u, ${chars.length ? charArrayName : '(const pce_vn_character_t *)0'}, ${chars.length}u, ${firstMessage}u, ${sceneMessages.length}u, ${cddaTrack}u, ${next} }${sceneIdx + 1 < doc.scenes.length ? ',' : ''}`);
  });

  const headerPath = path.join(generatedDir, 'vn.h');
  const sourcePath = path.join(generatedDir, 'vn.c');
  const header = [
    '#ifndef PCE_EDITOR_GENERATED_VN_H',
    '#define PCE_EDITOR_GENERATED_VN_H',
    '',
    'typedef struct {',
    '  unsigned char sprite_index;',
    '  unsigned char x;',
    '  unsigned char y;',
    '} pce_vn_character_t;',
    '',
    'typedef struct {',
    '  const unsigned char *glyphs;',
    '  unsigned char glyph_count;',
    '  signed char voice_index;',
    '} pce_vn_message_t;',
    '',
    'typedef struct {',
    '  unsigned char bg_index;',
    '  const pce_vn_character_t *characters;',
    '  unsigned char character_count;',
    '  unsigned char message_start;',
    '  unsigned char message_count;',
    '  unsigned char cdda_track;',
    '  signed char next_scene;',
    '} pce_vn_scene_t;',
    '',
    `#define PCE_VN_FONT_TILE_BASE ${Number(options.fontTileBase || DEFAULT_FONT_TILE_BASE)}u`,
    '#define PCE_VN_GLYPH_END 0xffu',
    '',
    'extern const unsigned char pce_vn_font_tiles[];',
    'extern const unsigned char pce_vn_font_glyph_count;',
    'extern const pce_vn_message_t pce_vn_messages[];',
    'extern const unsigned char pce_vn_message_count;',
    'extern const pce_vn_scene_t pce_vn_scenes[];',
    'extern const unsigned char pce_vn_scene_count;',
    'extern const unsigned char pce_vn_start_scene;',
    '',
    '#endif',
    '',
  ];
  const startScene = sceneIndex.get(doc.startScene) || 0;
  const source = [
    '#include "vn.h"',
    '',
    ...bytesToCArray('pce_vn_font_tiles', fontTiles, 'const unsigned char'),
    `const unsigned char pce_vn_font_glyph_count = ${glyphs.length};`,
    '',
    ...messageArrays,
    ...characterArrays,
    'const pce_vn_message_t pce_vn_messages[] = {',
    ...(messageMeta.length ? messageMeta.map((line, index) => line.replace(/,$/, index + 1 < messageMeta.length ? ',' : '')) : ['  { (const unsigned char *)0, 0u, -1 }']),
    '};',
    `const unsigned char pce_vn_message_count = ${messageCount};`,
    '',
    'const pce_vn_scene_t pce_vn_scenes[] = {',
    ...sceneMeta,
    '};',
    `const unsigned char pce_vn_scene_count = ${doc.scenes.length};`,
    `const unsigned char pce_vn_start_scene = ${startScene}u;`,
    '',
  ];
  fs.writeFileSync(headerPath, header.join('\n'), 'utf-8');
  fs.writeFileSync(sourcePath, source.join('\n'), 'utf-8');
  return {
    scenePath: getSceneFilePath(projectDir),
    headerPath,
    sourcePath,
    glyphCount: glyphs.length,
    messageCount,
    sceneCount: doc.scenes.length,
  };
}

function collectCdDataFiles(projectDir) {
  const doc = assetManager.readAssetDocument(projectDir);
  return (doc.assets || [])
    .filter((asset) => asset.type === 'adpcm')
    .map((asset) => normalizeRelativePath(asset.data?.generated?.outputFile || ''))
    .filter(Boolean)
    .filter((relativePath) => fs.existsSync(path.join(projectDir, relativePath)));
}

function collectCddaTracks(projectDir) {
  const doc = assetManager.readAssetDocument(projectDir);
  return (doc.assets || [])
    .filter((asset) => asset.type === 'cdda-track')
    .map((asset) => normalizeRelativePath(asset.data?.generated?.outputFile || asset.source || ''))
    .filter(Boolean)
    .filter((relativePath) => fs.existsSync(path.join(projectDir, relativePath)));
}

function prepareVisualNovelBuild(projectDir, config = {}) {
  ensureSceneFile(projectDir);
  const generated = generateVnSources(projectDir);
  const dataFiles = collectCdDataFiles(projectDir);
  const cddaTracks = collectCddaTracks(projectDir);
  const cd = config.cd && typeof config.cd === 'object' ? config.cd : {};
  const mergedDataFiles = Array.from(new Set([...(Array.isArray(cd.dataFiles) ? cd.dataFiles : []), ...dataFiles]));
  const mergedCddaTracks = Array.from(new Set([...(Array.isArray(cd.cddaTracks) ? cd.cddaTracks : []), ...cddaTracks]));
  return {
    ok: true,
    generated,
    configPatch: {
      toolchain: 'llvm-mos',
      targetMedia: 'cd',
      cd: {
        ...cd,
        dataFiles: mergedDataFiles,
        cddaTracks: mergedCddaTracks,
      },
      pluginSettings: {
        ...(config.pluginSettings || {}),
        'pce-sample-builder': {
          ...(config.pluginSettings?.['pce-sample-builder'] || {}),
          sample: 'visual-novel-cd',
        },
      },
    },
  };
}

module.exports = {
  VN_SCENE_FILE,
  DEFAULT_FONT_TILE_BASE,
  GLYPH_END,
  collectGlyphs,
  defaultSceneDocument,
  encodeGlyphTileData,
  ensureSceneFile,
  generateVnSources,
  getSceneFilePath,
  normalizeSceneDocument,
  prepareVisualNovelBuild,
  readSceneDocument,
  renderGlyphTileData,
  writeSceneDocument,
};
