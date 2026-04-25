# Mega Drive エミュレーター — WASM 組み込みガイド

WASM 版エミュレーターを **他の Web アプリ / Electron アプリに埋め込む** ための手順書です。

---

## 目次

1. [Quick Start — 3 ステップで動かす](#1-quick-start)
2. [pkg/ ディレクトリの取得](#2-pkg-ディレクトリの取得)
3. [Vanilla HTML に組み込む](#3-vanilla-html-に組み込む)
4. [ES Module バンドラー (Vite / webpack)](#4-es-module-バンドラー-vite--webpack)
5. [Electron — Renderer プロセス](#5-electron--renderer-プロセス)
6. [Electron — Main プロセス (Node.js)](#6-electron--main-プロセス-nodejs)
7. [TypeScript プロジェクトでの利用](#7-typescript-プロジェクトでの利用)
8. [上級: カスタムレンダーループ / デバッグ API](#8-上級-カスタムレンダーループ--デバッグ-api)
9. [MdEmulator API リファレンス](#9-mdemulator-api-リファレンス)

---

## 1. Quick Start

### ステップ 1 — WASM パッケージをビルドする

```bash
# プロジェクトルートで実行
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg
```

生成された `frontend/pkg/` ディレクトリが WASM パッケージです。

### ステップ 2 — ファイルをコピーする

自分のプロジェクトの公開ディレクトリ（`public/` など）にコピーします:

```
your-project/
└── public/
    ├── pkg/                ← frontend/pkg/ をまるごとコピー
    │   ├── md_wasm.js
    │   ├── md_wasm_bg.wasm
    │   └── md_wasm.d.ts
    └── md-emulator.js      ← frontend/md-emulator.js をコピー
    └── md-emulator.d.ts    ← frontend/md-emulator.d.ts をコピー（TypeScript 利用時）
```

### ステップ 3 — コードを書く

```html
<canvas id="screen" width="320" height="224"></canvas>
<script type="module">
  import MdEmulator from './md-emulator.js';

  const emu = new MdEmulator({ wasmJsUrl: './pkg/md_wasm.js' });
  emu.attachCanvas(document.getElementById('screen'));
  await emu.init();

  // ROM は ArrayBuffer, Uint8Array, File, Blob のいずれかを渡す
  const res  = await fetch('./game.bin');
  const data = new Uint8Array(await res.arrayBuffer());
  await emu.loadRom(data, 'game.bin');
  emu.play();
</script>
```

完全なサンプルは [`frontend/embed-example.html`](../frontend/embed-example.html) を参照してください。

---

## 2. pkg/ ディレクトリの取得

### A) このリポジトリから直接ビルド

```bash
# dev ビルド（デバッグ情報あり、ファイルサイズ大きめ）
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg

# release ビルド（最適化済み、本番環境推奨）
wasm-pack build crates/md-wasm --target web --release --out-dir ../../frontend/pkg
```

生成物は `frontend/pkg/` に出力されます。

### B) 既存の pkg/ をコピー

ビルド済みの `frontend/pkg/` をそのまま使うこともできます。  
Service Worker のキャッシュ無効化が必要な場合は URL に `?v=<timestamp>` を付加してください。

### pkg/ ディレクトリの構成

| ファイル | 説明 |
|---------|------|
| `md_wasm.js` | ES Module ラッパー（wasm-bindgen 生成） |
| `md_wasm_bg.wasm` | WebAssembly バイナリ |
| `md_wasm.d.ts` | TypeScript 型定義（低レベル API） |
| `md_wasm_bg.wasm.d.ts` | WASM バインディング型 |
| `package.json` | npm パッケージメタデータ |

---

## 3. Vanilla HTML に組み込む

`<script type="module">` で `md-emulator.js` を直接インポートします。  
`pkg/` と `md-emulator.js` が同じサーバー上に置かれていれば、バンドラー不要です。

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <title>My MD App</title>
</head>
<body>
  <canvas id="screen" width="320" height="224"
          style="width:640px;height:448px;image-rendering:pixelated"></canvas>

  <script type="module">
    import MdEmulator from './md-emulator.js';

    const emu = new MdEmulator({ wasmJsUrl: './pkg/md_wasm.js' });
    emu.attachCanvas(document.getElementById('screen'));

    emu.addEventListener('ready', () => console.log('WASM ready'));
    emu.addEventListener('romloaded', () => emu.play());

    await emu.init();

    document.querySelector('#romFile').addEventListener('change', async (e) => {
      await emu.loadRom(e.target.files[0]);
    });
  </script>

  <input type="file" id="romFile" accept=".bin,.md,.gen,.smd" />
</body>
</html>
```

> **注意**: ES Module は HTTP(S) サーバー経由でしか動作しません。  
> `file://` プロトコルでは CORS エラーになります。  
> ローカルで試す場合は `python3 -m http.server 8000` などを使用してください。

---

## 4. ES Module バンドラー (Vite / webpack)

### Vite

```bash
npm create vite@latest my-md-app -- --template vanilla
cd my-md-app
```

**ファイル配置**:

```
my-md-app/
├── public/
│   └── pkg/              ← pkg/ をここに置く
├── src/
│   ├── md-emulator.js    ← md-emulator.js をここに置く
│   └── main.js
└── vite.config.js
```

**`vite.config.js`**:

```js
import { defineConfig } from 'vite';

export default defineConfig({
  // .wasm は public/ 経由でサーブするため optimizeDeps から除外
  optimizeDeps: {
    exclude: ['md_wasm'],
  },
});
```

**`src/main.js`**:

```js
import MdEmulator from './md-emulator.js';

const emu = new MdEmulator({ wasmJsUrl: '/pkg/md_wasm.js' });
await emu.init();
emu.attachCanvas(document.querySelector('#screen'));
```

> **`wasmJsUrl`** は `public/` 以下の絶対パスを指定します（`/pkg/md_wasm.js`）。  
> `initExplicit()` で .wasm URL を別途指定することもできます:

```js
import wasmInit from '/pkg/md_wasm.js?url';
import wasmBin   from '/pkg/md_wasm_bg.wasm?url';
await emu.initExplicit(wasmInit, wasmBin);
```

### webpack 5

```bash
npm install --save-dev webpack webpack-cli
```

**`webpack.config.js`**:

```js
module.exports = {
  experiments: {
    asyncWebAssembly: true,
  },
  module: {
    rules: [
      {
        test: /\.wasm$/,
        type: 'webassembly/async',
      },
    ],
  },
};
```

`md-emulator.js` 内で `import()` を使って WASM をロードしているため、  
webpack は非同期モジュールとして自動的に処理します。

---

## 5. Electron — Renderer プロセス

Electron の Renderer プロセスはブラウザ環境のため、WASM をそのまま使用できます。

> このリポジトリ内で Electron アプリを立ち上げる場合は、`electron/` ディレクトリに分離済みの土台があります。
> `cd electron && npm install && npm start` で起動できます（詳細は [docs/usage.md](usage.md) を参照）。

### `main.js` (Main プロセス)

```js
const { app, BrowserWindow } = require('electron');

app.whenReady().then(() => {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      // 必須: ES Module 動的 import と WASM を有効にする
      contextIsolation: true,
      nodeIntegration: false,     // セキュリティのため false を推奨
      webSecurity: true,
      // ローカルファイルを読む場合
      // allowRunningInsecureContent: false,
    },
  });

  win.loadFile('index.html');
});
```

### `index.html`

```html
<!DOCTYPE html>
<html>
<body>
  <canvas id="screen" width="320" height="224"></canvas>
  <script type="module" src="./renderer.js"></script>
</body>
</html>
```

### `renderer.js`

```js
import MdEmulator from './md-emulator.js';

const emu = new MdEmulator({ wasmJsUrl: './pkg/md_wasm.js' });
emu.attachCanvas(document.getElementById('screen'));

emu.addEventListener('ready', () => {
  console.log('Emulator ready, version:', emu.buildVersion);
});
emu.addEventListener('romloaded', () => emu.play());

await emu.init();
```

> **ファイルアクセス**: `contextIsolation: true` の場合、ローカルファイルへのアクセスは  
> preload スクリプト + `ipcRenderer` / `contextBridge` 経由で行います。

### Preload スクリプト経由でのローカル ROM 読み込み

**`preload.js`**:

```js
const { contextBridge, ipcRenderer } = require('electron');
const fs = require('fs');

contextBridge.exposeInMainWorld('electronAPI', {
  readRomFile: async (filePath) => {
    const buf = fs.readFileSync(filePath);
    return new Uint8Array(buf);
  },
  onRomSelected: (callback) => ipcRenderer.on('rom-selected', (_, path) => callback(path)),
});
```

**`renderer.js`**:

```js
window.electronAPI.onRomSelected(async (filePath) => {
  const bytes = await window.electronAPI.readRomFile(filePath);
  await emu.loadRom(bytes, filePath.split('/').pop());
  emu.play();
});
```

---

## 6. Electron — Main プロセス (Node.js)

> **推奨しない用途**: Main プロセスは DOM / Canvas を持たないため、  
> エミュレーターを映像出力なしで動かす場合（ヘッドレス自動化・AI 制御）が主な用途です。

### 方法 A: REST API サーバー経由（推奨）

Main プロセスから `md-api` サーバーを子プロセスとして起動し、HTTP で制御する方法です。  
描画は Renderer プロセスが担当します（`api-client.html` 参照）。

```js
const { spawn } = require('child_process');

const server = spawn('./target/release/md-api', [], {
  env: { ...process.env, MD_API_PORT: '8080' },
});

// HTTP でエミュレーターを制御
const res = await fetch('http://127.0.0.1:8080/api/v1/emulator/reset', { method: 'POST' });
```

詳細は [docs/api.md](api.md) を参照してください。

### 方法 B: `--target nodejs` ビルド（上級）

Node.js ネイティブ向けに WASM をビルドする場合:

```bash
wasm-pack build crates/md-wasm --target nodejs --out-dir ../../frontend/pkg-node
```

> **注意**: `--target nodejs` ビルドはブラウザ向けと別バイナリになります。  
> `require()` / CommonJS ベースのインターフェースになるため、  
> `md-emulator.js` のラッパーは使用できません（別途アダプターが必要です）。  
> 本番利用には REST API 経由を強く推奨します。

---

## 7. TypeScript プロジェクトでの利用

`md-emulator.d.ts` と `frontend/pkg/md_wasm.d.ts` をプロジェクトに含めます。

### ファイル配置

```
src/
├── md-emulator.js      ← JS 実装
├── md-emulator.d.ts    ← 型定義
└── app.ts              ← アプリコード
```

### `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "allowJs": true,
    "checkJs": false
  }
}
```

### `src/app.ts`

```typescript
import MdEmulator, { type MdEmulatorOptions } from './md-emulator.js';

const options: MdEmulatorOptions = {
  wasmJsUrl: '/pkg/md_wasm.js',
  audio: true,
  sram: true,
};

const emu = new MdEmulator(options);

emu.addEventListener('romloaded', (ev) => {
  const { sramRestored } = ev.detail;  // 型が推論される
  console.log('SRAM restored:', sramRestored);
  emu.play();
});

await emu.init();
emu.attachCanvas(document.querySelector<HTMLCanvasElement>('#screen')!);

// コントローラー入力（型補完が効く）
const B = MdEmulator.Buttons;
emu.setInput(1, B.UP | B.A);

// CPU 状態の読み出し
const state = emu.getCpuState();
console.log('PC:', state.m68k.pc.toString(16));
```

---

## 8. 上級: カスタムレンダーループ / デバッグ API

### フレームループを手動制御する

`play()` を使わず、自分でフレームを進める場合:

```js
const emu = new MdEmulator({ wasmJsUrl: './pkg/md_wasm.js', audio: false });
await emu.init();
await emu.loadRom(romData);

// オプション A: 1 フレーム単位
function tick() {
  emu.stepFrame();          // 1 フレーム進める
  renderToMyCanvas(emu);    // 独自描画
  requestAnimationFrame(tick);
}
tick();

// オプション B: サイクル単位
emu.step(7_670_454 / 60);   // 約 1 フレーム分のサイクル
```

### 生の EmulatorHandle でデバッグ API を使う

`emu.handle` から wasm-bindgen が生成した低レベル API に直接アクセスできます:

```js
const h = emu.handle;  // EmulatorHandle

// VDP レジスタを JSON で取得
const vdpRegs = h.get_vdp_registers_json();

// プレーン A を ARGB バッファとして取得
const planeA  = h.debug_render_plane('A');

// CRAM を色配列として取得
const cram    = h.debug_cram_colors_json();

// スプライト属性を取得
const sprites = h.debug_sprites_json();

// 実行トレースを取得
const trace   = h.trace_execution();

// ブレークポイント設定
h.set_breakpoint(0x1000);
```

### SRAM を手動でエクスポートする

```js
if (emu.hasSram()) {
  const data = emu.getSram();
  const blob = new Blob([data], { type: 'application/octet-stream' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'save.srm'; a.click();
  URL.revokeObjectURL(url);
}
```

---

## 9. MdEmulator API リファレンス

### コンストラクター

```js
new MdEmulator(options?)
```

| オプション | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `wasmJsUrl` | `string` | `'./pkg/md_wasm.js'` | WASM JS ラッパーの URL |
| `audio` | `boolean` | `true` | オーディオを有効にするか |
| `sram` | `boolean` | `true` | IndexedDB SRAM 自動保存を有効にするか |
| `sramAutoSaveFrames` | `number` | `300` | SRAM 自動保存の間隔（フレーム数） |

### 静的プロパティ

| プロパティ | 説明 |
|-----------|------|
| `MdEmulator.Buttons` | コントローラーボタンビットマスク定数 |

#### Buttons

| キー | 値 | 対応ボタン |
|-----|-----|---------|
| `UP` | `0x01` | 上 |
| `DOWN` | `0x02` | 下 |
| `LEFT` | `0x04` | 左 |
| `RIGHT` | `0x08` | 右 |
| `B` | `0x10` | B ボタン |
| `C` | `0x20` | C ボタン |
| `A` | `0x40` | A ボタン |
| `START` | `0x80` | スタート |

### メソッド

| メソッド | 説明 |
|---------|------|
| `init()` | WASM を初期化する。完了後 `ready` イベントを発行 |
| `initExplicit(jsUrl, wasmUrl)` | JS/WASM URL を明示して初期化（バンドラー向け） |
| `attachCanvas(canvas)` | 描画対象 canvas をアタッチ |
| `detachCanvas()` | canvas を切り離す |
| `loadRom(data, label?)` | ROM をロード（`romloaded` イベントを発行） |
| `play()` | フレームループを開始 |
| `pause()` | フレームループを停止 |
| `reset()` | ソフトリセット |
| `stepFrame()` | 1 フレームだけ手動で進める（停止中のみ） |
| `step(cycles)` | 指定サイクル数だけ進める |
| `stepInstruction()` | 1 M68K 命令だけ進める |
| `setInput(player, buttons)` | コントローラー状態を設定 |
| `saveState()` | 状態をシリアライズして `Uint8Array` で返す |
| `loadState(data)` | シリアライズ済みデータから状態を復元 |
| `hasSram()` | SRAM サポートの有無を返す |
| `getSram()` | SRAM バイト列を返す |
| `loadSram(data)` | SRAM を復元する |
| `setMuted(muted)` | ミュート状態を設定 |
| `getMemory(address, length)` | メモリを読み出す |
| `getCpuState()` | CPU レジスタ状態を返す |
| `setBreakpoint(address)` | ブレークポイントを設定 |
| `destroy()` | リソースを解放する |

### プロパティ (読み取り専用)

| プロパティ | 型 | 説明 |
|-----------|-----|------|
| `ready` | `boolean` | WASM が初期化済みか |
| `running` | `boolean` | フレームループが動作中か |
| `frameCount` | `number` | ROM ロード後からの累積フレーム数 |
| `muted` | `boolean` | ミュート状態 |
| `audioContext` | `AudioContext\|null` | 使用中の AudioContext |
| `handle` | `object\|null` | 生の EmulatorHandle（低レベル API） |
| `buildVersion` | `string` | ビルドタイムスタンプ |

### イベント

| イベント名 | `detail` 型 | 発行タイミング |
|-----------|------------|--------------|
| `ready` | `void` | WASM 初期化完了 |
| `romloaded` | `{ sramRestored: boolean }` | ROM ロード完了 |
| `frame` | `{ frame: number }` | フレーム描画後（毎フレーム） |
| `error` | `{ message: string, cause?: Error }` | エラー発生時 |

---

## 関連ドキュメント

- [docs/api.md](api.md) — REST / WebSocket / JSON-RPC API リファレンス
- [docs/usage.md](usage.md) — サーバー起動・フロントエンド利用方法
- [docs/spec.md](spec.md) — エミュレーター仕様
- [crates/md-wasm/README.md](../crates/md-wasm/README.md) — WASM クレートの詳細
