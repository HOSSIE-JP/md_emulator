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

ビルド後は `frontend/pkg` にブラウザ向けバンドルが生成され、`frontend/wasm.html` から API を介さず直接実行できます。

> 注: `frontend/index.html` は REST 疎通確認用、`frontend/wasm.html` は md-wasm を直接使うプレイヤーです。
