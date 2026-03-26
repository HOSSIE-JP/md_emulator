# 仕様とAPI

## 現在の実装方針

- 正確性重視で段階的に実装を拡張
- コアは `md-core` に統合し、CPU/VDP/APU/Busを分離
- 外部制御（REST / WebSocket / JSON-RPC風）を提供
- 状態観測（CPU状態、メモリ、トレース、state save/load）を重視

## コア機能（`md-core`）

- ROMロード: `load_rom`, `load_rom_bytes`
- ROM情報: `rom_loaded`, `get_rom_info`
- 実行制御: `reset`, `step(cycles)`, `run_frame`, `pause`, `resume`, `step_instruction`
- 状態取得: `get_cpu_state`, `get_memory`, `get_vram`, `get_cram`, `get_framebuffer_argb`
- デバッグ: `set_breakpoint`, `trace_execution`
- 入力注入: `set_controller_state`
- 状態保存復元: `save_state`, `load_state`

`reset()` 時にROMがロード済みの場合は、ベクタテーブル先頭から初期SSP/初期PCを読み取ってM68Kへ反映します。

## サブシステム概要

### M68K (`md-cpu-m68k`)

- 命令デコード/実行の基盤を実装
- 代表的なMOVE系、分岐系、例外処理、サイクル予算実行を実装
- 命令テスト群を追加済み

### Z80 (`md-cpu-z80`)

- 基本命令（NOP/LD/XOR/INC/DEC/JR/JP）を実装
- 命令単位実行とサイクル予算実行を提供

### VDP (`md-vdp`)

- VRAM/CRAM/VSRAM 管理
- データ/コントロールポートアクセス（ワード・バイト両対応）
- レジスタ書き込み、HVカウンタ、DMA要求/実行
- DMA 68K転送（ワード単位、アドレスマスク付き）、DMA Fill、DMA Copy（addr^1書き込み）
- スクロールプレーンA/B描画（HScroll mode 0/2/3, VScroll mode 0/1[per-2-column]）
- ウィンドウプレーン描画（水平/垂直分割、Window優先度対応）
- スプライト描画（リンクチェーン順優先）
- 優先度合成（スプライト/プレーンA/プレーンB × high/low priority）
- シャドウ/ハイライトモード（R0C bit3、パレット3色14=シャドウ演算子、色15=ハイライト演算子）
- VBlank/HBlank割り込みフラグ管理、ステータスレジスタ
- フレームバッファ生成（320×224 ARGB）
- デバッグ用プレーン/タイル/スプライト/パレットAPI

### APU (`md-apu`)

- YM2612/PSGの状態とレジスタ書き込み口を実装
- バス経由でのYM2612書き込みキュー（アドレスラッチ＋データ）対応
- PSG書き込みキュー対応（VDPアドレス空間経由）
- 簡易ミキサでステレオサンプルを生成（48kHz）
- オーディオサンプル取得API

## 公開インターフェース

- ネイティブ: Rust API (`md-core`)
- Web: `md-wasm`（`wasm-bindgen` 経由）
- 外部制御: `md-api`（REST/WS/JSON-RPC風）

## Web 公開形態（GitHub Pages）

- 公開対象: `frontend/index.html`（WASM直実行プレーヤー）
- 配信先: GitHub Pages（Project Pages: `/md_emulator/`）
- デプロイトリガー: `v*` タグ push（`deploy-pages.yml`）
- ビルド内容:
	- `wasm-pack build crates/md-wasm --target web --release --out-dir ../../frontend/pkg`
	- `wasm-opt -Oz` による WASM 最適化
	- `roms/` から `frontend/roms/` への ROM 同梱
	- `frontend/roms/index.json` の自動生成

## PWA対応範囲

- `frontend/manifest.webmanifest` を提供
- `frontend/sw.js` でアプリシェルとWASM関連ファイルをキャッシュ
- オンライン前提で初回ロード後の再訪問性能を向上
- 対応ブラウザでホーム画面追加/アプリインストールをサポート

`md-api` はAPIログのON/OFF制御（`/api/v1/logging`）と、描画確認用フレーム取得（`/api/v1/video/frame`）を提供します。
また、入力注入API（`/api/v1/input/controller`）により外部からコントローラ状態を設定できます。

## 注意点（現時点）

- VBlank割り込みによるゲーム進行は動作確認済み（SGDK製ROMでタイトル画面→ゲーム画面遷移を確認）
- M68KバスはRead/Write 8/16/32ビットアクセス全対応（VDPバイトアクセスの副作用を回避）
- YM2612/PSGの音声合成はプレースホルダー（ダミー正弦波/矩形波）
- 全命令網羅・全ハード精度は未完了です
- API仕様は今後拡張されるため、変更可能性があります
- `md-api` はサーバープロセスが必要（Pages 単体では稼働しない）
- `md-wasm` フロントエンドは HTTP(S) サーブ必須（`file://` 直接起動は非対応）
