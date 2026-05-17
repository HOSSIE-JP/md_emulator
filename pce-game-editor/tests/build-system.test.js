'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadWithMockedElectron } = require('./helpers/mock-electron');

function tempUserData() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pce-editor-build-'));
}

function loadBuildSystem(userData) {
  return loadWithMockedElectron(path.join(__dirname, '..', 'pce-build-system.js'), { userData });
}

test('cc65 postprocess moves the last 8KB bank to the front', () => {
  const userData = tempUserData();
  const buildSystem = loadBuildSystem(userData);
  const input = path.join(userData, 'in.bin');
  const output = path.join(userData, 'out.pce');
  const chunks = [1, 2, 3, 4].map((value) => Buffer.alloc(8192, value));
  fs.writeFileSync(input, Buffer.concat(chunks));
  const result = buildSystem.postprocessCc65PceRom(input, output);
  const data = fs.readFileSync(output);
  assert.equal(result.rearranged, true);
  assert.equal(data[0], 4);
  assert.equal(data[8192], 1);
});

test('build command differs for cc65 and llvm-mos', () => {
  const userData = tempUserData();
  const buildSystem = loadBuildSystem(userData);
  const projectDir = path.join(userData, 'project');
  fs.mkdirSync(path.join(projectDir, 'src', 'generated'), { recursive: true });
  fs.writeFileSync(path.join(projectDir, 'src', 'main.c'), 'int main(void){return 0;}\n');
  fs.writeFileSync(path.join(projectDir, 'src', 'generated', 'assets.c'), '\n');

  const cc65 = buildSystem.buildCommandForProject(projectDir, { toolchain: 'cc65', romName: 'game' }, '/tools/cl65');
  assert.equal(cc65.command, '/tools/cl65');
  assert.deepEqual(cc65.args.slice(0, 4), ['-t', 'pce', '-O', '-o']);
  assert.equal(path.basename(cc65.binPath), 'game.bin');

  const llvm = buildSystem.buildCommandForProject(projectDir, { toolchain: 'llvm-mos', romName: 'game' }, '/tools/mos-pce-clang');
  assert.equal(llvm.command, '/tools/mos-pce-clang');
  assert.deepEqual(llvm.args.slice(0, 3), ['-Os', '-o', path.join(projectDir, 'out', 'game.pce')]);
});

test('cc65 Homebrew bottle path resolves CC65_HOME for portable builds', () => {
  const userData = tempUserData();
  const buildSystem = loadBuildSystem(userData);
  const cc65Home = path.join(userData, 'tools', 'cc65', 'cc65', '2.19', 'share', 'cc65');
  const toolPath = path.join(userData, 'tools', 'cc65', 'cc65', '2.19', 'bin', process.platform === 'win32' ? 'cl65.exe' : 'cl65');
  fs.mkdirSync(path.join(cc65Home, 'include'), { recursive: true });
  fs.mkdirSync(path.join(cc65Home, 'lib'), { recursive: true });
  fs.mkdirSync(path.join(cc65Home, 'cfg'), { recursive: true });
  fs.mkdirSync(path.dirname(toolPath), { recursive: true });
  fs.writeFileSync(path.join(cc65Home, 'include', 'conio.h'), '');
  fs.writeFileSync(path.join(cc65Home, 'include', 'pce.h'), '');
  fs.writeFileSync(path.join(cc65Home, 'lib', 'pce.lib'), '');
  fs.writeFileSync(path.join(cc65Home, 'cfg', 'pce.cfg'), '');
  fs.writeFileSync(toolPath, '');

  assert.equal(buildSystem.resolveCc65Home(toolPath), cc65Home);
  const command = buildSystem.buildCommandForProject(userData, { toolchain: 'cc65', romName: 'game' }, toolPath);
  assert.equal(command.env.CC65_HOME, cc65Home);
});

test('template project creates pce config and generated assets', async () => {
  const userData = tempUserData();
  const buildSystem = loadBuildSystem(userData);
  const created = buildSystem.createProjectInRoot('demo', {});
  assert.equal(created.config.platform, 'pce');
  assert.equal(created.config.pluginRoles.builder, 'pce-sample-builder');
  buildSystem.setProjectDir(created.projectDir);
  const result = await buildSystem.buildProject(() => {}, { dryRun: true, allowMissingToolchain: true });
  assert.equal(result.success, true);
  assert.equal(fs.existsSync(path.join(created.projectDir, 'src', 'generated', 'assets.h')), true);
  assert.equal(fs.existsSync(path.join(created.projectDir, 'src', 'generated', 'assets.c')), true);
});
