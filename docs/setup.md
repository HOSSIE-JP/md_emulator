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
cargo install wasm-pack
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg
```

ビルド後は `frontend/pkg` にブラウザ向けバンドルが生成され、`frontend/index.html` から API を介さず直接実行できます。

> 注: `frontend/index.html` が md-wasm プレイヤー本体です。`frontend/wasm.html` は `index.html` へリダイレクトします。

## Bundled ROM 更新

`index.html` の Bundled ROM 選択肢は `frontend/roms/index.json` を参照します。

1. ルート `roms/` にROMを配置
2. `frontend/roms/` にコピー
3. `frontend/roms/index.json` を更新

VS Code Tasks を使う場合は `Frontend: Refresh Bundled ROMs` を実行してください。
