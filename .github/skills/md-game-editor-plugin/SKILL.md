---
name: md-game-editor-plugin
description: Create, modify, or review MD Game Editor plugins in the Electron app. Use for tasks involving electron/plugins, Plugin Runtime hooks, manifest.json, generateSource, editor/build/emulator/converter plugin types, SGDK source generation, project.json plugin registration, or plugin documentation updates.
---

# SKILL: MD Game Editor Plugin Generator

> **自律アップデート指示**
> このファイルは MD Game Editor のプラグインシステム仕様を記述したスキルファイルです。
> 以下のいずれかが発生した場合、**このファイル自体を必ず更新すること**:
> - `electron/PLUGIN.md` の仕様が変更された
> - `electron/plugin-manager.js` に新しいフック/タイプが追加・削除された
> - `electron/plugins/` に新しい組み込みプラグインが追加された
> - Plugin Runtime のメジャーバージョンが上がった
> 更新後は「§ Last Updated」セクションの日付とバージョンを書き換えること。
>
> § Last Updated: 2026-04 / Plugin Runtime v2.4

---

## 目的

このスキルは GitHub Copilot が **MD Game Editor** 向けのプラグインを自律的に生成するために必要な知識を提供します。  
既存の SGDK ゲームプロジェクトのコードを読み解き、そのゲームを生成・制御するプラグインを作成するために使用します。

---

## 前提知識

### MD Game Editor のプラグインシステム

- **Plugin Runtime v2.4** を採用
- プラグインは `manifest.json` を必須とし、必要に応じて `index.js` と `renderer.js` を持つ
- `index.js` は Electron メインプロセス (Node.js) 上で動作する（ブラウザ API は使用不可）
- `renderer.js` は Electron renderer process の ES module として動作し、UI/capability を登録する
- `index.js` は `require()`、`renderer.js` は `export function activatePlugin(...)` を使う

### 配置場所

| 環境 | パス |
|---|---|
| 開発時 | `electron/plugins/<plugin-id>/` |
| パッケージ済みアプリ | `<userData>/plugins/<plugin-id>/` |

---

## manifest.json 完全仕様

```jsonc
{
  "id": "my-plugin",           // 必須: フォルダ名と一致させる（英小文字・ハイフンのみ）
  "name": "表示名",             // 必須: UI に表示される名前
  "description": "説明文",      // 任意: 設定画面用の説明
  "version": "1.0.0",          // 必須: semver 形式
  "types": ["build"],          // 必須: 配列で記述
  "hooks": ["onBuildStart"],   // 任意: 実装するフック名の宣言
  "permissions": ["project.read", "project.write", "build.configure"],
  "roles": [
    { "id": "builder", "label": "Build", "exclusive": true, "order": 10 }
  ],
  "mainApi": {                  // 任意: renderer から呼べる main hook/capability
    "hooks": ["convertAudio"],
    "capabilities": ["audio-convert"]
  },
  "tab": {                     // 任意: editor タイプでタブを追加する場合
    "label": "My Tab",
    "icon": "code",
    "page": "my-page",
    "order": 20
  },
  "renderer": {                 // 任意: renderer process 側の UI/capability
    "entry": "renderer.js",
    "styles": ["style.css"],
    "page": "my-page",
    "capabilities": ["page"]
  },
  "dependencies": ["other-id"] // 任意: 依存プラグイン ID
}
```

### タイプ一覧

| タイプ | 用途 | 主なフック |
|---|---|---|
| `build` | ビルドパイプライン参加・ソースコード生成 | `onBuildStart` / `onBuildEnd` / `onBuildError` / `generateSource` |
| `editor` | エディタ UI タブを提供 | `getTab` / `onActivate` / `onDeactivate` |
| `asset` | アセット管理機能 | `editor` との組み合わせが一般的 |
| `emulator` | Test Play 実行 | `onTestPlay` |
| `converter` | 画像・音声変換などの処理/UI capability | `renderer.capabilities` / 独自 hook |

### renderer module パターン

Plugin Runtime v2.4 では、機能固有 UI は本体 `electron/renderer/renderer.js` へ直接追加せず、プラグイン配下の renderer module に置く。

```js
export function activatePlugin({ plugin, root, pageRoot, hostRoot, api, logger, registerCapability }) {
  registerCapability('my-capability', { root });
  return {
    deactivate() {
      // イベント購読や DOM 状態を片付ける
    },
  };
}
```

- `entry` と `styles` は plugin ディレクトリ内の相対パスだけを指定する
- `../` や絶対パスで plugin 外へ出る指定は禁止
- Assets / Code のようなページ UI は `renderer.page` と `tab.page` を一致させる
- Converter は `image-resize`, `image-quantize`, `audio-convert-ui` などの capability を登録し、利用側 plugin は capability 経由で呼び出す
- 新規ページ、ツール、converter、モーダル、プレビューは本体 HTML/renderer に追加せず、`root` / `pageRoot` / `hostRoot` と `api.createModal()` / `api.mountElement()` で plugin 側に mount する
- プラグイン同士の連携は `api.capabilities.get()` / `api.capabilities.require()` / `api.events.on()` / `api.events.emit()` を使い、本体側に個別 plugin ID の分岐を追加しない
- renderer から main process hook を呼ぶ場合は `hooks` と `mainApi.hooks` の両方に宣言し、`api.plugins.invokeHook()` または `window.electronAPI.invokePluginHook()` を使う
- asset type / import / image 変換は `asset-type-provider` / `asset-import-handler` / `image-import-pipeline` capability として登録する
- Build / Test Play など単一選択 plugin は `roles` で宣言し、project.json の標準保存先は `pluginRoles` とする
- `permissions` は v2.4 では表示・レビュー用途の宣言で、sandbox 強制ではない
- 新規 plugin で本体 `main.js` / `preload.js` / `build-system.js` の個別追記が必要に見える場合は、まず Runtime v2.4 の汎用 API 不足として扱う

### Runtime v2.4 で必ず守る開発手順

1. `manifest.json` に `types`、`permissions`、必要な `roles`、`hooks`、`renderer.capabilities` を宣言する
2. Build / Test Play の単一選択 plugin は `roles` を宣言し、project 側は `project.json.pluginRoles` に保存する
3. UI、modal、preview、converter 連携は plugin の `renderer.js` で実装し、本体 HTML / renderer / main / preload へ個別追記しない
4. main process の処理が必要な場合は `hooks` と `mainApi.hooks` に同じ hook 名を宣言し、renderer から `api.plugins.invokeHook()` で呼ぶ
5. asset 登録拡張は `asset-type-provider` / `asset-import-handler` / `image-import-pipeline` capability として提供する

---

## フック完全仕様

### `onBuildStart(payload, context)`

```ts
payload: { projectDir: string }
context: { logger: Logger, projectDir: string }
return:  { ok: boolean, error?: string }
```

### `onBuildLog(payload)`

```ts
payload: { text: string, level: 'info' | 'warn' | 'error' | 'debug' }
return:  { ok: boolean }
```

### `onBuildEnd(payload, context)`

```ts
payload: { projectDir: string, romPath: string, elapsed: number }
context: { logger: Logger }
return:  { ok: boolean, error?: string }
```

### `onBuildError(payload, context)`

```ts
payload: { projectDir: string, error: string }
context: { logger: Logger }
return:  { ok: boolean }
```

### `generateSource(assets, context)` / `generateSourceAsync(assets, context)`

**最重要**: `build` タイプで `src/main.c` を生成するジェネレータ関数。  
`window.electronAPI.runPluginGenerator(pluginId)` から呼び出される。

```ts
assets: Array<{
  type: string;             // 'IMAGE' | 'SPRITE' | 'XGM2' | 'XGM' | 'WAV' など
  name: string;             // リソース名 (例: 'image001', 'bgm')
  sourcePath: string;       // プロジェクト相対パス
  sourceAbsolutePath: string; // 絶対パス
}>
context: { projectDir: string, logger: Logger }
return:  { ok: boolean, sourceCode?: string, error?: string }
```

### `onTestPlay(payload)`

```ts
payload: { romPath: string }
return:  { ok: boolean, handled: boolean }
// handled: true → デフォルトの WASM ウィンドウ起動をスキップ
// handled: false → デフォルト動作に委譲
```

### `getTab()`, `onActivate(payload, context)`, `onDeactivate(payload, context)`

`editor` タイプのプラグイン用フック。`manifest.json` の `tab` オブジェクトと連動する。

---

## index.js の必須パターン

### build プラグイン（ソースコード生成あり）

```js
'use strict';

const manifest = require('./manifest.json');

/**
 * @param {Array<{type:string, name:string, sourcePath:string, sourceAbsolutePath:string}>} assets
 * @param {{ projectDir: string, logger: object }} context
 */
function generateSource(assets, context) {
  // アセットを解析してソースコードを生成する
  // ...
  return { ok: true, sourceCode: '/* generated code */' };
}

function onBuildStart(payload, context) {
  context.logger.info(`ビルド開始: ${payload.projectDir}`);
  return { ok: true };
}

function onBuildEnd(payload, context) {
  context.logger.info(`ROM 生成完了: ${payload.romPath}`);
  return { ok: true };
}

module.exports = { generateSource, onBuildStart, onBuildEnd };
```

### SGDK main 関数の必須シグネチャ

```c
/* SGDK 2.11 以降の必須シグネチャ */
int main(bool hardReset)
{
    (void)hardReset;
    /* ... */
    return 0;
}
```

> ⚠️ `void main()` や `int main(void)` は SGDK 2.11 以降でビルド警告が発生する。
> 必ず `int main(bool hardReset)` を使用し、`(void)hardReset;` でパラメータを消費すること。

---

## 既存 SGDK プロジェクトの解析方法

### Step 1: project.json を読む

```json
{
  "name": "プロジェクト名",
  "author": "作者名",
  "serial": "GM MYGAME-00",
  "region": "JPN",
  "pluginRoles": {
    "builder": "my-build-plugin",
    "testplay": "standard-emulator"
  }
}
```

`pluginRoles.builder` に自作プラグインの `id` を設定するとビルド時に呼ばれる。`pluginRoles.testplay` は Test Play 用プラグインを指定する。

### Step 2: res/resources.res を解析する

`.res` ファイルの各行の形式:

```
TYPE   name   "ファイルパス"   [追加パラメータ...]
```

よく使うタイプ:

| タイプ | 説明 | SGDK の C 変数型 |
|---|---|---|
| `IMAGE` | 320×224 の背景画像 | `const Image name` |
| `SPRITE` | スプライト | `const SpriteDefinition name` |
| `XGM2` | FM 音楽 (推奨) | `const u8 name[]` |
| `XGM` | FM 音楽 (旧) | `const u8 name[]` |
| `WAV` | PCM 音声 | `const u8 name[]` |
| `TILESET` | タイルセット | `const TileSet name` |
| `MAP` | タイルマップ | `const Map name` |
| `PALETTE` | パレット | `const Palette name` |

### Step 3: src/main.c の既存コードを読む

- どのような SGDK API を使っているか把握する
- 状態機械、スプライト管理、音楽再生の構造を理解する
- プラグイン生成時はこれを「ベース」に自動化・パラメータ化するコードを生成する

---

## generateSource 実装パターン集

### 画像スライドショー（参考実装: slideshow プラグイン）

```
1. assets から type=IMAGE かつ name が "image" で始まるものを名前順ソート
2. 存在しない場合は { ok: false, error: "..." } を返す
3. BGR アセットを extern 宣言してスライド配列を生成
4. main() でタイマーとジョイパッド入力でスライドを切り替える
```

### 汎用 build プラグインの設計指針

1. `assets` の解析は防衛的に行う（存在しないアセットタイプは `ok: false` を返す）
2. 生成コードの先頭に `/* Generated by <plugin-id> v<version> */` コメントを入れる
3. ハードコードを避け、アセット名から変数名を動的に生成する
4. SGDK API は `#include <genesis.h>` だけで利用可能
5. グローバル変数は最小限にし、スタック変数を優先する

---

## 既存組み込みプラグイン一覧

| id | タイプ | 説明 |
|---|---|---|
| `slideshow` | `build` | imageXXX アセットのスライドショー生成 |
| `code-editor` | `editor` | src/ ファイルツリー + コードエディタ |
| `asset-manager` | `editor`, `asset` | resources.res アセット管理 |
| `image-resize-converter` | `converter` | 8px 境界リサイズ |
| `image-quantize-converter` | `converter` | 16 色減色変換 |
| `audio-converter` | `converter` | WAV/MP3/OGG 変換と音声変換 UI |
| `standard-emulator` | `emulator` | WASM Mega Drive エミュレーター |

> 新しいプラグインが追加されたら、このテーブルに追記し § Last Updated を更新すること。

---

## コード生成ルール（OSS / ライセンス）

- 生成コードは必ず **オリジナル実装** とする
- 外部リポジトリからのコードコピーは禁止
- SGDK の公式 API (`genesis.h` で宣言された関数) を使うことは問題ない
- 疑わしい類似コードが生まれた場合は制御フローを変えて書き直す

---

## よくある間違い

| 間違い | 正しい対応 |
|---|---|
| `types: "build"` | `types: ["build"]` — 必ず配列で |
| `void main()` | `int main(bool hardReset)` |
| hooks 宣言と実装の不一致 | manifest の hooks と module.exports のキーを一致させる |
| Electron API を直接使う | `context` / `require()` 経由でアクセスする |
| ブラウザ API (fetch, DOM) を使う | プラグインはメインプロセス (Node.js) で動作するため使用不可 |
| generateSource でエラー時に例外を throw | `{ ok: false, error: "メッセージ" }` を返す |
