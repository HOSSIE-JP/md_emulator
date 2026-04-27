# MD Game Editor — プラグイン開発ガイド

このドキュメントは、**MD Game Editor** 向けのカスタムプラグインを開発する方を対象としています。  
プラグインシステム (Plugin Runtime v2) の仕様、マニフェスト定義、フック API、およびレンダラーからの呼び出し方を解説します。

---

## 目次

1. [プラグインの配置場所](#1-プラグインの配置場所)
2. [ディレクトリ構成](#2-ディレクトリ構成)
3. [manifest.json 仕様](#3-manifestjson-仕様)
4. [プラグインタイプ一覧](#4-プラグインタイプ一覧)
5. [フック一覧](#5-フック一覧)
6. [index.js の書き方](#6-indexjs-の書き方)
7. [コンテキストオブジェクト](#7-コンテキストオブジェクト)
8. [依存関係の宣言](#8-依存関係の宣言)
9. [タブ UI の追加 (tab オブジェクト)](#9-タブ-ui-の追加-tab-オブジェクト)
10. [有効 / 無効の管理](#10-有効--無効の管理)
11. [レンダラーから呼び出せる IPC API](#11-レンダラーから呼び出せる-ipc-api)
12. [既存プラグイン一覧](#12-既存プラグイン一覧)
13. [開発の流れ (チュートリアル)](#13-開発の流れ-チュートリアル)
14. [よくある間違い](#14-よくある間違い)

---

## 1. プラグインの配置場所

### 開発時（非パッケージ）

```
electron/plugins/<plugin-id>/
```

### パッケージ済みアプリ

```
<app resources>/plugins/<plugin-id>/
```

アプリ内の **Settings > Plugins** パネルの「📂 フォルダを開く」ボタンで、実際の配置先を Explorer で開けます。

---

## 2. ディレクトリ構成

プラグインは最低限 2 つのファイルで構成されます。

```
electron/plugins/
└── my-plugin/
    ├── manifest.json   ← 必須: メタデータ・タイプ・フック宣言
    └── index.js        ← 必須: フック実装
```

その他のファイル（ライブラリ・アセットなど）を追加することも可能です。  
`index.js` から `require('./lib/util.js')` のように相対パスで参照できます。

---

## 3. manifest.json 仕様

```jsonc
{
  "id": "my-plugin",           // 必須: 一意な ID (英小文字・ハイフンのみ推奨)
  "name": "My Plugin",         // 必須: 表示名
  "description": "...",        // 任意: 説明文
  "version": "1.0.0",          // 必須: semver 形式
  "types": ["build"],          // 必須: プラグインタイプ (配列)
  "hooks": ["onBuildStart"],   // 任意: 実装するフック名の一覧
  "tab": { ... },              // 任意: タブ UI を追加する場合
  "dependencies": ["other-id"] // 任意: 依存プラグイン ID の一覧
}
```

### フィールド詳細

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | `string` | ✅ | プラグインを一意に識別する ID。フォルダ名と一致させること |
| `name` | `string` | ✅ | UI に表示される名前 |
| `description` | `string` | — | 設定画面に表示される説明文 |
| `version` | `string` | ✅ | semver 形式 (例: `"1.0.0"`) |
| `types` | `string[]` | ✅ | タイプ名の配列。複数タイプを持てる |
| `hooks` | `string[]` | — | 実装するフック名を列挙する（宣言のみ。実装は `index.js`） |
| `tab` | `object` | — | エディタにタブを追加する場合。[§9 参照](#9-タブ-ui-の追加-tab-オブジェクト) |
| `dependencies` | `string[]` | — | 依存プラグイン ID。[§8 参照](#8-依存関係の宣言) |

> **注意**: `types` は必ず **配列**で記述してください。文字列単体での記述 (`"type": "build"`) は後方互換のために内部処理されますが、新規プラグインでは使用しないでください。

---

## 4. プラグインタイプ一覧

`types` に指定できる値の一覧です。一つのプラグインが複数のタイプを持てます。

| タイプ名 | 説明 | 主なフック |
|---|---|---|
| `build` | ビルドパイプラインに参加するプラグイン | `onBuildStart` / `onBuildLog` / `onBuildEnd` / `onBuildError` |
| `editor` | エディタ UI にタブを提供するプラグイン | `getTab` / `onActivate` / `onDeactivate` |
| `asset` | アセット管理機能を提供するプラグイン | （`editor` との組み合わせが一般的） |
| `emulator` | Test Play 実行を担当するプラグイン | `onTestPlay` |
| `converter` | 画像などの変換処理を提供するプラグイン | （主にレンダラー側から直接利用） |

---

## 5. フック一覧

### `onBuildStart`

ビルド開始直前に呼び出されます。

```ts
// payload
{ projectDir: string }

// context
{ logger: Logger }

// 戻り値
{ ok: boolean, error?: string }
```

### `onBuildLog`

ビルドプロセスからのログ行が届くたびに呼び出されます。

```ts
// payload
{ text: string, level: 'info' | 'warn' | 'error' | 'debug' }

// 戻り値
{ ok: boolean }
```

### `onBuildEnd`

ビルド完了（成功）後に呼び出されます。

```ts
// payload
{ projectDir: string, romPath: string, elapsed: number }

// 戻り値
{ ok: boolean, error?: string }
```

### `onBuildError`

ビルド失敗時に呼び出されます。

```ts
// payload
{ projectDir: string, error: string }

// 戻り値
{ ok: boolean }
```

### `getTab`

エディタのタブ情報を返します。`editor` タイプのプラグインが実装します。

```ts
// payload: なし

// 戻り値
{
  id: string,
  label: string,
  icon?: string,
  mountType: 'builtin-code-editor' | string
}
```

### `onActivate`

タブがアクティブになったときに呼び出されます。

```ts
// payload: {}
// context: { logger: Logger }
// 戻り値: { ok: boolean }
```

### `onDeactivate`

タブが非アクティブになったときに呼び出されます。

```ts
// payload: {}
// context: { logger: Logger }
// 戻り値: { ok: boolean }
```

### `onTestPlay`

Test Play ボタンが押されたときに呼び出されます。`emulator` タイプのプラグインが実装します。

```ts
// payload
{ romPath: string }

// 戻り値
{
  ok: boolean,
  handled: boolean  // true を返すとデフォルトの WASM ウィンドウ起動をスキップ
}
```

### `generateSource` / `generateSourceAsync`

`build` タイプのプラグインがソースコードを生成するために実装します。  
フックではなく **ジェネレータ関数** として扱われ、`plugins:runGenerator` IPC から呼び出されます。

```ts
// 引数
assets: Array<{
  type: string,       // 'IMAGE' | 'SPRITE' | 'XGM2' | 'WAV' など
  name: string,       // リソース名 (例: 'image001')
  sourcePath: string, // プロジェクト相対パス
  sourceAbsolutePath: string // 絶対パス
}>

context: {
  projectDir: string,
  logger: Logger
}

// 戻り値
{ ok: boolean, sourceCode?: string, error?: string }
```

---

## 6. index.js の書き方

### 最小構成

```js
'use strict';

module.exports = {
  // hooks ここに実装
};
```

### build プラグイン例

```js
'use strict';

const manifest = require('./manifest.json');

/**
 * ソースコード生成関数
 * @param {Array<{type:string, name:string, sourcePath:string}>} assets
 * @param {{ projectDir:string, logger:object }} context
 */
async function generateSourceAsync(assets, context) {
  context.logger.info('generateSource 開始');

  const images = assets.filter((a) => a.type === 'IMAGE');
  if (images.length === 0) {
    return { ok: false, error: 'IMAGE アセットが見つかりません' };
  }

  const sourceCode = `#include <genesis.h>\n/* generated by ${manifest.id} */\n`;
  return { ok: true, sourceCode };
}

async function onBuildStart(payload, context) {
  context.logger.info(`ビルド開始: ${payload.projectDir}`);
  return { ok: true };
}

async function onBuildEnd(payload, context) {
  context.logger.info(`ビルド完了: ${payload.romPath}`);
  return { ok: true };
}

module.exports = {
  generateSourceAsync,
  onBuildStart,
  onBuildEnd,
};
```

### editor タブ プラグイン例

```js
'use strict';

const manifest = require('./manifest.json');

function getTab() {
  return {
    id: manifest.id,
    label: manifest.tab?.label || manifest.name,
    icon: manifest.tab?.icon || 'default',
    mountType: 'builtin-code-editor', // または独自のマウントタイプ
  };
}

function onActivate(_payload, context) {
  context?.logger?.info(`${manifest.id} activated`);
  return { ok: true };
}

function onDeactivate(_payload, context) {
  context?.logger?.info(`${manifest.id} deactivated`);
  return { ok: true };
}

module.exports = { manifest, getTab, onActivate, onDeactivate };
```

---

## 7. コンテキストオブジェクト

フック関数の第 2 引数 `context` には、以下のプロパティが含まれます。

```ts
interface PluginContext {
  projectDir: string;    // 現在のプロジェクトディレクトリの絶対パス
  logger: Logger;        // ログ出力オブジェクト
}

interface Logger {
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
  debug(message: string): void;
  log(message: string): void;  // info の別名
}
```

`logger` で出力したメッセージは、エディタの **Build Log** パネルと **Plugin Log** パネルの両方に表示されます。

---

## 8. 依存関係の宣言

プラグイン A がプラグイン B の機能を必要とする場合、`dependencies` に宣言します。

```jsonc
{
  "id": "my-editor",
  "dependencies": ["image-resize-converter", "image-quantize-converter"]
}
```

**動作ルール**:

- プラグイン A を **有効化** すると、依存している B も自動的に有効化されます
- プラグイン B を **無効化** しようとすると、B に依存している A も自動的に無効化されます
- 依存するプラグインが存在しない場合、`setEnabled` の戻り値 `missingDependencies` に ID が含まれます

---

## 9. タブ UI の追加 (tab オブジェクト)

`editor` タイプのプラグインは `manifest.json` に `tab` オブジェクトを追加することで、エディタ上部のタブバーに項目を追加できます。

```jsonc
"tab": {
  "label": "My Tab",   // 必須: タブに表示されるラベル
  "icon": "code",      // 任意: アイコン識別子
  "page": "my-page",   // 任意: ページ識別子
  "order": 20          // 任意: タブの表示順 (小さい値が左)
}
```

`getTab` フックで返すオブジェクトの `mountType` により、タブコンテンツのマウント方式が決まります。

| `mountType` | 説明 |
|---|---|
| `"builtin-code-editor"` | 組み込みのコードエディタを使用 |
| その他の文字列 | カスタムマウントタイプ（将来の拡張用） |

---

## 10. 有効 / 無効の管理

プラグインの有効・無効状態は `<userData>/plugins-state.json` に保存されます。  
デフォルトはすべて **有効** です。

### `plugins-state.json` の形式

```json
{
  "my-plugin": { "enabled": false },
  "other-plugin": { "enabled": true }
}
```

ユーザーは Settings 画面の Plugins タブからトグルで切り替えられます。  
プラグイン自身がこのファイルを直接編集する必要はありません。

---

## 11. レンダラーから呼び出せる IPC API

レンダラープロセス（`renderer.js` など）は `window.electronAPI` 経由でプラグイン関連の IPC を呼び出せます。

### プラグイン管理

```js
// 全プラグイン一覧を取得
const plugins = await window.electronAPI.listPlugins();
// => Array<PluginInfo>

// プラグインを有効/無効化
const result = await window.electronAPI.setPluginEnabled('my-plugin', true);
// => { ok: boolean, changed: Array<{id,enabled,reason}>, changedIds: string[], missingDependencies: string[] }

// ジェネレータ実行 (src/main.c が生成される)
const result = await window.electronAPI.runPluginGenerator('my-plugin');
// => { ok: boolean, srcPath?: string, error?: string }

// plugins フォルダを Explorer で開く
await window.electronAPI.openPluginsFolder();
```

### `PluginInfo` の型

```ts
interface PluginInfo {
  id: string;
  name: string;
  description: string;
  version: string;
  pluginTypes: string[];   // types 配列の正規化済み値
  pluginType: string;      // pluginTypes[0]
  tab: object | null;      // manifest.tab の値
  dependencies: string[];
  hooks: string[];
  hasGenerator: boolean;   // generateSource / generateSourceAsync が存在するか
  enabled: boolean;        // 現在の有効状態
}
```

### イベント購読

プラグインのログは `onPluginLog` で購読できます。

```js
window.electronAPI.onPluginLog((payload) => {
  // payload: { pluginId: string, text: string, level: 'info'|'warn'|'error'|'debug' }
  console.log(`[${payload.pluginId}] ${payload.text}`);
});
```

---

## 12. 既存プラグイン一覧

### `slideshow` — スライドショーゲーム

| 項目 | 値 |
|---|---|
| タイプ | `build` |
| バージョン | 1.1.0 |
| フック | `onBuildStart`, `onBuildLog`, `onBuildEnd`, `onBuildError` |
| ジェネレータ | `generateSource` ✅ |

`resources.res` に登録された `imageXXX` という名前の IMAGE アセットを 5 秒ごとに切り替えるスライドショー用の `main.c` を自動生成します。

---

### `code-editor` — コードエディタ

| 項目 | 値 |
|---|---|
| タイプ | `editor` |
| バージョン | 0.1.0 |
| フック | `getTab`, `onActivate`, `onDeactivate` |

`src/` 配下のファイルをツリー表示して編集・新規作成・削除できる標準エディタプラグインです。

---

### `asset-manager` — Rescomp アセット管理

| 項目 | 値 |
|---|---|
| タイプ | `editor`, `asset` |
| バージョン | 1.0.0 |
| 依存 | `image-resize-converter`, `image-quantize-converter` |

`resources.res` のアセット一覧・編集・登録を担うメインエディタプラグインです。  
画像アセットのリサイズ・減色変換を内部から呼び出します。

---

### `image-resize-converter` — 画像リサイズコンバーター

| 項目 | 値 |
|---|---|
| タイプ | `converter` |
| バージョン | 1.0.0 |

8 ドット境界へのリサイズ / クリッピング機能を提供します。  
`asset-manager` が依存して利用します。

---

### `image-quantize-converter` — 画像減色コンバーター

| 項目 | 値 |
|---|---|
| タイプ | `converter` |
| バージョン | 1.0.0 |

画像を 16 色に減色変換する機能を提供します。  
参照パレット指定・メディアンカット法による独立実装です。

---

### `standard-emulator` — 標準エミュレーター（WASM）

| 項目 | 値 |
|---|---|
| タイプ | `emulator` |
| バージョン | 1.0.0 |
| フック | `onTestPlay` |

WASM ベースの Mega Drive エミュレーターです。  
Test Play ボタン押下時に呼び出され、`handled: false` を返すことでデフォルトの WASM ウィンドウ起動に委譲します。

---

## 13. 開発の流れ (チュートリアル)

### 手順 1: フォルダを作成する

```
electron/plugins/my-build-plugin/
├── manifest.json
└── index.js
```

### 手順 2: manifest.json を作成する

```json
{
  "id": "my-build-plugin",
  "name": "My Build Plugin",
  "description": "カスタムビルドプラグインのサンプル",
  "version": "1.0.0",
  "types": ["build"],
  "hooks": ["onBuildEnd"]
}
```

### 手順 3: index.js を作成する

```js
'use strict';

async function onBuildEnd(payload, context) {
  context.logger.info(`ROM が生成されました: ${payload.romPath}`);
  return { ok: true };
}

module.exports = { onBuildEnd };
```

### 手順 4: アプリを再起動して有効化する

1. `npm start` でアプリを起動
2. Settings > Plugins を開く
3. `my-build-plugin` が一覧に表示されていることを確認
4. トグルを ON にする

### 手順 5: 動作確認

プロジェクトをビルドすると、Build Log に `ROM が生成されました: ...` と表示されます。

---

## 14. よくある間違い

### `types` を文字列で書いてしまう

```jsonc
// ❌ 非推奨 (後方互換で動作はするが使わないこと)
{ "type": "build" }

// ✅ 正しい書き方
{ "types": ["build"] }
```

### `hooks` の宣言が `index.js` の実装と一致しない

`hooks` フィールドは宣言のみです。実装がなくても起動時エラーにはなりませんが、  
`invokeHook` を呼び出したときに `skipped: true` が返されます。  
宣言と実装は必ず一致させてください。

### `generateSource` と `generateSourceAsync` の混在

どちらか一方のみ実装してください。両方ある場合は `generateSourceAsync` が優先されます。

### 依存プラグインが存在しないのに `dependencies` に記載する

`setPluginEnabled` の `missingDependencies` に含まれます。  
存在しない ID は `dependencies` に記載しないでください。

### `context.logger` が undefined になる

`invokeHook` は `context` 引数が省略された場合、空オブジェクト `{}` を渡します。  
`context?.logger?.info(...)` のようにオプショナルチェーンを使うか、  
フック関数のデフォルト引数を `context = {}` にしてください。
