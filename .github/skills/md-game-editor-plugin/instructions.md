---
applyTo: "**"
---

# MD Game Editor Plugin Generator — Copilot Instructions

> **自律アップデート指示**
> このファイルはユーザーが MD Game Editor 向けプラグインを生成させるためにプロジェクトに配置する指示書です。
> - MD Game Editor の `electron/PLUGIN.md` や `electron/plugin-manager.js` が変更されたとき、この指示書の該当部分を更新すること
> - SGDK の `main()` シグネチャや API が変更されたとき、「SGDK コード規約」セクションを更新すること
> - プラグインシステムのフック仕様が追加・変更されたとき、「フック早見表」を更新すること
> - 更新後は末尾の「Last Updated」を書き換えること

---

## このファイルの目的

このプロジェクトは **SGDK (Sega Genesis Development Kit)** で作られた Mega Drive / Genesis 向けゲームです。

GitHub Copilot は以下のタスクを依頼されることがあります:

1. **このゲームプロジェクトを解析**して、MD Game Editor が使用できるプラグインを生成する
2. **既存プラグインを改修**してアセット構成の変化に対応させる
3. **新しいプラグインタイプ**（editor / emulator / converter）や renderer module を追加する

---

## プロジェクト構造（このファイルが配置されたリポジトリ）

```
<project-root>/
├── src/
│   └── main.c          ← ゲームのエントリポイント (SGDK)
├── res/
│   └── resources.res   ← Rescomp アセット定義
├── project.json        ← MD Game Editor のプロジェクト設定
└── .github/
    └── instructions.md ← このファイル
```

---

## プラグイン生成タスクの手順

Copilot がプラグインを生成するとき、以下の順序で作業すること:

### Step 1: プロジェクトを解析する

1. `res/resources.res` を読んで全アセット（タイプ・名前・パス）を把握する
2. `src/main.c` を読んでゲームロジックの構造を把握する
3. `project.json` を読んで `builderPlugin` / `emulatorPlugin` フィールドを確認する

### Step 2: manifest.json を作成する

```jsonc
{
  "id": "<plugin-id>",          // フォルダ名と一致（英小文字・ハイフンのみ）
  "name": "<表示名>",
  "description": "<説明>",
  "version": "1.0.0",
  "types": ["build"],           // 必ず配列
  "hooks": ["onBuildStart", "onBuildEnd"],
  "permissions": ["project.read", "project.write", "build.configure"],
  "roles": [
    { "id": "builder", "label": "Build", "exclusive": true, "order": 10 }
  ],
  "renderer": {                  // UI/capability を提供する場合のみ
    "entry": "renderer.js",
    "styles": ["style.css"],
    "page": "my-page",
    "capabilities": ["page"]
  }
}
```

### Step 3: index.js を作成する

```js
'use strict';

const manifest = require('./manifest.json');

/**
 * @param {Array<{type:string, name:string, sourcePath:string, sourceAbsolutePath:string}>} assets
 * @param {{ projectDir: string, logger: object }} context
 */
function generateSource(assets, context) {
  // このプロジェクトのアセット構成に合わせてコードを生成する
  return { ok: true, sourceCode: '/* generated */' };
}

function onBuildStart(payload, context) {
  context.logger.info(`ビルド開始: ${payload.projectDir}`);
  return { ok: true };
}

module.exports = { generateSource, onBuildStart };
```

### renderer.js を持つ場合

Plugin Runtime v2.4 では、Assets / Code / Converter のような機能固有 UI を本体 `electron/renderer/renderer.js` に追加しない。
プラグイン配下の `renderer.js` で capability を登録する。

```js
export function activatePlugin({ plugin, root, pageRoot, hostRoot, api, logger, registerCapability }) {
  const modal = api.createModal({
    id: `${plugin.id}-modal`,
    html: '<p>Plugin UI</p>',
  });
  registerCapability('my-capability', { root });
  logger.info(`${plugin.id} renderer activated`);
  return {
    deactivate() {
      modal.destroy();
    },
  };
}
```

`renderer.entry` と `renderer.styles` は plugin ディレクトリ内の相対パスに限定する。`../` や絶対パスで plugin 外へ出る指定は禁止。
ページを持たない converter でも `hostRoot` が渡されるため、独自 modal や背景処理のために本体 HTML を変更しない。
プラグイン同士の連携は `api.capabilities.get()` / `api.capabilities.require()` / `api.events.on()` / `api.events.emit()` を使い、本体側に個別 plugin ID の分岐を追加しない。
renderer から main process hook を呼ぶ場合は `hooks` と `mainApi.hooks` の両方に宣言し、`api.plugins.invokeHook()` または `window.electronAPI.invokePluginHook()` を使う。
asset type / import / image 変換は `asset-type-provider` / `asset-import-handler` / `image-import-pipeline` capability として登録する。
Build / Test Play など単一選択 plugin は `roles` で宣言し、project.json の標準保存先は `pluginRoles` とする。
`permissions` は v2.4 では表示・レビュー用途の宣言で、sandbox 強制ではない。
新規 plugin で本体 `main.js` / `preload.js` / `build-system.js` の個別追記が必要に見える場合は、まず Runtime v2.4 の汎用 API 不足として扱う。

### Step 4: 配置場所を案内する

生成したプラグインフォルダを以下のどちらかに配置するようユーザーに案内する:

- **開発時** → MD Game Editor リポジトリの `electron/plugins/<plugin-id>/`
- **パッケージ済みアプリ** → `<userData>/plugins/<plugin-id>/`  
  （Settings > Plugins 画面の「📂 フォルダを開く」から開ける）

---

## SGDK コード規約（必須）

### main 関数シグネチャ

```c
/* SGDK 2.11 以降 — 必須シグネチャ */
int main(bool hardReset)
{
    (void)hardReset;
    /* ... */
    return 0;
}
```

> ⛔ `void main()` や `int main(void)` は **使用禁止**。ビルド警告が発生する。

### よく使う SGDK API

```c
#include <genesis.h>

// 画面
VDP_setScreenWidth320();
VDP_drawImage(BG_B, &myImage, 0, 0);
VDP_clearPlane(BG_B, TRUE);

// パレット
PAL_setColors(0, (u16*)palette_black, 64, CPU);
PAL_fadeIn(0, 63, savedPal, 20, FALSE);
PAL_fadeOut(0, 63, 10, FALSE);

// ジョイパッド
u16 btn = JOY_readJoypad(JOY_1);
if (btn & BUTTON_A) { /* ... */ }

// 音楽 (XGM2)
XGM2_loadDriver(TRUE);
XGM2_play(bgm);
XGM2_stop();

// Vblank
SYS_doVBlankProcess();
```

---

## resources.res の読み方

各行のフォーマット:

```
TYPE   name   "ファイルパス"   [追加パラメータ]
```

| タイプ | C の extern 型 | 説明 |
|---|---|---|
| `IMAGE` | `const Image name;` | 背景画像 (最大 320×224px) |
| `SPRITE` | `const SpriteDefinition name;` | スプライト定義 |
| `XGM2` | `const u8 name[];` | FM 音楽 (SGDK 2.x 推奨) |
| `XGM` | `const u8 name[];` | FM 音楽 (旧形式) |
| `WAV` | `const u8 name[];` | PCM サウンド |
| `TILESET` | `const TileSet name;` | タイルセット |
| `MAP` | `const Map name;` | タイルマップ |
| `PALETTE` | `const Palette name;` | パレット定義 |

生成コードでは `resources.h` をインクルードすることで extern 宣言が自動で提供される:

```c
#include <genesis.h>
#include "resources.h"
```

---

## フック早見表

| フック | 呼ばれるタイミング | payload の主要フィールド |
|---|---|---|
| `onBuildStart` | ビルド開始直前 | `projectDir` |
| `onBuildLog` | ビルドログ 1 行ごと | `text`, `level` |
| `onBuildEnd` | ビルド成功後 | `projectDir`, `romPath`, `elapsed` |
| `onBuildError` | ビルド失敗時 | `projectDir`, `error` |
| `onTestPlay` | Test Play ボタン押下 | `romPath` |
| `generateSource` | ジェネレータ実行時 | *(assets 配列)* |

---

## generateSource の実装ルール

1. **バリデーション優先**: 必要なアセットが存在しない場合は `{ ok: false, error: "説明" }` を返す
2. **生成コードの先頭コメント**: `/* Generated by <plugin-id> v<version> */` を必ず入れる
3. **アセット名から変数名を動的生成**: ハードコードを避ける
4. **SGDK ヘッダのみ使用**: `#include <genesis.h>` と `#include "resources.h"` だけで完結させる
5. **エラーは例外でなく返り値で**: `throw` ではなく `{ ok: false, error }` を使う

---

## project.json へのプラグイン登録

プラグインを生成したら、`project.json` の `builderPlugin` を更新するよう案内する:

```json
{
  "name": "My Game",
  "author": "Your Name",
  "serial": "GM MYGAME-00",
  "region": "JPN",
  "builderPlugin": "<新しいプラグインのid>",
  "emulatorPlugin": "standard-emulator"
}
```

---

## OSS / ライセンス遵守

- 生成するすべてのコードは **オリジナル実装** とする
- 外部リポジトリのコードを直接コピーしない
- SGDK 公式 API の使用は問題ない
- GPL/AGPL コードを参考に実装した場合は制御フローを変えて書き直す

---

*Last Updated: 2026-04 / SGDK 2.11 / Plugin Runtime v2.4*
