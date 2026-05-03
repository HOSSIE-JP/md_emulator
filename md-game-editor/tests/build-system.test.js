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
  buildSystem.setPluginRole('builder', 'standard-builder');
  buildSystem.setPluginRole('testplay', 'standard-emulator');

  assert.equal(buildSystem.getPluginRole('builder'), 'standard-builder');
  assert.equal(buildSystem.getPluginRole('testplay'), 'standard-emulator');

  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.deepEqual(config.pluginRoles, {
    builder: 'standard-builder',
    testplay: 'standard-emulator',
  });
  assert.equal(Object.prototype.hasOwnProperty.call(config, 'builderPlugin'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(config, 'emulatorPlugin'), false);
});

test('createProject can persist an initial builder role', () => {
  const userData = makeTempDir('md-editor-create-builder-role-test-');
  const projectDir = path.join(makeTempDir('md-editor-create-builder-role-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);

  buildSystem.createProject(projectDir, {
    title: 'Demo',
    pluginRoles: { builder: 'slideshow' },
  }, 'int main(void) { return 0; }\n');

  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.deepEqual(config.pluginRoles, { builder: 'slideshow' });
});

test('default bundled project points at sample slideshow project', () => {
  const userData = makeTempDir('md-editor-default-project-test-');
  const buildSystem = loadBuildSystem(userData);

  assert.equal(path.basename(buildSystem.getDefaultProjectDir()), 'sample_slideshow');
});

test('project startup state requires selection on first run or missing saved project', () => {
  const userData = makeTempDir('md-editor-startup-project-test-');
  const buildSystem = loadBuildSystem(userData);

  let startup = buildSystem.getProjectStartupState();
  assert.equal(startup.hasSavedProject, false);
  assert.equal(startup.savedProjectExists, false);
  assert.equal(startup.requiresProjectSelection, true);

  const missingProject = path.join(makeTempDir('md-editor-missing-project-root-'), 'deleted');
  buildSystem.setProjectDir(missingProject);
  startup = buildSystem.getProjectStartupState();
  assert.equal(startup.hasSavedProject, true);
  assert.equal(startup.savedProjectDir, path.resolve(missingProject));
  assert.equal(startup.savedProjectExists, false);
  assert.equal(startup.requiresProjectSelection, true);

  const existingProject = path.join(makeTempDir('md-editor-existing-project-root-'), 'demo');
  fs.mkdirSync(existingProject, { recursive: true });
  buildSystem.setProjectDir(existingProject);
  startup = buildSystem.getProjectStartupState();
  assert.equal(startup.savedProjectExists, true);
  assert.equal(startup.requiresProjectSelection, false);
});

test('pluginRoles are the only plugin role storage', () => {
  const userData = makeTempDir('md-editor-plugin-roles-test-');
  const projectDir = path.join(makeTempDir('md-editor-plugin-roles-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);

  buildSystem.createProject(projectDir, { title: 'Demo' }, 'int main(void) { return 0; }\n');
  buildSystem.saveProjectConfig({ pluginRoles: { builder: 'role-builder' } });

  assert.equal(buildSystem.getPluginRole('builder'), 'role-builder');
  assert.equal(buildSystem.getPluginRole('testplay'), null);

  buildSystem.setPluginRole('testplay', 'role-emulator');
  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.equal(config.pluginRoles.testplay, 'role-emulator');
  assert.equal(Object.prototype.hasOwnProperty.call(config, 'emulatorPlugin'), false);
});

test('saveProjectConfig persists project settings and rewrites the ROM header', () => {
  const userData = makeTempDir('md-editor-save-config-header-test-');
  const projectDir = path.join(makeTempDir('md-editor-save-config-header-project-test-'), 'demo');
  const buildSystem = loadBuildSystem(userData);

  buildSystem.createProject(projectDir, {
    title: 'Before Title',
    author: 'OLD',
    serial: 'GM OLD-01',
    region: 'U',
  }, 'int main(void) { return 0; }\n');

  const saved = buildSystem.saveProjectConfig({
    title: 'Saved Header',
    author: 'NEWAUTHOR',
    serial: 'GM SAVE-02',
    region: 'JUE',
  });

  assert.equal(saved.title, 'Saved Header');
  const config = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf-8'));
  assert.equal(config.title, 'Saved Header');
  assert.equal(config.serial, 'GM SAVE-02');

  const header = fs.readFileSync(path.join(projectDir, 'src', 'boot', 'rom_head.c'), 'utf-8');
  assert.match(header, /"Saved Header\s+"/);
  assert.match(header, /"GM SAVE-02\s+"/);
  assert.match(header, /"JUE\s+"/);
  assert.doesNotMatch(header, /Before Title/);
  assert.doesNotMatch(header, /GM OLD-01/);
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

test('build env and make targets are normalized for plugin build options', () => {
  const buildSystem = loadBuildSystem(makeTempDir('md-editor-build-options-test-'));

  assert.deepEqual(buildSystem.normalizeBuildEnv({
    SGDK_TRACE: '1',
    'BAD-NAME': 'ignored',
    PATH: 'ignored',
    NODE_OPTIONS: '--require bad',
    MULTILINE: 'a\nb',
    EMPTY_OK: '',
  }), { SGDK_TRACE: '1', EMPTY_OK: '' });

  assert.deepEqual(buildSystem.normalizeMakeTargets(['release', 'tools-only', '../bad', 'release']), ['release', 'tools-only']);
  assert.deepEqual(buildSystem.normalizeMakeTargets([]), ['release']);
});
