# 実行して試す

## 1) APIサーバーを起動

プロジェクトルートで実行:

```powershell
cargo run -p md-api
```

ログを最初から有効化したい場合（PowerShell）:

```powershell
$env:MD_API_LOG = "1"
cargo run -p md-api
```

起動後、`http://127.0.0.1:8080` で待ち受けます。

## 2) REST APIを手動で叩く（PowerShell）

### ヘルスチェック

```powershell
Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/health
```

### リセット

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8080/api/v1/emulator/reset
```

### ROMをファイルパスでロード

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/emulator/load-rom-path `
  -ContentType 'application/json' `
  -Body '{"path":"D:/homebrew/rom.bin"}'
```

### ROMヘッダ情報を確認

```powershell
Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/rom/info
```

### APIログON/OFFを切り替え

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/logging `
  -ContentType 'application/json' `
  -Body '{"enabled":true}'
```

現在設定の確認:

```powershell
Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/logging
```

### 1フレーム進める

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/emulator/step `
  -ContentType 'application/json' `
  -Body '{"frames":1}'
```

### CPU状態を取得

```powershell
Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/cpu/state
```

### メモリを読む（例: 0番地から16バイト）

```powershell
Invoke-RestMethod -Method Get "http://127.0.0.1:8080/api/v1/cpu/memory?addr=0&len=16"
```

## 3) APIフロントエンドで試す

別ターミナルで `frontend` を配信し、ブラウザで開きます。

```powershell
python -m http.server 5500 --directory frontend
```

ブラウザで `http://127.0.0.1:5500/api-client.html` を開くと、REST APIの手動検証UIを使えます。

`ROM path` にROMファイルパスを入力し、`Load ROM Path` → `ROM Info` → `Step 10 frames` の順で操作すると、
ROMロード状態と実行進行をまとめて確認できます。

`Run Preview` を押すとVBlank同期ベース（60fps目標）で `step + video/frame取得` を繰り返し、Canvasにフレームが描画されます。
`Toggle API Log` でサーバーログをON/OFFできます。

### オーディオ再生

`Unmute` ボタンをクリックすると、Web Audio API経由でゲーム音声の再生が開始されます（ブラウザのユーザージェスチャー要件に対応）。
`Run Preview` 中に `Unmute` を押すとリアルタイムで音声が再生されます。音声はAPIサーバーから48kHzステレオサンプルを取得して再生します。
再度ボタン（`Mute`）を押すとミュートします。

### VDP デバッグビューア

`http://127.0.0.1:5500/debug.html` を開くと、VDPの内部状態を視覚的に確認できます。

- **Scroll Planes**: Plane A / Plane B / Window の全面レンダリング
- **Tiles**: VRAM全2048タイルのシート表示（パレット選択可能）
- **CRAM**: 64色パレットのカラーグリッド（4パレット×16色）
- **Sprites**: スプライト属性テーブル（座標・サイズ・タイル・反転・優先度）
- **Frame**: 合成済みフレーム

コピー支援:

- `Copy Snapshot`: レジスタ、CRAM、スプライト、各画像のハッシュ付き要約をまとめてクリップボードへコピー
- `Copy Active Tab`: 現在タブの生JSONをコピー
- 各パネルの `Copy JSON`: 対象セクションだけをコピー
- CRAMセルをクリック: その色だけをコピー

`Refresh All` で全データ取得、`Auto Refresh` で500ms間隔の自動更新が可能です。

キーボード入力（player1）:

- 方向: `Arrow` または `WASD`
- `B`: `J`
- `C`: `K`
- `A`: `U`
- `Start`: `Enter`

## 4) WASM 直実行プレイヤーで試す

API を介さずブラウザ内で直接実行したい場合は、先に WASM バンドルを生成します。

```powershell
cargo install wasm-pack
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg
python -m http.server 5500 --directory frontend
```

その後、`http://127.0.0.1:5500/index.html` を開きます（`wasm.html` は `index.html` へリダイレクト）。

- ROM選択（Bundled ROM選択またはローカルファイル選択）で **自動的に Load → Run** が開始
- 音声はデフォルトで有効（初回ユーザー操作時に有効化）
- `Run` / `Pause`: 実行の一時停止と再開
- `Step`: Developer Mode を ON にしたときのみ表示されるデバッグ機能
- `Mute` / `Unmute`: 音声の切り替え

このページは描画・入力・音声をすべて md-wasm から処理するため、REST API 経由の遅延や同期ずれを切り分ける用途に使えます。

### 補足: ローカルファイル直接起動について

`index.html` は ES Modules (`type="module"`) と WASM のロードを行うため、`file://` で直接開くとブラウザの制約で失敗します。
必ず HTTP サーバー経由で開いてください。

## 5) GitHub Pages で公開する（リリースタグ時）

このリポジトリは `v*` 形式のタグ push 時に Pages デプロイを行う想定です。

例:

```bash
git tag v0.1.0
git push origin v0.1.0
```

デプロイワークフローでは以下を実施します。

1. `wasm-pack` で `frontend/pkg` を再生成
2. `wasm-opt -Oz` で `md_wasm_bg.wasm` を最適化
3. リポジトリ `roms/` 配下の ROM を `frontend/roms/` へ取り込み
4. `frontend/roms/index.json` を自動生成
5. `frontend/` を GitHub Pages へデプロイ

公開URL（Project Pages）:

`https://<user>.github.io/md_emulator/`

## 6) PWA として使う

WASM プレイヤーは PWA 対応済みです。

- `manifest.webmanifest` を配信
- `sw.js`（Service Worker）でアセットをキャッシュ
- 対応ブラウザでは「Install App」ボタンでインストール可能

インストール後はスタンドアロン表示で起動できます。初回起動時に必要ファイルがキャッシュされます。

## 7) JSON-RPC風APIで試す（AIエージェント向け）

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/mcp/rpc `
  -ContentType 'application/json' `
  -Body '{"jsonrpc":"2.0","id":1,"method":"step","params":{"cycles":1000}}'
```

ROMをパスでロードするJSON-RPC例:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/mcp/rpc `
  -ContentType 'application/json' `
  -Body '{"jsonrpc":"2.0","id":2,"method":"load_rom_path","params":{"path":"D:/homebrew/rom.bin"}}'
```

## 8) テストで動作確認

```powershell
cargo test --workspace
```

コア周辺だけ確認したい場合:

```powershell
cargo test -p md-cpu-m68k
cargo test -p md-cpu-z80

## 9) Electron デスクトップ版（土台）を試す

このリポジトリには、既存の `frontend/` と分離した Electron アプリ土台を `electron/` 配下に用意しています。

### 前提

- Node.js 18+
- `frontend/pkg/` が生成済みであること（未生成なら先に `wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg` を実行）

### 初回セットアップ

```bash
cd electron
npm install
```

### 開発起動

```bash
cd electron
npm start
```

`npm start` は以下を順に実行します。

1. `npm run copy-pkg` で `frontend/pkg/` と `frontend/md-emulator.js` を `electron/` 配下へコピー
2. Electron アプリを起動

### 使い方

- `Mode` を `WASM (Renderer)` にすると、Renderer 内で wasm を直接実行
- `Mode` を `REST API (md-api)` にすると、`Start API` で `md-api` を起動し REST で制御
- `Open ROM` または `File > Open ROM...` で ROM をロード

### 配布ビルド

```bash
cd electron
npm run build:mac
npm run build:win
```

出力先は `electron/dist/` です。
cargo test -p md-vdp
cargo test -p md-apu
cargo test -p md-core --lib
```

## 9) ビルドとROM更新の運用ガイド

### WASM版は毎回ビルドが必要か？

- `crates/md-wasm` / `crates/md-core` / `crates/md-apu` / `crates/md-vdp` / `crates/md-cpu-*` / `crates/md-bus` を変更した場合は、`frontend/pkg` を再生成するため **WASMビルドが必要** です。
- フロントHTML/CSS/JSだけ変更した場合は、通常WASM再ビルドは不要です。

### Bundled ROM を更新する手順

1. ルートの `roms/` にROMファイル（`.bin/.md/.gen/.smd/.sms/.zip`）を追加・更新
2. `frontend/roms/` へ同期
3. `frontend/roms/index.json` を再生成

### VS Code Tasks（推奨）

- `WASM: Build Package (dev)`
- `WASM: Build Package (release)`
- `Frontend: Refresh Bundled ROMs`
- `WASM: Rebuild and Refresh ROMs`

`WASM: Rebuild and Refresh ROMs` を実行すれば、開発で必要なWASM再ビルドとBundled ROM更新をまとめて実施できます。

## 10) 他プロジェクトへの組み込み

WASM 版エミュレーターを外部の Web アプリや Electron アプリに組み込む場合は、
`frontend/md-emulator.js` ラッパーと `frontend/pkg/` を使用します。

### 最小例

```bash
# 1. WASM をビルド
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg

# 2. 必要ファイルを自分のプロジェクトにコピー
cp -r frontend/pkg/   your-project/public/pkg/
cp frontend/md-emulator.js   your-project/public/
cp frontend/md-emulator.d.ts your-project/public/   # TypeScript の場合
```

```js
// your-project/main.js
import MdEmulator from './md-emulator.js';

const emu = new MdEmulator({ wasmJsUrl: './pkg/md_wasm.js' });
await emu.init();
emu.attachCanvas(document.querySelector('canvas'));
await emu.loadRom(romBytes);
emu.play();
```

動作確認用の最小サンプルは `frontend/embed-example.html` です:

```bash
# http://localhost:8000/embed-example.html を開く
python3 -m http.server 8000 --directory frontend
```

**詳細な手順・Electron 対応・TypeScript 利用方法は [docs/embedding.md](embedding.md) を参照してください。**
