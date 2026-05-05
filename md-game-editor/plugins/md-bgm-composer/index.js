'use strict';

const core = require('./music-core');

function importMidi(payload, context = {}) {
  const result = core.importMidi(payload || {}, context);
  context?.logger?.info?.(`[md-bgm-composer] MIDI import: ${result.ok ? 'ok' : result.error}`);
  return result;
}

function exportMusic(payload, context = {}) {
  const result = core.exportMusic(payload || {}, context);
  context?.logger?.info?.(`[md-bgm-composer] export: ${result.ok ? result.symbol : result.error}`);
  return result;
}

function validateSong(payload) {
  return {
    ok: true,
    diagnostics: core.validateSong(payload?.song || payload),
  };
}

function analyzeVgm(payload, context = {}) {
  const result = core.analyzeVgm(payload || {}, context);
  context?.logger?.info?.(`[md-bgm-composer] analyze VGM: ${result.ok ? 'ok' : result.error}`);
  return result;
}

module.exports = {
  importMidi,
  exportMusic,
  validateSong,
  analyzeVgm,
  _core: core,
};
