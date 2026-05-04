'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROWS_PER_PATTERN = 64;
const DEFAULT_TICKS_PER_ROW = 6;
const SAMPLE_RATE_NTSC = 44100;

const CHANNELS = [
  { id: 'FM1', type: 'fm', label: 'FM1' },
  { id: 'FM2', type: 'fm', label: 'FM2' },
  { id: 'FM3', type: 'fm', label: 'FM3' },
  { id: 'FM4', type: 'fm', label: 'FM4' },
  { id: 'FM5', type: 'fm', label: 'FM5' },
  { id: 'PSG1', type: 'psg', label: 'PSG1' },
  { id: 'PSG2', type: 'psg', label: 'PSG2' },
  { id: 'PSG3', type: 'psg', label: 'PSG3' },
  { id: 'NOISE', type: 'noise', label: 'NOISE' },
];

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function makeDiagnostic(level, code, message, detail = {}) {
  return { level, code, message, detail };
}

function normalizeSymbolName(value) {
  const base = String(value || 'bgm')
    .replace(/\.[^.]+$/, '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_');
  const safe = base || 'bgm';
  return /^[a-z_]/.test(safe) ? safe : `bgm_${safe}`;
}

function midiNoteToName(note) {
  const n = Number(note);
  if (!Number.isFinite(n)) return '';
  const octave = Math.floor(n / 12) - 1;
  return `${NOTE_NAMES[((n % 12) + 12) % 12]}${octave}`;
}

function noteNameToMidi(noteName) {
  const match = String(noteName || '').trim().match(/^([A-G])(#?)(-?\d+)$/i);
  if (!match) return null;
  const name = `${match[1].toUpperCase()}${match[2] || ''}`;
  const index = NOTE_NAMES.indexOf(name);
  if (index < 0) return null;
  return (Number(match[3]) + 1) * 12 + index;
}

function createDefaultFmInstrument(id = 'fm_bell') {
  return {
    id,
    name: 'FM Bell',
    type: 'fm',
    algorithm: 4,
    feedback: 2,
    pan: 'center',
    operators: Array.from({ length: 4 }, () => ({
      tl: 32,
      ar: 31,
      dr: 12,
      sr: 0,
      rr: 8,
      sl: 4,
      detune: 0,
      multiple: 1,
    })),
  };
}

function createDefaultPsgInstrument(id = 'psg_square') {
  return {
    id,
    name: 'PSG Square',
    type: 'psg',
    volume: 10,
    envelope: 'hold',
    toneMode: 'square',
    noiseFrequency: 'clocked',
  };
}

function createEmptyRows() {
  return Array.from({ length: ROWS_PER_PATTERN }, () => ({ cells: {} }));
}

function createDefaultSong(options = {}) {
  const symbol = normalizeSymbolName(options.symbol || 'bgm_001');
  return {
    version: 1,
    title: String(options.title || 'New BGM'),
    artist: String(options.artist || ''),
    symbol,
    tempo: Number(options.tempo) || 150,
    speed: Number(options.speed) || DEFAULT_TICKS_PER_ROW,
    rowsPerPattern: ROWS_PER_PATTERN,
    channels: CHANNELS,
    order: [0],
    patterns: [{ id: 0, name: 'Pattern 00', rows: createEmptyRows() }],
    instruments: [
      createDefaultFmInstrument('fm_bell'),
      createDefaultPsgInstrument('psg_square'),
      { ...createDefaultPsgInstrument('noise_kit'), name: 'Noise Kit', type: 'noise' },
    ],
    metadata: {
      profile: 'xgm2-safe',
      createdBy: 'md-bgm-composer',
    },
  };
}

class ByteReader {
  constructor(buffer) {
    this.buffer = Buffer.from(buffer);
    this.offset = 0;
  }

  remaining() {
    return this.buffer.length - this.offset;
  }

  readUInt8() {
    if (this.remaining() < 1) throw new Error('Unexpected end of MIDI data');
    return this.buffer[this.offset++];
  }

  readUInt16BE() {
    if (this.remaining() < 2) throw new Error('Unexpected end of MIDI data');
    const value = this.buffer.readUInt16BE(this.offset);
    this.offset += 2;
    return value;
  }

  readUInt32BE() {
    if (this.remaining() < 4) throw new Error('Unexpected end of MIDI data');
    const value = this.buffer.readUInt32BE(this.offset);
    this.offset += 4;
    return value;
  }

  readAscii(length) {
    if (this.remaining() < length) throw new Error('Unexpected end of MIDI data');
    const value = this.buffer.toString('ascii', this.offset, this.offset + length);
    this.offset += length;
    return value;
  }

  readBytes(length) {
    if (this.remaining() < length) throw new Error('Unexpected end of MIDI data');
    const value = this.buffer.slice(this.offset, this.offset + length);
    this.offset += length;
    return value;
  }

  readVarLen() {
    let value = 0;
    for (let i = 0; i < 4; i += 1) {
      const byte = this.readUInt8();
      value = (value << 7) | (byte & 0x7F);
      if ((byte & 0x80) === 0) return value;
    }
    throw new Error('Invalid MIDI variable length value');
  }
}

function parseMidi(buffer) {
  const reader = new ByteReader(buffer);
  if (reader.readAscii(4) !== 'MThd') {
    throw new Error('MIDI header MThd が見つかりません。');
  }
  const headerLength = reader.readUInt32BE();
  if (headerLength < 6) {
    throw new Error('MIDI header が短すぎます。');
  }
  const format = reader.readUInt16BE();
  const trackCount = reader.readUInt16BE();
  const division = reader.readUInt16BE();
  if (headerLength > 6) reader.readBytes(headerLength - 6);
  if (division & 0x8000) {
    throw new Error('SMPTE time division の MIDI は MVP では未対応です。');
  }

  const ticksPerQuarter = division;
  const tracks = [];
  for (let trackIndex = 0; trackIndex < trackCount; trackIndex += 1) {
    const chunkId = reader.readAscii(4);
    const chunkLength = reader.readUInt32BE();
    const data = reader.readBytes(chunkLength);
    if (chunkId !== 'MTrk') continue;
    tracks.push(parseMidiTrack(data, trackIndex));
  }

  return { format, trackCount, ticksPerQuarter, tracks };
}

function parseMidiTrack(data, trackIndex) {
  const reader = new ByteReader(data);
  const events = [];
  let tick = 0;
  let runningStatus = 0;
  let name = `Track ${trackIndex + 1}`;

  while (reader.remaining() > 0) {
    tick += reader.readVarLen();
    let status = reader.readUInt8();
    if (status < 0x80) {
      if (!runningStatus) throw new Error('MIDI running status が不正です。');
      reader.offset -= 1;
      status = runningStatus;
    } else if (status < 0xF0) {
      runningStatus = status;
    }

    if (status === 0xFF) {
      const type = reader.readUInt8();
      const length = reader.readVarLen();
      const payload = reader.readBytes(length);
      if (type === 0x03) {
        name = payload.toString('utf-8') || name;
        events.push({ tick, type: 'trackName', name });
      } else if (type === 0x51 && payload.length === 3) {
        events.push({
          tick,
          type: 'tempo',
          microsecondsPerQuarter: (payload[0] << 16) | (payload[1] << 8) | payload[2],
        });
      } else if (type === 0x2F) {
        events.push({ tick, type: 'endOfTrack' });
        break;
      } else {
        events.push({ tick, type: 'meta', metaType: type, length });
      }
      continue;
    }

    if (status === 0xF0 || status === 0xF7) {
      reader.readBytes(reader.readVarLen());
      events.push({ tick, type: 'sysex' });
      continue;
    }

    const eventType = status & 0xF0;
    const channel = status & 0x0F;
    const data1 = reader.readUInt8();
    const needsData2 = eventType !== 0xC0 && eventType !== 0xD0;
    const data2 = needsData2 ? reader.readUInt8() : 0;

    if (eventType === 0x80 || (eventType === 0x90 && data2 === 0)) {
      events.push({ tick, type: 'noteOff', channel, note: data1, velocity: data2 });
    } else if (eventType === 0x90) {
      events.push({ tick, type: 'noteOn', channel, note: data1, velocity: data2 });
    } else if (eventType === 0xB0) {
      events.push({ tick, type: 'controlChange', channel, controller: data1, value: data2 });
    } else if (eventType === 0xC0) {
      events.push({ tick, type: 'programChange', channel, program: data1 });
    } else if (eventType === 0xE0) {
      events.push({ tick, type: 'pitchBend', channel, value: ((data2 << 7) | data1) - 8192 });
    } else {
      events.push({ tick, type: 'midi', status, channel, data1, data2 });
    }
  }

  return { index: trackIndex, name, events };
}

function extractNotes(track, diagnostics) {
  const active = new Map();
  const notes = [];
  const controls = [];
  const programs = new Map();

  for (const event of track.events) {
    if (event.type === 'programChange') {
      programs.set(event.channel, event.program);
    } else if (event.type === 'controlChange') {
      if (event.controller === 7 || event.controller === 10) controls.push(event);
      else diagnostics.push(makeDiagnostic('info', 'midi-cc-ignored', `CC ${event.controller} は import 診断のみ記録しました。`, { track: track.index }));
    } else if (event.type === 'pitchBend' && event.value !== 0) {
      diagnostics.push(makeDiagnostic('warn', 'pitch-bend-ignored', 'Pitch bend は MVP では近似せず破棄します。', { track: track.index, tick: event.tick }));
    } else if (event.type === 'noteOn') {
      const key = `${event.channel}:${event.note}`;
      const stack = active.get(key) || [];
      stack.push(event);
      active.set(key, stack);
    } else if (event.type === 'noteOff') {
      const key = `${event.channel}:${event.note}`;
      const stack = active.get(key) || [];
      const start = stack.shift();
      if (stack.length) active.set(key, stack);
      else active.delete(key);
      if (start) {
        notes.push({
          trackIndex: track.index,
          trackName: track.name,
          channel: event.channel,
          note: event.note,
          velocity: start.velocity,
          startTick: start.tick,
          endTick: Math.max(event.tick, start.tick + 1),
          program: programs.get(event.channel) ?? 0,
        });
      }
    }
  }

  active.forEach((stack) => {
    stack.forEach((event) => {
      diagnostics.push(makeDiagnostic('warn', 'dangling-note', 'Note off が見つからない音を短い音として取り込みました。', { track: track.index, tick: event.tick }));
      notes.push({
        trackIndex: track.index,
        trackName: track.name,
        channel: event.channel,
        note: event.note,
        velocity: event.velocity,
        startTick: event.tick,
        endTick: event.tick + 120,
        program: programs.get(event.channel) ?? 0,
      });
    });
  });

  return { notes, controls };
}

function convertMidiToSong(midi, options = {}) {
  const diagnostics = [];
  const title = String(options.title || 'Imported MIDI');
  const symbol = normalizeSymbolName(options.symbol || title);
  const tempoEvent = midi.tracks.flatMap((track) => track.events).find((event) => event.type === 'tempo');
  const tempo = tempoEvent ? Math.round(60000000 / tempoEvent.microsecondsPerQuarter) : 150;
  const ticksPerRow = Math.max(1, Math.round(midi.ticksPerQuarter / 4));
  const grouped = new Map();

  midi.tracks.forEach((track) => {
    const { notes } = extractNotes(track, diagnostics);
    notes.forEach((note) => {
      const key = `${note.trackIndex}:${note.channel}`;
      const current = grouped.get(key) || {
        key,
        trackIndex: note.trackIndex,
        trackName: note.trackName,
        midiChannel: note.channel,
        program: note.program,
        notes: [],
      };
      current.notes.push(note);
      grouped.set(key, current);
    });
  });

  const candidates = Array.from(grouped.values())
    .filter((entry) => entry.notes.length > 0)
    .sort((a, b) => b.notes.length - a.notes.length);
  const allocations = allocateMidiTracks(candidates, diagnostics);
  const overrides = Array.isArray(options.allocations) ? options.allocations : [];
  const overrideMap = new Map(overrides.map((entry) => [entry.key, entry.target]));
  allocations.forEach((allocation) => {
    if (overrideMap.has(allocation.key)) {
      allocation.target = overrideMap.get(allocation.key);
    }
  });
  const maxTick = candidates.reduce((max, entry) => Math.max(max, ...entry.notes.map((note) => note.endTick)), 0);
  const totalRows = Math.max(ROWS_PER_PATTERN, Math.ceil(maxTick / ticksPerRow) + 1);
  const patternCount = Math.max(1, Math.ceil(totalRows / ROWS_PER_PATTERN));
  const song = createDefaultSong({ title, symbol, tempo, speed: DEFAULT_TICKS_PER_ROW });
  song.order = Array.from({ length: patternCount }, (_, index) => index);
  song.patterns = song.order.map((id) => ({ id, name: `Pattern ${String(id).padStart(2, '0')}`, rows: createEmptyRows() }));
  song.metadata.midi = {
    format: midi.format,
    ticksPerQuarter: midi.ticksPerQuarter,
    ticksPerRow,
    allocations,
  };

  for (const allocation of allocations) {
    if (allocation.target === 'ignore') continue;
    const entry = candidates.find((candidate) => candidate.key === allocation.key);
    if (!entry) continue;
    const instrumentId = allocation.target.startsWith('FM') ? 'fm_bell' : allocation.target === 'NOISE' ? 'noise_kit' : 'psg_square';
    entry.notes.sort((a, b) => a.startTick - b.startTick).forEach((note) => {
      const absoluteRow = Math.max(0, Math.round(note.startTick / ticksPerRow));
      const pattern = song.patterns[Math.floor(absoluteRow / ROWS_PER_PATTERN)];
      const row = pattern?.rows[absoluteRow % ROWS_PER_PATTERN];
      if (!row) return;
      if (row.cells[allocation.target]?.note) {
        diagnostics.push(makeDiagnostic('warn', 'row-polyphony-trimmed', '同一 row/channel の重複音を 1 音に丸めました。', {
          row: absoluteRow,
          channel: allocation.target,
        }));
        return;
      }
      const volume = Math.max(1, Math.min(15, Math.round((note.velocity / 127) * 15)));
      row.cells[allocation.target] = {
        note: allocation.target === 'NOISE' ? 'N' : midiNoteToName(note.note),
        midiNote: note.note,
        instrument: instrumentId,
        volume,
        effect: '',
      };
    });
  }

  return { song, diagnostics, allocations };
}

function allocateMidiTracks(candidates, diagnostics = []) {
  const melodicTargets = ['FM1', 'FM2', 'FM3', 'FM4', 'FM5', 'PSG1', 'PSG2', 'PSG3'];
  const allocations = [];
  let melodicIndex = 0;
  let noiseUsed = false;

  for (const entry of candidates) {
    const isPercussion = entry.midiChannel === 9;
    if (isPercussion && !noiseUsed) {
      allocations.push({ key: entry.key, target: 'NOISE', trackName: entry.trackName, midiChannel: entry.midiChannel });
      noiseUsed = true;
      continue;
    }
    if (melodicIndex < melodicTargets.length) {
      allocations.push({ key: entry.key, target: melodicTargets[melodicIndex], trackName: entry.trackName, midiChannel: entry.midiChannel });
      melodicIndex += 1;
      continue;
    }
    diagnostics.push(makeDiagnostic('warn', 'midi-track-overflow', 'XGM2-safe profile の同時チャンネル数を超えた track を ignore にしました。', {
      trackName: entry.trackName,
      midiChannel: entry.midiChannel,
    }));
    allocations.push({ key: entry.key, target: 'ignore', trackName: entry.trackName, midiChannel: entry.midiChannel });
  }

  return allocations;
}

function validateSong(song) {
  const diagnostics = [];
  const knownChannels = new Set(CHANNELS.map((channel) => channel.id));
  const supportedEffects = new Set(['', 'volume', 'pan', 'arpeggio', 'portamento', 'vibrato', 'note-cut', 'tempo', 'speed']);

  if (!song || typeof song !== 'object') {
    return [makeDiagnostic('error', 'song-missing', 'song データがありません。')];
  }
  if (!Array.isArray(song.patterns) || song.patterns.length === 0) {
    diagnostics.push(makeDiagnostic('error', 'patterns-missing', 'pattern がありません。'));
  }
  if (!Array.isArray(song.order) || song.order.length === 0) {
    diagnostics.push(makeDiagnostic('error', 'order-missing', 'pattern order がありません。'));
  }

  for (const pattern of song.patterns || []) {
    (pattern.rows || []).forEach((row, rowIndex) => {
      Object.entries(row.cells || {}).forEach(([channelId, cell]) => {
        if (!knownChannels.has(channelId)) {
          diagnostics.push(makeDiagnostic('warn', 'unknown-channel', `未対応 channel ${channelId} は export されません。`, { pattern: pattern.id, row: rowIndex }));
          return;
        }
        const channel = CHANNELS.find((entry) => entry.id === channelId);
        if (channel.type !== 'noise') {
          const midiNote = cell.midiNote ?? noteNameToMidi(cell.note);
          if (midiNote == null) {
            diagnostics.push(makeDiagnostic('warn', 'invalid-note', `不正な note ${cell.note || ''} を無視します。`, { pattern: pattern.id, row: rowIndex, channelId }));
          } else if (midiNote < 24 || midiNote > 96) {
            diagnostics.push(makeDiagnostic('warn', 'note-range', `${channelId} の ${cell.note} は Mega Drive 向けの安全音域外です。`, { pattern: pattern.id, row: rowIndex, channelId }));
          }
        }
        if (!supportedEffects.has(String(cell.effect || ''))) {
          diagnostics.push(makeDiagnostic('warn', 'unsupported-effect', `${cell.effect} は MVP export では無視されます。`, { pattern: pattern.id, row: rowIndex, channelId }));
        }
      });
    });
  }

  return diagnostics;
}

function writeU32LE(buffer, offset, value) {
  buffer.writeUInt32LE(value >>> 0, offset);
}

function ymPortForChannel(channelId) {
  const index = Number(String(channelId).replace('FM', '')) - 1;
  if (index < 0 || index > 5) return null;
  return {
    port: index >= 3 ? 1 : 0,
    channel: index % 3,
  };
}

function fmFnumBlock(midiNote) {
  const note = Number(midiNote);
  const semitone = ((note % 12) + 12) % 12;
  const octave = Math.max(0, Math.min(7, Math.floor(note / 12) - 1));
  const base = [617, 654, 693, 734, 778, 824, 873, 925, 980, 1038, 1100, 1165][semitone];
  return { block: octave, fnum: base };
}

function pushYmWrite(commands, port, register, value) {
  commands.push(port ? 0x53 : 0x52, register & 0xFF, value & 0xFF);
}

function pushPsgWrite(commands, value) {
  commands.push(0x50, value & 0xFF);
}

function pushWaitFrame(commands) {
  commands.push(0x62);
}

function pushFmNote(commands, channelId, cell) {
  const mapped = ymPortForChannel(channelId);
  const midiNote = cell.midiNote ?? noteNameToMidi(cell.note);
  if (!mapped || midiNote == null) return;
  const { block, fnum } = fmFnumBlock(midiNote);
  const ch = mapped.channel;
  const port = mapped.port;
  const keyChannel = ch + (port ? 4 : 0);
  const panBits = cell.pan === 'left' ? 0x80 : cell.pan === 'right' ? 0x40 : 0xC0;
  pushYmWrite(commands, port, 0xB4 + ch, panBits | 0x30);
  pushYmWrite(commands, port, 0xA4 + ch, ((block & 0x07) << 3) | ((fnum >> 8) & 0x07));
  pushYmWrite(commands, port, 0xA0 + ch, fnum & 0xFF);
  pushYmWrite(commands, 0, 0x28, keyChannel);
  pushYmWrite(commands, 0, 0x28, 0xF0 | keyChannel);
}

function psgTonePeriod(midiNote) {
  const frequency = 440 * (2 ** ((Number(midiNote) - 69) / 12));
  return Math.max(1, Math.min(0x3FF, Math.round(3579545 / (32 * frequency))));
}

function pushPsgNote(commands, channelId, cell) {
  const channelIndex = channelId === 'PSG1' ? 0 : channelId === 'PSG2' ? 1 : channelId === 'PSG3' ? 2 : 3;
  const volume = Math.max(0, Math.min(15, 15 - (Number(cell.volume) || 10)));
  if (channelId === 'NOISE') {
    pushPsgWrite(commands, 0xE0 | 0x04);
    pushPsgWrite(commands, 0xF0 | volume);
    return;
  }
  const midiNote = cell.midiNote ?? noteNameToMidi(cell.note);
  if (midiNote == null) return;
  const period = psgTonePeriod(midiNote);
  pushPsgWrite(commands, 0x80 | (channelIndex << 5) | (period & 0x0F));
  pushPsgWrite(commands, (period >> 4) & 0x3F);
  pushPsgWrite(commands, 0x90 | (channelIndex << 5) | volume);
}

function buildVgmData(song) {
  const commands = [];
  pushYmWrite(commands, 0, 0x22, 0x00);
  pushYmWrite(commands, 0, 0x27, 0x00);
  pushYmWrite(commands, 0, 0x2B, 0x00);

  const patternMap = new Map((song.patterns || []).map((pattern) => [pattern.id, pattern]));
  for (const patternId of song.order || []) {
    const pattern = patternMap.get(patternId);
    for (const row of pattern?.rows || []) {
      for (const channel of CHANNELS) {
        const cell = row.cells?.[channel.id];
        if (!cell?.note) continue;
        if (channel.type === 'fm') pushFmNote(commands, channel.id, cell);
        else pushPsgNote(commands, channel.id, cell);
      }
      pushWaitFrame(commands);
    }
  }
  commands.push(0x66);
  return Buffer.from(commands);
}

function writeVgm(song) {
  const data = buildVgmData(song);
  const headerSize = 0x100;
  const out = Buffer.alloc(headerSize + data.length, 0);
  out.write('Vgm ', 0, 'ascii');
  writeU32LE(out, 0x04, out.length - 4);
  writeU32LE(out, 0x08, 0x00000170);
  writeU32LE(out, 0x0C, 3579545);
  writeU32LE(out, 0x2C, 7670454);
  writeU32LE(out, 0x34, headerSize - 0x34);
  writeU32LE(out, 0x18, Math.max(1, (song.order || []).length * ROWS_PER_PATTERN) * 735);
  data.copy(out, headerSize);
  return out;
}

function ensureProjectPath(projectDir, relPath) {
  const root = path.resolve(projectDir);
  const abs = path.resolve(root, relPath);
  const rel = path.relative(root, abs);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) {
    throw new Error('project directory outside path is not allowed');
  }
  return abs;
}

function findXgmTool(extraPath) {
  if (extraPath) {
    return fs.existsSync(extraPath) ? extraPath : '';
  }
  const candidates = [];
  candidates.push('xgmtool.exe', 'xgmtool');
  const sgdk = process.env.GDK || process.env.SGDK;
  if (sgdk) candidates.push(path.join(sgdk, 'bin', 'xgmtool.exe'));
  candidates.push(path.resolve(__dirname, '..', '..', '..', '..', 'sgdk', 'current', 'bin', 'xgmtool.exe'));
  candidates.push('D:\\homebrew\\SGDK\\sgdk\\current\\bin\\xgmtool.exe');
  return candidates.find((candidate) => {
    if (!candidate) return false;
    if (candidate.includes(path.sep) || candidate.includes('\\')) return fs.existsSync(candidate);
    const probe = spawnSync(candidate, [], { windowsHide: true, encoding: 'utf-8' });
    return !probe.error || probe.status !== null;
  }) || '';
}

function exportMusic(payload, context = {}) {
  const projectDir = String(context.projectDir || payload?.projectDir || '');
  if (!projectDir) return { ok: false, error: 'projectDir が未設定です。' };
  const song = payload?.song || createDefaultSong();
  const symbol = normalizeSymbolName(payload?.symbol || song.symbol || song.title);
  const outputs = payload?.outputs || {};
  const diagnostics = validateSong(song);
  const musicDir = ensureProjectPath(projectDir, 'res/music');
  fs.mkdirSync(musicDir, { recursive: true });

  const jsonRel = `res/music/${symbol}.mdbgm.json`;
  const vgmRel = `res/music/${symbol}.vgm`;
  const xgmRel = `res/music/${symbol}.xgm`;
  const jsonPath = ensureProjectPath(projectDir, jsonRel);
  const vgmPath = ensureProjectPath(projectDir, vgmRel);
  const xgmPath = ensureProjectPath(projectDir, xgmRel);

  fs.writeFileSync(jsonPath, JSON.stringify({ ...song, symbol }, null, 2), 'utf-8');
  fs.writeFileSync(vgmPath, writeVgm({ ...song, symbol }));

  const result = {
    ok: true,
    symbol,
    files: { json: jsonRel, vgm: vgmRel },
    diagnostics,
    warnings: [],
  };

  if (outputs.xgm !== false) {
    const xgmTool = findXgmTool(payload?.xgmToolPath);
    if (!xgmTool) {
      result.warnings.push('xgmtool が見つからないため XGM 出力をスキップしました。VGM は保存済みです。');
    } else {
      const converted = spawnSync(xgmTool, [vgmPath, xgmPath, '-s'], { windowsHide: true, encoding: 'utf-8' });
      if (converted.error || converted.status !== 0 || !fs.existsSync(xgmPath)) {
        result.warnings.push(`XGM 変換に失敗しました: ${(converted.stderr || converted.stdout || converted.error?.message || '').trim()}`);
      } else {
        result.files.xgm = xgmRel;
      }
    }
  }

  if (outputs.registerAsset !== false) {
    result.asset = {
      type: 'XGM2',
      name: symbol,
      sourcePath: `music/${symbol}.vgm`,
      files: [`music/${symbol}.vgm`],
      options: '',
    };
  }

  return result;
}

function importMidi(payload) {
  const sourcePath = String(payload?.sourcePath || '');
  if (!sourcePath || !fs.existsSync(sourcePath)) {
    return { ok: false, error: 'MIDI ファイルが見つかりません。' };
  }
  const midi = parseMidi(fs.readFileSync(sourcePath));
  const imported = convertMidiToSong(midi, {
    title: payload?.title || path.basename(sourcePath, path.extname(sourcePath)),
    symbol: payload?.symbol || path.basename(sourcePath, path.extname(sourcePath)),
    allocations: payload?.allocations,
  });
  return { ok: true, ...imported };
}

module.exports = {
  CHANNELS,
  ROWS_PER_PATTERN,
  normalizeSymbolName,
  midiNoteToName,
  noteNameToMidi,
  createDefaultSong,
  parseMidi,
  convertMidiToSong,
  allocateMidiTracks,
  validateSong,
  buildVgmData,
  writeVgm,
  findXgmTool,
  exportMusic,
  importMidi,
};
