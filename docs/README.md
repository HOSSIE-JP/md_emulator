# Mega Drive Emulator ドキュメント

このディレクトリには、現在実装されているエミュレーターの仕様・セットアップ・利用方法をまとめています。

## 目次

- [セットアップ](./setup.md)
- [実行して試す](./usage.md)
- [仕様とAPI](./spec.md)
- [HTTP / WebSocket / JSON-RPC API](./api.md)

## 最短で試す手順

1. Rust をインストール（`rustup`）
2. プロジェクトルートで `cargo test --workspace` を実行
3. APIサーバーを起動: `cargo run -p md-api`
4. 別ターミナルからヘルスチェック:  
   `Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/health`
5. ROMをロード:  
   `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/v1/emulator/load-rom-path -ContentType 'application/json' -Body '{"path":"D:/homebrew/rom.bin"}'`
6. ROM情報を確認:  
   `Invoke-RestMethod -Method Get http://127.0.0.1:8080/api/v1/rom/info`
7. `frontend` の簡易UIを静的サーバーで開いて `Reset` / `Step` を試す
8. 必要なら `wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg` を実行し、`frontend/wasm.html` で API を介さず確認する
