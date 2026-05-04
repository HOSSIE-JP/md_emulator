const VGM_SAMPLE_RATE = 44100;
const YM2612_CHANNELS = 6;

export function canPreviewVgmEntry(entry = {}) {
  const source = String(entry.sourcePath || '').toLowerCase();
  const files = Array.isArray(entry.files) ? entry.files : [];
  const firstFile = String(files[0] || '').toLowerCase();
  const type = String(entry.type || '').toUpperCase();
  return source.endsWith('.vgm') || (['XGM', 'XGM2'].includes(type) && firstFile.endsWith('.vgm'));
}

export function dataUrlToBytes(dataUrl = '') {
  const text = String(dataUrl || '');
  const comma = text.indexOf(',');
  const body = comma >= 0 ? text.slice(comma + 1) : text;
  const binary = typeof atob === 'function'
    ? atob(body)
    : Buffer.from(body, 'base64').toString('binary');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i) & 0xff;
  return bytes;
}

function readAscii(bytes, offset, length) {
  let out = '';
  for (let i = 0; i < length; i += 1) out += String.fromCharCode(bytes[offset + i] || 0);
  return out;
}

function u16(bytes, offset) {
  return (bytes[offset] || 0) | ((bytes[offset + 1] || 0) << 8);
}

function u32(bytes, offset) {
  return (bytes[offset] || 0)
    | ((bytes[offset + 1] || 0) << 8)
    | ((bytes[offset + 2] || 0) << 16)
    | ((bytes[offset + 3] || 0) << 24);
}

function skipDataBlock(bytes, offset, warnings) {
  if (bytes[offset] !== 0x66) {
    warnings.push(`Unsupported VGM data block at 0x${Math.max(0, offset - 1).toString(16)}.`);
    return bytes.length;
  }
  const size = u32(bytes, offset + 2) >>> 0;
  return Math.min(bytes.length, offset + 6 + size);
}

export function parseVgmBytes(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input || []);
  const warnings = [];
  if (bytes.length < 0x40 || readAscii(bytes, 0, 4) !== 'Vgm ') {
    return { ok: false, error: 'VGM header が見つかりません。' };
  }

  const version = u32(bytes, 0x08) >>> 0;
  const sn76489Clock = u32(bytes, 0x0c) >>> 0;
  const ym2612Clock = u32(bytes, 0x2c) >>> 0;
  const dataOffsetValue = u32(bytes, 0x34) >>> 0;
  let offset = dataOffsetValue ? 0x34 + dataOffsetValue : 0x40;
  if (offset < 0x40 || offset >= bytes.length) offset = 0x40;

  const events = [];
  let waitSamples = 0;
  let ym2612Writes = 0;
  let psgWrites = 0;

  while (offset < bytes.length) {
    const commandOffset = offset;
    const command = bytes[offset];
    offset += 1;

    if (command === 0x66) break;
    if (command === 0x50) {
      if (offset >= bytes.length) break;
      events.push({ timeSamples: waitSamples, type: 'psg', value: bytes[offset], offset: commandOffset });
      offset += 1;
      psgWrites += 1;
      continue;
    }
    if (command === 0x52 || command === 0x53) {
      if (offset + 1 >= bytes.length) break;
      events.push({
        timeSamples: waitSamples,
        type: 'ym2612',
        port: command === 0x52 ? 0 : 1,
        address: bytes[offset],
        value: bytes[offset + 1],
        offset: commandOffset,
      });
      offset += 2;
      ym2612Writes += 1;
      continue;
    }
    if (command === 0x61) {
      waitSamples += u16(bytes, offset);
      offset += 2;
      continue;
    }
    if (command === 0x62) {
      waitSamples += 735;
      continue;
    }
    if (command === 0x63) {
      waitSamples += 882;
      continue;
    }
    if (command >= 0x70 && command <= 0x7f) {
      waitSamples += (command & 0x0f) + 1;
      continue;
    }
    if (command === 0x67) {
      offset = skipDataBlock(bytes, offset, warnings);
      continue;
    }

    warnings.push(`Unsupported VGM command 0x${command.toString(16).padStart(2, '0')} at 0x${commandOffset.toString(16)}.`);
    break;
  }

  return {
    ok: true,
    version,
    ym2612Clock,
    sn76489Clock,
    events,
    warnings,
    meta: {
      durationSec: waitSamples / VGM_SAMPLE_RATE,
      ym2612Writes,
      psgWrites,
      waitSamples,
      warnings,
    },
  };
}

function fmFrequency(channel) {
  const fnum = ((channel.fnumMsb || 0) << 8) | (channel.fnumLsb || 0);
  const block = channel.block || 4;
  if (!fnum) return 0;
  return Math.max(20, Math.min(12000, (fnum / 144) * (2 ** (block - 4)) * 440));
}

function fmGain(channel) {
  const tl = Math.min(127, Math.max(0, channel.totalLevel ?? 36));
  return Math.max(0.015, (127 - tl) / 127) * 0.14;
}

function scheduleOscillator(ctx, destination, start, stop, frequency, type, gainValue) {
  if (!frequency || stop <= start || start < ctx.currentTime - 0.05) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, gainValue), start + 0.01);
  gain.gain.setValueAtTime(Math.max(0.0001, gainValue), Math.max(start + 0.011, stop - 0.03));
  gain.gain.exponentialRampToValueAtTime(0.0001, stop);
  osc.connect(gain).connect(destination);
  osc.start(start);
  osc.stop(stop + 0.02);
}

function makeNoiseBuffer(ctx, durationSec) {
  const length = Math.max(1, Math.ceil(ctx.sampleRate * durationSec));
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) data[i] = (Math.random() * 2) - 1;
  return buffer;
}

function scheduleNoise(ctx, destination, start, stop, gainValue) {
  if (stop <= start) return;
  const source = ctx.createBufferSource();
  const gain = ctx.createGain();
  source.buffer = makeNoiseBuffer(ctx, stop - start);
  gain.gain.setValueAtTime(Math.max(0.0001, gainValue), start);
  gain.gain.exponentialRampToValueAtTime(0.0001, stop);
  source.connect(gain).connect(destination);
  source.start(start);
  source.stop(stop + 0.02);
}

export function createVgmPreviewPlayer() {
  let parsed = null;
  let audioContext = null;
  let stopTimer = 0;
  let timeTimer = 0;
  let startedAt = 0;
  let playing = false;

  function stop() {
    if (stopTimer) clearTimeout(stopTimer);
    if (timeTimer) clearInterval(timeTimer);
    stopTimer = 0;
    timeTimer = 0;
    playing = false;
    if (audioContext) {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
  }

  function load({ dataUrl } = {}) {
    stop();
    const result = parseVgmBytes(dataUrlToBytes(dataUrl));
    if (!result.ok) {
      parsed = null;
      return result;
    }
    parsed = result;
    return { ok: true, meta: result.meta, warnings: result.warnings };
  }

  async function play({ onTime, onEnded, onError } = {}) {
    if (!parsed?.ok) return { ok: false, error: 'VGM が読み込まれていません。' };
    stop();
    const Ctor = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!Ctor) return { ok: false, error: 'Web Audio が利用できません。' };

    try {
      audioContext = new Ctor();
      const master = audioContext.createGain();
      master.gain.value = 0.55;
      master.connect(audioContext.destination);
      const startAt = audioContext.currentTime + 0.08;
      const fm = Array.from({ length: YM2612_CHANNELS }, () => ({
        fnumLsb: 0,
        fnumMsb: 0,
        block: 4,
        totalLevel: 36,
        keyStart: null,
      }));
      const psg = Array.from({ length: 4 }, () => ({
        tone: 0,
        volume: 15,
        start: null,
        noise: false,
      }));
      let psgLatched = { type: 'tone', channel: 0 };

      function closeFm(index, time) {
        const channel = fm[index];
        if (channel.keyStart == null) return;
        scheduleOscillator(audioContext, master, startAt + channel.keyStart, startAt + time, fmFrequency(channel), 'sine', fmGain(channel));
        channel.keyStart = null;
      }

      function closePsg(index, time) {
        const channel = psg[index];
        if (channel.start == null) return;
        const gain = Math.max(0, (15 - channel.volume) / 15) * 0.10;
        if (index === 3 || channel.noise) {
          scheduleNoise(audioContext, master, startAt + channel.start, startAt + time, gain);
        } else {
          const freq = Math.max(40, Math.min(8000, 3579545 / (32 * Math.max(1, channel.tone || 1))));
          scheduleOscillator(audioContext, master, startAt + channel.start, startAt + time, freq, 'square', gain);
        }
        channel.start = null;
      }

      function handlePsg(value, time) {
        if (value & 0x80) {
          const channel = (value >> 5) & 0x03;
          const isVolume = !!(value & 0x10);
          psgLatched = { type: isVolume ? 'volume' : 'tone', channel };
          if (isVolume) {
            closePsg(channel, time);
            psg[channel].volume = value & 0x0f;
            if (psg[channel].volume < 15) psg[channel].start = time;
            return;
          }
          closePsg(channel, time);
          psg[channel].tone = (psg[channel].tone & 0x3f0) | (value & 0x0f);
          psg[channel].noise = channel === 3;
          if (psg[channel].volume < 15) psg[channel].start = time;
          return;
        }
        const channel = psgLatched.channel;
        if (psgLatched.type === 'tone') {
          closePsg(channel, time);
          psg[channel].tone = (psg[channel].tone & 0x0f) | ((value & 0x3f) << 4);
          if (psg[channel].volume < 15) psg[channel].start = time;
        }
      }

      parsed.events.forEach((event) => {
        const time = event.timeSamples / VGM_SAMPLE_RATE;
        if (event.type === 'psg') {
          handlePsg(event.value, time);
          return;
        }
        const channelIndex = event.port * 3 + (event.address & 0x03);
        if (channelIndex < 0 || channelIndex >= YM2612_CHANNELS) return;
        const channel = fm[channelIndex];
        if (event.address >= 0x40 && event.address <= 0x4e) {
          const opChannel = event.address & 0x03;
          if (opChannel < 3) fm[event.port * 3 + opChannel].totalLevel = event.value & 0x7f;
        } else if (event.address >= 0xa0 && event.address <= 0xa2) {
          closeFm(channelIndex, time);
          channel.fnumLsb = event.value;
          if (channel.keyStart != null) channel.keyStart = time;
        } else if (event.address >= 0xa4 && event.address <= 0xa6) {
          closeFm(channelIndex, time);
          channel.fnumMsb = event.value & 0x07;
          channel.block = (event.value >> 3) & 0x07;
          if (channel.keyStart != null) channel.keyStart = time;
        } else if (event.address === 0x28) {
          const keyChannel = (event.value & 0x03) + ((event.value & 0x04) ? 3 : 0);
          if (keyChannel >= 0 && keyChannel < YM2612_CHANNELS) {
            if (event.value & 0xf0) {
              if (fm[keyChannel].keyStart == null) fm[keyChannel].keyStart = time;
            } else {
              closeFm(keyChannel, time);
            }
          }
        }
      });

      const duration = Math.max(0.1, parsed.meta.durationSec);
      for (let i = 0; i < fm.length; i += 1) closeFm(i, duration);
      for (let i = 0; i < psg.length; i += 1) closePsg(i, duration);

      startedAt = startAt;
      playing = true;
      if (audioContext.state === 'suspended') await audioContext.resume();
      timeTimer = setInterval(() => {
        if (!playing) return;
        onTime?.(Math.min(duration, Math.max(0, audioContext.currentTime - startedAt)));
      }, 100);
      stopTimer = setTimeout(() => {
        stop();
        onTime?.(0);
        onEnded?.();
      }, Math.ceil((duration + 0.15) * 1000));
      return { ok: true, durationSec: duration, warnings: parsed.warnings };
    } catch (error) {
      stop();
      onError?.(error);
      return { ok: false, error: String(error?.message || error) };
    }
  }

  return {
    canPreview: canPreviewVgmEntry,
    load,
    play,
    stop,
    isPlaying: () => playing,
  };
}
