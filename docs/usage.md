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

## 3) 簡易フロントエンドで試す

別ターミナルで `frontend` を配信し、ブラウザで開きます。

```powershell
python -m http.server 5500 --directory frontend
```

ブラウザで `http://127.0.0.1:5500` を開き、`Reset` と `Step 1 frame` を押すと、APIレスポンスを確認できます。

`ROM path` にROMファイルパスを入力し、`Load ROM Path` → `ROM Info` → `Step 10 frames` の順で操作すると、
ROMロード状態と実行進行をまとめて確認できます。

`Run Preview` を押すとVBlank同期ベース（60fps目標）で `step + video/frame取得` を繰り返し、Canvasにフレームが描画されます。
`Toggle API Log` でサーバーログをON/OFFできます。

### VDP デバッグビューア

`http://127.0.0.1:5500/debug.html` を開くと、VDPの内部状態を視覚的に確認できます。

- **Scroll Planes**: Plane A / Plane B / Window の全面レンダリング
- **Tiles**: VRAM全2048タイルのシート表示（パレット選択可能）
- **CRAM**: 64色パレットのカラーグリッド（4パレット×16色）
- **Sprites**: スプライト属性テーブル（座標・サイズ・タイル・反転・優先度）
- **Frame**: 合成済みフレーム

`Refresh All` で全データ取得、`Auto Refresh` で500ms間隔の自動更新が可能です。

キーボード入力（player1）:

- 方向: `Arrow` または `WASD`
- `B`: `J`
- `C`: `K`
- `A`: `U`
- `Start`: `Enter`

## 4) JSON-RPC風APIで試す（AIエージェント向け）

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

## 5) テストで動作確認

```powershell
cargo test --workspace
```

コア周辺だけ確認したい場合:

```powershell
cargo test -p md-cpu-m68k
cargo test -p md-cpu-z80
cargo test -p md-vdp
cargo test -p md-apu
cargo test -p md-core --lib
```
