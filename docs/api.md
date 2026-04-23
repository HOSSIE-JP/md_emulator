# HTTP / WebSocket / JSON-RPC API

> **WASM として他プロジェクトへ組み込む場合は [docs/embedding.md](embedding.md) を参照してください。**  
> このドキュメントは REST/WebSocket/JSON-RPC API サーバー (`md-api`) の仕様を説明します。

ベースURL: `http://127.0.0.1:8080`

## REST エンドポイント

### GET /api/v1/health

- 用途: サーバー稼働確認
- レスポンス例: `{"ok": true}`

### GET /api/v1/logging

- 用途: APIログ出力の現在設定を取得
- レスポンス例: `{"enabled": false}`

### POST /api/v1/logging

- 用途: APIログ出力のON/OFFを切り替え
- Body例:

```json
{"enabled": true}
```

### POST /api/v1/input/controller

- 用途: コントローラ状態を注入（player 1/2）
- Body例:

```json
{"player": 1, "buttons": 145}
```

`buttons` はbitmask:

- `1<<0`: Up
- `1<<1`: Down
- `1<<2`: Left
- `1<<3`: Right
- `1<<4`: B
- `1<<5`: C
- `1<<6`: A
- `1<<7`: Start

### POST /api/v1/emulator/reset

- 用途: エミュレーターのリセット

### POST /api/v1/emulator/resume

- 用途: `pause` 済みエミュレーターの実行を再開

### POST /api/v1/emulator/step-instruction

- 用途: M68K 命令を 1 命令だけ実行（デバッグ用）

### POST /api/v1/emulator/breakpoint

- 用途: M68K ブレークポイントを追加
- Body例:

```json
{"address": 4096}
```

### POST /api/v1/emulator/step

- 用途: サイクルまたはフレーム単位で進める
- Body例（cycles指定）:

```json
{"cycles": 1000}
```

- Body例（frames指定）:

```json
{"frames": 1}
```

### POST /api/v1/emulator/load-rom

- 用途: ROMバイト列のロード
- Body例:

```json
{"rom": [0,1,2,3]}
```

### POST /api/v1/emulator/load-rom-path

- 用途: ローカルファイルパスからROMをロード
- Body例:

```json
{"path": "D:/homebrew/rom.bin"}
```

### GET /api/v1/emulator/save-state

- 用途: 現在状態の保存データ取得
- レスポンス例: `{"ok": true, "state": [...]}`

### POST /api/v1/emulator/load-state

- 用途: 保存状態の復元
- Body例:

```json
{"data": [1,2,3]}
```

### GET /api/v1/emulator/region

- 用途: 現在のビデオリージョン設定（NTSC/PAL）と自動判定状態を取得
- レスポンス例:

```json
{
  "region": "ntsc",
  "auto_detected": true
}
```

### POST /api/v1/emulator/region

- 用途: ビデオリージョンの手動設定、またはROMヘッダからの自動再判定
- Body例（手動設定）:

```json
{"region": "pal"}
```

- Body例（自動判定に戻す）:

```json
{"auto": true}
```

- 備考:
  - `region` は `ntsc` / `pal`
  - `auto: true` 指定時は `region` を無視して ROM ヘッダ（`0x1F0-0x1FF`）から再判定

### GET /api/v1/emulator/sram

- 用途: カートリッジ SRAM データ取得（バッテリーバックアップセーブ）
- レスポンス例:

```json
{
  "has_sram": true,
  "start": 2097152,
  "end": 2162687,
  "size": 32768,
  "flags": 32,
  "data_base64": "<base64 encoded SRAM bytes>"
}
```

### POST /api/v1/emulator/sram

- 用途: カートリッジ SRAM データ書き込み（ファイルからのセーブ復元など）
- Body例:

```json
{"data_base64": "<base64 encoded SRAM bytes>"}
```

- レスポンス例: `{"ok": true, "loaded_bytes": 32768}`

### GET /api/v1/cpu/state

- 用途: CPU状態取得（M68K/Z80）

### GET /api/v1/cpu/memory?addr=<u32>&len=<usize>

- 用途: メモリ範囲の読み出し

### GET /api/v1/cpu/trace

- 用途: 命令実行トレース（最新64命令のリングバッファと例外発生時のスナップショット）
- レスポンス例:

```json
{
  "exception_trace": [...],
  "trace_ring": [{"pc": 22344, "opcode": 20089, "mnemonic": "MOVE.L D1,D1"}, ...]
}
```

### GET /api/v1/rom/info

- 用途: ROMロード状態とROMヘッダ情報の取得

### GET /api/v1/video/frame

- 用途: 現在フレームのARGBピクセルを取得（frontend Canvas描画用）
- レスポンス例:

```json
{
  "width": 320,
  "height": 224,
  "pixels_argb": [4278190080, 4278255873, 4278321666]
}
```

### GET /api/v1/vdp/cram

- 用途: CRAM（カラーRAM）の生データ取得（16-bit値 × 64エントリ）
- レスポンス例: `{"cram": [0, 292, 584, ...]}`

### GET /api/v1/vdp/registers

- 用途: VDPレジスタ状態とデバッグ情報の取得
- レスポンス例:

```json
{
  "registers": [4, 116, 48, ...],
  "code": 0, "address": 49152,
  "status": 13312, "frame": 60,
  "data_writes": 8640, "ctrl_writes": 120
}
```

### GET /api/v1/vdp/vram?addr=&lt;u32&gt;&len=&lt;usize&gt;

- 用途: VRAM範囲の読み出し
- レスポンス例: `{"addr": 0, "data": [0, 0, 17, ...]}`

### GET /api/v1/vdp/plane?name=A|B|W

- 用途: スクロールプレーン全体をARGBバッファとして描画
- パラメータ: `name` = `A`（Plane A）, `B`（Plane B）, `W`（Window）
- レスポンス例:

```json
{
  "plane": "A",
  "width": 512,
  "height": 256,
  "pixels_argb": [4278190080, ...]
}
```

### GET /api/v1/vdp/tiles?palette=0

- 用途: VRAM全2048タイル（32列×64行のシート）をARGBバッファとして描画
- パラメータ: `palette` = 0〜3（使用するCRAMパレット番号）
- レスポンス例:

```json
{
  "palette": 0,
  "width": 256,
  "height": 512,
  "pixels_argb": [4278190080, ...]
}
```

### GET /api/v1/vdp/colors

- 用途: CRAM全64色をARGB値に変換して取得
- レスポンス例:

```json
{
  "colors_argb": [4278190080, 4280624164, ...]
}
```

### GET /api/v1/vdp/sprites

- 用途: スプライト属性テーブル（SAT）の解析結果を取得
- レスポンス例:

```json
{
  "sprites": [
    {
      "index": 0, "x": 128, "y": 128,
      "width": 2, "height": 2,
      "tile": 256, "palette": 0,
      "priority": false, "hflip": false, "vflip": false,
      "link": 1
    }
  ]
}
```

### GET /api/v1/audio/samples?frames=N

- 用途: オーディオサンプルの取得（ステレオ f32 PCM）
- パラメータ: `frames` = 取得するサンプルフレーム数（デフォルト: 800）
- レスポンス例:

```json
{
  "sample_rate": 48000,
  "channels": 2,
  "samples": [0.0, 0.0, 0.0123, -0.0456, ...]
}
```

### GET /api/v1/apu/state

- 用途: YM2612/PSG/Z80 の内部デバッグ状態を取得

レスポンスの `cpu` には既存の `m68k`, `z80_pc`, `z80_cycles` に加えて、Z80 の全レジスタと割り込み状態を含む `z80` オブジェクトが含まれます。
- 主なフィールド:

`dac_enabled`, `dac_data`, `debug_dac_nonzero`, `debug_fm_nonzero`, `ym_write_total`, `z80_pc`, `z80_total_cycles`, `z80_bank_68k_addr`, `regs_port0_2b`, `z80_banked_read_log`, `z80_trace_ring`

- YM 書き込みログ:

`ym_write_log_first100`: 直近100件のYM書き込み

`ym_write_log_recent_non_dac`: 直近100件の非 DAC データ書き込み（`$2A` を除外）。DAC enable (`$2B`) や通常 FM レジスタ設定の追跡用

`z80_banked_read_log`: Z80 が banked window 経由で読んだ直近64件の 68K 側アドレスと値。ROM/68K RAM から音声データを引く処理の追跡用

`z80_trace_ring`: 直近32件の Z80 命令トレース。サウンドドライバのループや割り込み受理状況の確認用

### GET /api/v1/version

- 用途: 実行中バイナリのビルド識別子を取得
- レスポンス例:

```json
{
  "version": "0.1.0+20260326-005140.abcdef123456.dirty"
}
```

- 形式:

`<crate version>+<最新ソース更新UTC時刻>.<git short sha>[.dirty]`

- 手動更新は不要。`md-core` の build script がソース更新時刻と Git 状態から自動生成する

## WebSocket

- URL: `ws://127.0.0.1:8080/api/v1/ws`
- 送受信形式: JSON-RPC風（テキストメッセージ）

## JSON-RPC風 HTTP

- URL: `POST /api/v1/mcp/rpc`
- 形式: `{"jsonrpc":"2.0","id":...,"method":"...","params":{...}}`

### サポートメソッド

- `load_rom` (`params.rom`)
- `load_rom_path` (`params.path`)
- `reset`
- `step` (`params.cycles`)
- `run_frame`
- `get_video_region`
- `set_video_region` (`params.region` = `"ntsc" | "pal"`)
- `auto_video_region`
- `pause`
- `resume`
- `set_breakpoint` (`params.address`)
- `step_instruction`
- `set_controller_state` (`params.player`, `params.buttons`)
- `get_registers`
- `get_cpu_state`
- `trace_execution`
- `get_rom_info`
- `get_memory` (`params.address`, `params.length`)
- `get_vram`
- `get_cram`
- `save_state`
- `load_state` (`params.state`)

## エラー

- パース失敗: `code = -32700`
- メソッド未定義: `code = -32601`
- 内部エラー: `code = -32603`
