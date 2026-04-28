'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const rescomp = require('../rescomp-manager');

function makeProject() {
  const projectDir = fs.mkdtempSync(path.join(os.tmpdir(), 'md-editor-res-test-'));
  fs.mkdirSync(path.join(projectDir, 'res', 'gfx'), { recursive: true });
  return projectDir;
}

test('parseResContent parses comments, quoted paths, and type-specific fields', () => {
  const parsed = rescomp.parseResContent([
    '// main background',
    'IMAGE bg "gfx/title screen.png" BEST ALL 0',
    '# music comment',
    'XGM2 bgm "sfx/intro part1.vgm" "sfx/intro part2.vgm" -pack',
  ].join('\n'));

  assert.equal(parsed.entries.length, 2);
  assert.equal(parsed.entries[0].type, 'IMAGE');
  assert.equal(parsed.entries[0].name, 'bg');
  assert.equal(parsed.entries[0].sourcePath, 'gfx/title screen.png');
  assert.equal(parsed.entries[0].compression, 'BEST');
  assert.equal(parsed.entries[0].comment, 'main background');
  assert.deepEqual(parsed.entries[1].files, ['sfx/intro part1.vgm', 'sfx/intro part2.vgm']);
  assert.equal(parsed.entries[1].options, '-pack');
});

test('entryToResLine quotes names and paths only when needed', () => {
  const line = rescomp.entryToResLine({
    type: 'IMAGE',
    name: 'title bg',
    sourcePath: 'gfx/title screen.png',
    compression: 'NONE',
    mapOpt: 'ALL',
    mapBase: '0',
  });

  assert.equal(line, 'IMAGE "title bg" "gfx/title screen.png" NONE ALL 0');
});

test('parseResContent parses WAV with omitted out_rate correctly', () => {
  const parsed = rescomp.parseResContent([
    'WAV bgm sfx/bgm.wav XGM2 TRUE',
    'WAV se sfx/se.wav PCM 22050 FALSE',
  ].join('\n'));

  assert.equal(parsed.entries.length, 2);
  assert.equal(parsed.entries[0].type, 'WAV');
  assert.equal(parsed.entries[0].driver, 'XGM2');
  assert.equal(parsed.entries[0].outRate, '');
  assert.equal(parsed.entries[0].far, 'TRUE');

  assert.equal(parsed.entries[1].type, 'WAV');
  assert.equal(parsed.entries[1].driver, 'PCM');
  assert.equal(parsed.entries[1].outRate, '22050');
  assert.equal(parsed.entries[1].far, 'FALSE');
});

test('listResDefinitions creates a default resources.res when none exists', () => {
  const projectDir = makeProject();
  const result = rescomp.listResDefinitions(projectDir);

  assert.equal(result.files.length, 1);
  assert.equal(result.files[0].file, 'resources.res');
  assert.equal(fs.existsSync(path.join(projectDir, 'res', 'resources.res')), true);
});

test('resource file operations preserve comments through update and delete', () => {
  const projectDir = makeProject();

  rescomp.createResFile(projectDir, 'resources.res');
  rescomp.addResEntry(projectDir, 'resources.res', {
    type: 'IMAGE',
    name: 'bg',
    sourcePath: 'gfx/bg.png',
    compression: 'NONE',
    mapOpt: 'ALL',
    mapBase: '0',
    comment: 'first asset',
  });

  let defs = rescomp.listResDefinitions(projectDir);
  const lineNumber = defs.files[0].entries[0].lineNumber;
  assert.equal(defs.files[0].entries[0].comment, 'first asset');

  rescomp.updateResEntry(projectDir, 'resources.res', lineNumber, {
    type: 'IMAGE',
    name: 'bg2',
    sourcePath: 'gfx/bg2.png',
    compression: 'NONE',
    mapOpt: 'ALL',
    mapBase: '0',
    comment: 'updated asset',
  });

  defs = rescomp.listResDefinitions(projectDir);
  assert.equal(defs.files[0].entries[0].name, 'bg2');
  assert.equal(defs.files[0].entries[0].comment, 'updated asset');

  rescomp.deleteResEntry(projectDir, 'resources.res', defs.files[0].entries[0].lineNumber);
  defs = rescomp.listResDefinitions(projectDir);
  assert.equal(defs.files[0].entryCount, 0);
});

test('listResDefinitions rejects source paths escaping the resource directory', () => {
  const projectDir = makeProject();
  fs.writeFileSync(path.join(projectDir, 'res', 'resources.res'), 'IMAGE bad ../outside.png NONE ALL 0\n', 'utf-8');

  assert.throws(
    () => rescomp.listResDefinitions(projectDir),
    /outside resource directory/,
  );
});
