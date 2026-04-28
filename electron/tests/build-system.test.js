'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function makeTempDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function loadBuildSystem(userData, home = makeTempDir('md-editor-home-test-')) {
  return loadWithMockedElectron(path.join(__dirname, '..', 'build-system.js'), {
    userData,
    paths: { userData, home },
  });
}

test('createProject writes SGDK project files and persists the active project', () => {
  const userData = makeTempDir('md-editor-build-state-test-');
  const projectDir = path.join(makeTempDir('md-editor-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);

  const result = buildSystem.createProject(projectDir, {
    title: 'Long Title With Non ASCII かな and Extra Characters',
    author: 'ME',
    serial: 'GM TEST-01',
    region: 'J',
  }, 'int main(void) { return 0; }\n');

  assert.equal(result.projectDir, path.resolve(projectDir));
  assert.equal(fs.readFileSync(path.join(projectDir, 'src', 'main.c'), 'utf-8'), 'int main(void) { return 0; }\n');
  assert.equal(fs.existsSync(path.join(projectDir, 'res', 'resources.res')), true);

  const header = fs.readFileSync(path.join(projectDir, 'src', 'boot', 'rom_head.c'), 'utf-8');
  assert.match(header, /"Long Title With Non ASCII/);
  assert.doesNotMatch(header, /かな/);

  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.equal(config.title, 'Long Title With Non ASCII かな and Extra Characters');
  assert.equal(buildSystem.getProjectDir(), path.resolve(projectDir));
});

test('openProject preserves existing user source and project config', () => {
  const userData = makeTempDir('md-editor-open-state-test-');
  const projectDir = path.join(makeTempDir('md-editor-open-project-test-'), 'existing');
  fs.mkdirSync(path.join(projectDir, 'src'), { recursive: true });
  fs.writeFileSync(path.join(projectDir, 'src', 'main.c'), 'int preserved(void) { return 1; }\n', 'utf-8');
  fs.writeFileSync(path.join(projectDir, 'project.json'), JSON.stringify({ title: 'Preserved' }, null, 2), 'utf-8');

  const buildSystem = loadBuildSystem(userData);
  const info = buildSystem.openProject(projectDir);

  assert.equal(info.projectDir, path.resolve(projectDir));
  assert.equal(info.title, 'Preserved');
  assert.equal(fs.readFileSync(path.join(projectDir, 'src', 'main.c'), 'utf-8'), 'int preserved(void) { return 1; }\n');
  assert.equal(fs.existsSync(path.join(projectDir, 'src', 'boot', 'rom_head.c')), true);
  assert.equal(fs.existsSync(path.join(projectDir, 'res', 'resources.res')), true);
});

test('project plugin selection is stored in project config', () => {
  const userData = makeTempDir('md-editor-plugin-config-test-');
  const projectDir = path.join(makeTempDir('md-editor-plugin-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);

  buildSystem.createProject(projectDir, { title: 'Demo' }, 'int main(void) { return 0; }\n');
  buildSystem.setBuilderPlugin('standard-builder');
  buildSystem.setEmulatorPlugin('standard-emulator');

  assert.equal(buildSystem.getBuilderPlugin(), 'standard-builder');
  assert.equal(buildSystem.getEmulatorPlugin(), 'standard-emulator');

  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.equal(config.builderPlugin, 'standard-builder');
  assert.equal(config.emulatorPlugin, 'standard-emulator');
});

test('buildProject fails fast when the toolchain path is missing', async () => {
  const userData = makeTempDir('md-editor-build-run-test-');
  const projectDir = path.join(makeTempDir('md-editor-build-run-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);
  const logs = [];

  buildSystem.createProject(projectDir, { title: 'Demo' }, 'int main(void) { return 0; }\n');
  const result = await buildSystem.buildProject(path.join(projectDir, 'missing-sgdk'), null, (message, level) => {
    logs.push({ message, level });
  });

  assert.equal(result.success, false);
  assert.match(result.error, /missing-sgdk/);
  assert.equal(logs.at(-1).level, 'error');
});

test('build log sanitization strips GCC ANSI color escapes', () => {
  const buildSystem = loadBuildSystem(makeTempDir('md-editor-build-sanitize-test-'));

  const clean = buildSystem.sanitizeBuildLogLine('\u001b[01m\u001b[Ksrc/main.c:7:\u001b[m\u001b[K error');
  assert.equal(clean, 'src/main.c:7: error');
});

test('make variables are normalized for command-line overrides', () => {
  const buildSystem = loadBuildSystem(makeTempDir('md-editor-build-vars-test-'));

  assert.deepEqual(buildSystem.normalizeMakeVariables({
    SRC_C: 'src/main.c',
    'BAD-NAME': 'ignored',
    MULTILINE: 'a\nb',
    EMPTY_OK: '',
  }), ['SRC_C=src/main.c', 'EMPTY_OK=']);
});
