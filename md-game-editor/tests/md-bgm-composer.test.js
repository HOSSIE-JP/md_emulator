'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const pluginDir = path.join(__dirname, '..', 'plugins', 'md-bgm-composer');
const composer = require(path.join(pluginDir, 'index.js'));
const core = require(path.join(pluginDir, 'music-core.js'));

function vlq(value) {
  let buffer = value & 0x7F;
  let n = value >>> 7;
  while (n > 0) {
    buffer <<= 8;
    buffer |= ((n & 0x7F) | 0x80);
    n >>>= 7;
  }
  const out = [];
  for (;;) {
    out.push(buffer & 0xFF);
    if (buffer & 0x80) buffer >>>= 8;
    else break;
  }
  return Buffer.from(out.reverse());
}

function chunk(id, payload) {
  const header = Buffer.alloc(8);
  header.write(id, 0, 4, 'ascii');
  header.writeUInt32BE(payload.length, 4);
  return Buffer.concat([header, payload]);
}

function meta(delta, type, payload) {
  return Buffer.concat([vlq(delta), Buffer.from([0xFF, type]), vlq(payload.length), payload]);
}

function midi(delta, bytes) {
  return Buffer.concat([vlq(delta), Buffer.from(bytes)]);
}

function makeMidiFixture() {
  const header = Buffer.alloc(6);
  header.writeUInt16BE(1, 0);
  header.writeUInt16BE(2, 2);
  header.writeUInt16BE(96, 4);

  const tempoTrack = Buffer.concat([
    meta(0, 0x03, Buffer.from('Tempo')),
    meta(0, 0x51, Buffer.from([0x07, 0xA1, 0x20])),
    meta(0, 0x2F, Buffer.alloc(0)),
  ]);

  const noteTrack = Buffer.concat([
    meta(0, 0x03, Buffer.from('Lead')),
    midi(0, [0xC0, 0x10]),
    midi(0, [0xB0, 0x07, 0x64]),
    midi(0, [0x90, 60, 100]),
    midi(24, [0xE0, 0x00, 0x50]),
    midi(72, [0x80, 60, 0]),
    meta(0, 0x2F, Buffer.alloc(0)),
  ]);

  return Buffer.concat([
    chunk('MThd', header),
    chunk('MTrk', tempoTrack),
    chunk('MTrk', noteTrack),
  ]);
}

test('md-bgm-composer declares renderer and main hook capabilities', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(pluginDir, 'manifest.json'), 'utf-8'));
  const rendererSource = fs.readFileSync(path.join(pluginDir, 'renderer.js'), 'utf-8');

  assert.deepEqual(manifest.types, ['editor', 'converter', 'asset']);
  assert.deepEqual(manifest.dependencies, ['midi-converter']);
  assert.equal(manifest.tab.page, 'md-bgm-composer');
  assert.deepEqual(manifest.mainApi.hooks, ['importMidi', 'exportMusic', 'validateSong']);
  assert.ok(manifest.renderer.capabilities.includes('page'));
  assert.ok(manifest.renderer.capabilities.includes('md-bgm-composer'));
  assert.ok(manifest.renderer.capabilities.includes('music-import-handler'));
  assert.match(rendererSource, /registerCapability\(['"]md-bgm-composer['"]/);
  assert.match(rendererSource, /registerCapability\(['"]music-import-handler['"]/);
  assert.match(rendererSource, /api\.capabilities\.get\(['"]midi-convert-ui['"]\)/);
  assert.match(rendererSource, /convertMidiMusic/);
  assert.doesNotMatch(rendererSource, /window\.prompt|window\.alert|window\.confirm/);
});

test('MIDI parser reads format 1 tempo, program, CC, pitch bend, and notes', () => {
  const parsed = core.parseMidi(makeMidiFixture());

  assert.equal(parsed.format, 1);
  assert.equal(parsed.ticksPerQuarter, 96);
  assert.equal(parsed.tracks.length, 2);
  assert.ok(parsed.tracks[0].events.some((event) => event.type === 'tempo'));
  assert.ok(parsed.tracks[1].events.some((event) => event.type === 'programChange' && event.program === 0x10));
  assert.ok(parsed.tracks[1].events.some((event) => event.type === 'controlChange' && event.controller === 7));
  assert.ok(parsed.tracks[1].events.some((event) => event.type === 'pitchBend'));
  assert.ok(parsed.tracks[1].events.some((event) => event.type === 'noteOn' && event.note === 60));
});

test('MIDI import builds an XGM2-safe song and reports lossy conversions', () => {
  const imported = core.convertMidiToSong(core.parseMidi(makeMidiFixture()), {
    title: 'Lead Theme',
    symbol: 'lead_theme',
  });

  assert.equal(imported.song.symbol, 'lead_theme');
  assert.equal(imported.song.tempo, 120);
  assert.equal(imported.allocations[0].target, 'FM1');
  assert.equal(imported.song.patterns[0].rows[0].cells.FM1.note, 'C4');
  assert.ok(imported.diagnostics.some((diag) => diag.code === 'pitch-bend-ignored'));

  const remapped = core.convertMidiToSong(core.parseMidi(makeMidiFixture()), {
    title: 'Lead Theme',
    symbol: 'lead_theme',
    allocations: [{ key: imported.allocations[0].key, target: 'PSG1' }],
  });
  assert.equal(remapped.allocations[0].target, 'PSG1');
  assert.equal(remapped.song.patterns[0].rows[0].cells.PSG1.note, 'C4');
});

test('channel allocator trims tracks that exceed FM/PSG/noise profile', () => {
  const diagnostics = [];
  const candidates = Array.from({ length: 11 }, (_, index) => ({
    key: `t${index}:0`,
    trackName: `Track ${index}`,
    midiChannel: index === 0 ? 9 : 0,
    notes: Array.from({ length: 4 }, () => ({ note: 60 })),
  }));

  const allocations = core.allocateMidiTracks(candidates, diagnostics);
  assert.equal(allocations.filter((entry) => entry.target === 'NOISE').length, 1);
  assert.equal(allocations.filter((entry) => entry.target === 'ignore').length, 2);
  assert.ok(diagnostics.some((diag) => diag.code === 'midi-track-overflow'));
});

test('VGM writer emits Mega Drive header, YM2612, PSG, waits, and end command', () => {
  const song = core.createDefaultSong({ symbol: 'test_bgm' });
  song.patterns[0].rows[0].cells.FM1 = { note: 'C4', midiNote: 60, instrument: 'fm_bell', volume: 12 };
  song.patterns[0].rows[1].cells.PSG1 = { note: 'E4', midiNote: 64, instrument: 'psg_square', volume: 10 };
  song.patterns[0].rows[2].cells.NOISE = { note: 'N', instrument: 'noise_kit', volume: 10 };

  const vgm = core.writeVgm(song);
  assert.equal(vgm.toString('ascii', 0, 4), 'Vgm ');
  assert.equal(vgm.readUInt32LE(0x0C), 3579545);
  assert.equal(vgm.readUInt32LE(0x2C), 7670454);
  assert.ok(vgm.includes(0x52));
  assert.ok(vgm.includes(0x50));
  assert.ok(vgm.includes(0x62));
  assert.equal(vgm[vgm.length - 1], 0x66);
});

test('export hook saves song and VGM, and reports missing xgmtool clearly', () => {
  const projectDir = fs.mkdtempSync(path.join(os.tmpdir(), 'md-bgm-composer-'));
  const song = core.createDefaultSong({ symbol: 'export_theme' });
  song.patterns[0].rows[0].cells.FM1 = { note: 'C4', midiNote: 60, instrument: 'fm_bell', volume: 12 };

  const result = composer.exportMusic({
    song,
    symbol: 'export_theme',
    xgmToolPath: path.join(projectDir, 'missing-xgmtool.exe'),
    outputs: { xgm: true, registerAsset: true },
  }, { projectDir });

  assert.equal(result.ok, true);
  assert.equal(result.files.json, 'res/music/export_theme.mdbgm.json');
  assert.equal(result.files.vgm, 'res/music/export_theme.vgm');
  assert.equal(result.asset.type, 'XGM2');
  assert.equal(result.asset.sourcePath, 'music/export_theme.vgm');
  assert.ok(result.warnings.some((warning) => warning.includes('xgmtool')));
  assert.ok(fs.existsSync(path.join(projectDir, 'res', 'music', 'export_theme.mdbgm.json')));
  assert.ok(fs.existsSync(path.join(projectDir, 'res', 'music', 'export_theme.vgm')));
});
