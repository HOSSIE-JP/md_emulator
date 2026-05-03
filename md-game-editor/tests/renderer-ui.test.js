'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

function readRendererFile(name) {
  return fs.readFileSync(path.join(__dirname, '..', 'renderer', name), 'utf-8');
}

test('settings page keeps project and export settings in two columns', () => {
  const html = readRendererFile('index.html');
  const css = readRendererFile('style.css');

  assert.match(html, /settings-form project-settings-grid/);
  assert.match(html, /<section class="settings-column">[\s\S]*現在のプロジェクト/);
  assert.match(html, /<section class="settings-column export-settings-column">[\s\S]*エクスポート設定[\s\S]*settingOutputPath/);
  assert.match(css, /\.project-settings-grid\s*\{[\s\S]*grid-template-columns:\s*minmax\(320px,\s*1fr\)\s*minmax\(280px,\s*0\.82fr\)/);
});

test('header project chips are actionable buttons wired to project actions', () => {
  const html = readRendererFile('index.html');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /<button class="project-name" id="projectName" type="button"/);
  assert.match(html, /<button class="project-path-chip" id="projectDirLabel" type="button"/);
  assert.match(renderer, /el\.projectName\?\.addEventListener\('click',\s*openProjectPicker\)/);
  assert.match(renderer, /el\.projectDirLabel\?\.addEventListener\('click',\s*openCurrentProjectDirectory\)/);
  assert.match(renderer, /window\.electronAPI\.openPathInExplorer\(state\.project\.dir\)/);
});

test('plugin role accordion starts collapsed by default', () => {
  const html = readRendererFile('index.html');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /id="btnPluginRoleAccordion" type="button" aria-expanded="false"/);
  assert.match(html, /class="accordion-body is-collapsed" id="pluginRoleBody"/);
  assert.match(renderer, /roleAccordionOpen:\s*false/);
});

test('log viewer height persists and popout control is wired', () => {
  const html = readRendererFile('index.html');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /id="btnPopoutLog"/);
  assert.match(renderer, /LOG_VIEWER_STATE_KEY\s*=\s*['"]md-editor\.logViewerState\.v1['"]/);
  assert.match(renderer, /localStorage\.setItem\(LOG_VIEWER_STATE_KEY/);
  assert.match(renderer, /loadLogViewerState\(\)/);
  assert.match(renderer, /openLogWindow\?\.\(getLogSnapshot\(\)\)/);
  assert.match(renderer, /appendLogWindowEntry\?\.\(entry\)/);
});

test('startup selects the first sidebar plugin and project creation exposes builder choice', () => {
  const html = readRendererFile('index.html');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /id="projectBuilderSelect"/);
  assert.match(renderer, /function getFirstSidebarPluginPageId\(\)/);
  assert.match(renderer, /selectedDefaultSidebarPage:\s*false/);
  assert.match(renderer, /switchPage\(getFirstSidebarPluginPageId\(\)\s*\|\|\s*getFirstVisiblePageId\(\)\)/);
  assert.match(renderer, /function populateProjectBuilderSelect\(\)/);
  assert.match(renderer, /function getPluginsByRole\(roleId\)/);
  assert.match(renderer, /return getPluginsByRole\('builder'\)/);
  assert.doesNotMatch(renderer, /function getInstalledBuilderPlugins\(\)\s*\{[\s\S]*?plugin\.enabled && pluginSupportsRole\(plugin,\s*'builder'\)/);
  assert.match(renderer, /空のプロジェクト/);
  assert.match(renderer, /payload\.config\.pluginRoles\s*=\s*\{\s*builder:\s*selectedBuilder\s*\}/);
});

test('plugin role selectors list installed role plugins regardless of enabled state', () => {
  const renderer = readRendererFile('renderer.js');

  assert.match(renderer, /const plugins = getPluginsByRole\(role\.id\)/);
  assert.match(renderer, /const buildIds = new Set\(getPluginsByRole\('builder'\)\.map\(\(p\) => p\.id\)\)/);
  assert.match(renderer, /const suffix = p\.enabled \? '' : '（無効: 選択時に有効化）'/);
  assert.doesNotMatch(renderer, /const plugins = getEnabledPluginsByRole\(role\.id\)/);
});

test('project settings save through IPC before build structure generation', () => {
  const renderer = readRendererFile('renderer.js');

  assert.match(renderer, /async function persistProjectSettings\(config,\s*\{\s*showMessage\s*=\s*false\s*\}\s*=\s*\{\}\)/);
  assert.match(renderer, /window\.electronAPI\.saveProjectConfig\(config\)/);
  assert.match(renderer, /await persistProjectSettings\(result\.config,\s*\{\s*showMessage:\s*true\s*\}\)/);
  assert.match(renderer, /await persistProjectSettings\(settingsResult\.config\)/);
  assert.match(renderer, /generateStructureOnly\(state\.projectConfig\)/);
});

test('exclusive role selection reloads plugin state after saving', () => {
  const renderer = readRendererFile('renderer.js');

  assert.match(renderer, /const result = await window\.electronAPI\.setPluginRole\(roleId,\s*nextId\)/);
  assert.match(renderer, /if \(!result\?\.ok\) throw new Error\(result\?\.error \|\| 'unknown'\)/);
  assert.match(renderer, /setPluginRoleStatus\(`✓ \$\{roleId\} プラグイン設定を保存しました`, 'ok'\);[\s\S]*await loadPlugins\(\)/);
});

test('project plugin roles restore plugin enabled state on plugin load', () => {
  const renderer = readRendererFile('renderer.js');

  assert.match(renderer, /async function restoreProjectPluginRoleState\(\)/);
  assert.match(renderer, /for \(const \[roleId,\s*pluginId\] of Object\.entries\(roles\)\)/);
  assert.match(renderer, /window\.electronAPI\.setPluginRole\(roleId,\s*pluginId\)/);
  assert.match(renderer, /pluginState\.plugins = await window\.electronAPI\.listPlugins\(\)/);
  assert.match(renderer, /await restoreProjectPluginRoleState\(\)/);
});

test('quantize dialog is larger and exposes tone controls', () => {
  const html = readRendererFile('index.html');
  const css = readRendererFile('style.css');
  const renderer = readRendererFile('renderer.js');

  assert.match(css, /\.quantize-panel\s*\{[\s\S]*width:\s*min\(1480px,\s*98vw\)/);
  assert.match(css, /\.quantize-panel\s*\{[\s\S]*height:\s*min\(940px,\s*96vh\)/);
  assert.match(css, /\.quantize-preview-panel canvas\s*\{[\s\S]*min-height:\s*520px/);
  assert.match(html, /id="quantizeBrightness"/);
  assert.match(html, /id="quantizeSaturation"/);
  assert.match(renderer, /function applyQuantizeToneAdjustments\(imageData,\s*options\s*=\s*\{\}\)/);
  assert.match(renderer, /const adjustedData = applyQuantizeToneAdjustments\(quantizeState\.originalData,\s*tone\)/);
  assert.match(renderer, /quantizeToIndexed16\(adjustedData,\s*options\)/);
});

test('quantize converter targets SGDK palette parameters with fast and slow dithering', () => {
  const html = readRendererFile('index.html');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /id="quantizeDitherMode"/);
  assert.match(html, /<option value="fast" selected>Fast<\/option>/);
  assert.match(html, /<option value="slow">Slow<\/option>/);
  assert.match(renderer, /return level \* 36/);
  assert.match(renderer, /function colorImportance\(color\)/);
  assert.match(renderer, /function weightedMedianCutPalette\(colors,\s*maxColors\)/);
  assert.match(renderer, /function refinePaletteKMeans\(colors,\s*initialPalette,\s*maxColors/);
  assert.match(renderer, /function popularDiversePalette\(colors,\s*maxColors\)/);
  assert.match(renderer, /function farthestPointPalette\(colors,\s*maxColors\)/);
  assert.match(renderer, /function chooseOptimizedPalette\(colors,\s*maxColors\)/);
  assert.match(renderer, /const palette = chooseOptimizedPalette\(colors,\s*maxColors\)/);
  assert.match(renderer, /function mapImageToPalette\(imageData,\s*palette,\s*options\s*=\s*\{\}\)/);
  assert.match(renderer, /ditherMode === 'slow'/);
  assert.match(renderer, /7 \/ 16/);
  assert.match(renderer, /const ditherNote = ` \/ dither: \$\{options\.ditherMode\}`/);
});

test('quantize converter previews the resulting palette', () => {
  const html = readRendererFile('index.html');
  const css = readRendererFile('style.css');
  const renderer = readRendererFile('renderer.js');

  assert.match(html, /id="quantizeResultPalette"/);
  assert.match(css, /\.quantize-result-palette\s*\{[\s\S]*grid-template-columns:\s*repeat\(16,/);
  assert.match(renderer, /function renderQuantizeResultPalette\(palette\s*=\s*\[\],\s*transparentIndex\s*=\s*-1\)/);
  assert.match(renderer, /renderQuantizeResultPalette\(converted\.palette,\s*converted\.transparentPaletteIndex\)/);
  assert.match(renderer, /el\.quantizeResultPalette\.innerHTML = ''/);
});
