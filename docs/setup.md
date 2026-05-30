# セットアップ

## 前提

- OS: Windows / Linux / macOS
- 必須: Rust stable（`rustup` + `cargo`）
- 任意:
  - Webフロント確認用の静的ファイルサーバー（`python -m http.server` など）
  - WASMビルド用 `wasm-pack`

## Rust の導入

### Windows (PowerShell)

公式サイトから `rustup-init.exe` を実行し、インストール後に確認します。

```powershell
rustc --version
cargo --version
```

## プロジェクト取得後の初期確認

プロジェクトルートで実行:

```powershell
cargo check --workspace
cargo test --workspace
```

## 主要クレート

- `md-core`: エミュレーター統合コア（M68K/Z80/VDP/APU統合）
- `md-api`: HTTP + WebSocket + JSON-RPC風エンドポイント
- `md-wasm`: WebAssembly向けバインディング
- `md-cpu-m68k`, `md-cpu-z80`, `md-vdp`, `md-apu`, `md-bus`: 各サブシステム

## WASM（任意）

`md-wasm` は `cdylib` を出力する設定です。`wasm-pack` を使う場合の例:

```powershell
cargo install wasm-pack --locked
npm run wasm:build
```

ビルド後は `frontend/pkg` にブラウザ向けバンドルが生成され、同時に `frontend/sw.js` と `frontend/roms/index.json` も更新されます。`frontend/index.html` から API を介さず直接実行できます。

> 注: `frontend/index.html` が md-wasm プレイヤー本体です。`frontend/wasm.html` は `index.html` へリダイレクトします。

## Bundled ROM

`npm run wasm:build` / `npm run wasm:build:release` は、`frontend/roms/` 配下のファイル一覧から `frontend/roms/index.json` を再生成します。WASM プレイヤーでは、画面上のファイル選択またはドラッグ&ドロップでもROMを読み込めます。


## MD/PCE Game Editor split

- MD Game Editor and PCE Game Editor are now separate Electron apps: use `npm --prefix md-game-editor start` for Mega Drive work and `npm --prefix pce-game-editor start` for PC Engine work.
- Each app has its own `userData`, `projects`, `tools`, plugins, templates, package metadata, and packaging output name.
- PCE Game Editor performs a one-time non-destructive copy of existing PC Engine projects from the old MD editor project locations. Existing folders in the PCE target are never overwritten. PC Engine builds are standardized on llvm-mos-sdk; cc65 is not exposed in the PCE setup flow.
- Built-in PCE plugins live under `pce-game-editor/plugins`; `md-game-editor/plugins` keeps Mega Drive plugins plus shared `supportedCores: ["*"]` plugins such as `code-editor`.
