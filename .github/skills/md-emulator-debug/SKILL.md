---
name: md-emulator-debug
description: 'Mega Drive エミュレータのバグ診断・修正ワークフロー。音声無音・音程ずれ・CPU ハング・VDP 描画不具合などの症状を診断する。USE FOR: Z80バス問題, YM2612/PSG 音声不具合, M68K クラッシュ, VDP スプライト/プレーン不具合, WASM ビルド後の動作確認。診断ツール群 (tools/diag_*.py) を活用した段階的デバッグを実施する。'
argument-hint: '診断したい症状 (例: "ぷよぷよBGMが鳴らない", "Z80クラッシュ", "VDP描画バグ")'
---

# Mega Drive エミュレータ デバッグワークフロー

## 症状ごとの診断ルート

| 症状 | 疑い箇所 | 最初に使う診断ツール |
|------|----------|----------------------|
| BGM・SEが無音 / 歪む | Z80ドライバ, YM2612, APU | `diag_apu_state.py`, `diag_apu_channels.py` |
| Z80がクラッシュ / ハング | M68K→Z80バスマッピング, Z80バンクウィンドウ | `diag_m68k_trace.py`, `check_cpu.py` |
| 音が出るが音程が外れる | YM2612 周波数計算, フィードバック, TL | `diag_deep_audio.py`, `diag_audio_quality.py` |
| VDP描画乱れ（プレーン・スプライト） | VDP レジスタ, VRAM/VSRAM | `diag_vdp_state.py`, `diag_sprite_check.py` |
| ゲームが起動途中で止まる | M68K 例外ベクタ, I/O ポート | `diag_vectors.py`, `diag_vblank.py` |
| DMA転送失敗 | VDP DMA, バス調停 | `check_dma.py`, `diag_dma_trace.py` |

---

## 標準デバッグ手順

### 1. 環境確認・サーバー起動

```bash
# API サーバー起動
cargo run -p md-api

# ROM ロード
python3 tools/diag_check_state.py
```

- `crates/md-api/src/lib.rs` のルーター起動確認
- `export MD_API_PORT=8118` 必要であれば設定

### 2. 症状の再現・ログ取得

診断ツールを実行して現象を数値化する：

```bash
# 音声振幅チェック（無音かどうか即確認）
python3 tools/diag_audio_quality.py

# APU チャンネル状態（YM2612 の 6ch fnum/blk 確認）
python3 tools/diag_apu_channels.py

# Z80 実行トレース
python3 tools/diag_m68k_trace.py
```

期待値の目安：
- `max_amp >= 0.05` → 音声出力あり
- `ym_writes > 10000` (600フレーム時点) → YM2612 書き込み正常
- Z80 PC が `$114A` や `$116F` (アイドルループ) → Z80 正常動作

### 3. 根本原因の特定

#### Z80 バスマッピング問題の典型パターン

**症状**: Z80 が `$BB11` 等の異常アドレスで実行停止 → バンクウィンドウの `<< 1` ずれ
**症状**: Z80 ドライバの奇数バイトが欠落 → M68K→Z80 バイトアクセスの `>>1` フィルタ

確認すべき実装（`crates/md-core/src/lib.rs`）：

```
// Z80 バンクウィンドウ（正しい実装）
m68k_addr = bank_base | (z80_addr & 0x7FFF)  // << 1 は不要

// M68K → Z80 バイトアクセス（正しい実装）
let z80_addr = Z80_SPACE_START | ((addr - Z80_SPACE_START) & 0x1FFF)  // 1:1 マッピング
```

#### YM2612 周波数問題の典型パターン

**症状**: 音は出るが音程が大幅にずれる → 周波数係数の誤り
正しい係数: `F = fnum * 2^block * 7670454 / (144 * 2^21)` ≈ 0.025400

#### APU TL 減衰問題

**症状**: 音が極端に小さい / 大きい → TL は線形ではなく dB ベース
正しい実装: `0.75 dB/step`（線形乗算は不正確）

### 4. 修正を適用

修正対象クレートと主要ファイル：

| 問題 | ファイル |
|------|---------|
| Z80/M68K バスマッピング | `crates/md-core/src/lib.rs` |
| YM2612 FM 合成 | `crates/md-apu/src/lib.rs` |
| VDP レンダリング | `crates/md-vdp/src/lib.rs` |
| Z80 CPU 命令 | `crates/md-cpu-z80/src/lib.rs` |
| M68K CPU 命令 | `crates/md-cpu-m68k/src/lib.rs` |

### 5. テスト実行

```bash
# 修正したクレートのテストのみ実行
cargo test -p md-core
cargo test -p md-apu
cargo test -p md-vdp

# 全テスト
cargo test
```

### 6. 修正後の検証

```bash
# 音声品質の再計測
python3 tools/diag_audio_quality.py

# フレーム400〜600 の APU チャンネル確認
python3 tools/diag_apu_channels.py
```

合格基準：
- `max_amp >= 0.10` （BGMあり）
- 全6ch の `fnum != 0`
- Z80 PC がアイドルループ内

### 7. WASM ビルド（コア変更時は必須）

`md-core` / `md-apu` / `md-vdp` / `md-cpu-*` / `md-bus` / `md-wasm` に変更があった場合：

```bash
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg
```

- バージョンは `crates/md-core/build.rs` が自動生成
- `frontend/wasm.html` で動作確認

---

## 重要な実装上の注意点

### I/O ポートのデフォルト値

PAD コントロールポートは Reset/Power-on 時に `0x00` を設定すること。  
`0x40` にすると Darius 等が短い初期化パスに入り RAM コールバックがセットアップされない。

### APU ホットパス

`next_fm_sample()` 内で sin/pow テーブルを `clone()` しないこと。  
Darius 等の音声重いROMでフレームタイム劣化の原因になる。

### Z80 バスリクエストポーリング

A11100 のバスリクエストポーリングはタイミング敏感。  
スキャンライン単位の 68K/Z80 スケジューリングで Z80 が餓死し  
PS2 等のゲームが YM ハンドシェイク中にデッドロックすることがある。

### デバッグ時の `eprintln!` 削除

フレームごと・書き込みごとのホットパスに `eprintln!` を残さないこと。  
実行時に顕著なパフォーマンス劣化を引き起こす。

---

## 参照リソース

- VDP 正確性リファレンス: [Exodus Emulation Platform](https://github.com/RogerSanders/Exodus) (MIT) — コードは参照のみ、実装は独自に行うこと
- ハードウェア仕様: `docs/spec.md`
- API リファレンス: `docs/api.md`
- リポジトリメモリ: `/memories/repo/md-emulator-status.md`
