# Mega Drive Emulator Project - Copilot Instructions

## 🎯 Project Goal

Implement a highly accurate Sega Mega Drive / Genesis emulator with:

* High hardware fidelity (cycle-accurate where possible)
* Embeddable architecture (Web, Desktop, API)
* AI-agent controllable interfaces for debugging and automation

---

## 🧠 Core Design Principles

1. Accuracy over performance (optimize later)
2. Deterministic execution (important for AI debugging)
3. Modular architecture (CPU / VDP / APU separated)
4. External controllability via APIs
5. State introspection must be first-class

---

## 🧩 Required Components

### CPU

* Motorola 68000 (cycle-aware)
* Zilog Z80 (for sound)

### Graphics

* VDP (Video Display Processor)
* Support:

  * Scroll planes
  * Sprites
  * DMA
  * CRAM / VRAM / VSRAM

### Audio

* Yamaha YM2612 (FM synthesis)
* PSG (SN76489)

### Memory Map

* Cartridge ROM
* RAM
* I/O registers

---

## 🧪 Accuracy Requirements

* Instruction-level correctness required first
* Then move toward cycle accuracy
* Must pass known test ROMs

---

## 🔌 External Control API (MANDATORY)

Expose emulator control via:

### Commands

* load_rom(path or buffer)
* reset()
* step(cycles)
* run_frame()
* pause()

### State Access

* get_registers()
* get_memory(address, length)
* get_vram()
* get_cram()
* get_cpu_state()

### Debug

* set_breakpoint(address)
* step_instruction()
* trace_execution()

### Input Injection

* set_controller_state(player, buttons)

---

## 🤖 AI Agent Integration

Design API for AI:

* Deterministic stepping
* Save/Load state instantly
* Full memory inspection
* Execution trace logs

Preferred protocols:

* JSON-RPC
* WebSocket
* MCP (Model Context Protocol)

---

## 🌐 Web Integration

* Compile core to WebAssembly
* Provide JavaScript bindings
* Rendering via WebGL/WebGPU
* Audio via AudioWorklet

---

## 🧱 File Structure

/core
/cpu
/vdp
/apu
/memory
/api
/wasm
/frontend
/tools

---

## 🧪 Testing

* Use known ROM test suites
* Snapshot-based regression tests
* Deterministic replay required

---

## 🚫 Anti-Patterns

* Do NOT tightly couple rendering with emulation
* Do NOT hide internal state (must be inspectable)
* Do NOT optimize prematurely

---

## 📝 Documentation Rule (MANDATORY)

When adding or changing any public API (Rust core API / REST / WebSocket / JSON-RPC / WASM bindings), always update documentation under `docs/` in the same implementation pass.

Minimum required updates:

* `docs/api.md` for endpoint/method/schema changes
* `docs/usage.md` for new run/test examples
* `docs/spec.md` when behavior/feature scope changes

---

## ✅ Deliverables

1. Headless emulator core
2. WASM build
3. Debug API
4. Sample Web UI
5. AI control interface

---

## 🚫 License Safety Rules (MANDATORY)

- NEVER copy code from external repositories
- NEVER reproduce GPL or AGPL code
- Only implement from specifications, not source code
- If referencing external code, summarize behavior only
- All implementations must be original

## ✅ Allowed Sources

- Official hardware documentation
- Public domain code
- MIT / BSD licensed references (concept only)

## ⚠️ If Similarity is Suspected

- Rewrite logic using different structure
- Change control flow
- Rename variables meaningfully

---

## 🎨 VDP 描画リファレンス (MANDATORY)

VDP (S315-5313) の画面描画実装を改善・修正する際は、**Exodus Emulation Platform** の VDP 実装を正確性のリファレンスとして参照すること。

**リファレンスリポジトリ**: https://github.com/RogerSanders/Exodus (MIT License)
**主要ファイル**: `Devices/315-5313/S315-5313_Rendering.cpp`

### 参照すべき主要な実装ポイント

- **レイヤー優先度**: `CalculateLayerPriorityIndex()` のルックアップテーブル方式
- **Shadow/Highlight モード**: オペレータースプライト (palette 3, index 14/15) の正確な合成、shadow/highlight のキャンセル
- **VSRAM 境界処理**: アドレス >= 0x50 では最後の2エントリのAND値を返す
- **Hscroll データ**: 下位10ビットのみ有効
- **パレットセレクトビット**: Register 1 bit 2 がクリア時、各色の最下位ビットのみ有効
- **インターレースモード2**: 8×16パターン、倍精度Y座標、VSRAM 11ビットマスク
- **スプライト**: ドットオーバーフロー（H40=320dots, H32=256dots）、マスキング、衝突検出
- **ウィンドウ歪みバグ**: 左寄せウィンドウ後の部分表示2セル領域のマッピングデータ問題
- **CRAM ドット**: 書き込み中のライン上への色伝搬

### ルール

1. **コードのコピーは禁止** — Exodus のソースから直接コードをコピーしないこと
2. **仕様・動作の理解のみ** — Exodus の実装を読んで仕様や正しい動作を理解し、独自のコードで実装すること
3. **ハードウェアテスト結果を優先** — Exodus のコメントに記載されたハードウェアテスト結果は信頼性が高い
4. **差分がある場合** — 本プロジェクトの描画結果と Exodus の結果に乖離がある場合、Exodus 側の動作を正とする

---

## 🔄 WASM ビルド更新ルール (MANDATORY)

`md-core` / `md-apu` / `md-vdp` / `md-cpu-*` / `md-bus` / `md-wasm` クレートに変更を加えた場合、**必ず WASM パッケージも再ビルドすること**。

```bash
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg
```

- バージョン（ビルドタイムスタンプ）は `crates/md-core/build.rs` が自動生成する。
- WASM 再ビルドを忘れると、フロントエンド (wasm.html) に修正が反映されない。
- API サーバー (`md-api`) のビルドだけでは WASM は更新されない。両方を別々にビルドする必要がある。

---

## コミットメッセージ (MANDATORY)

- リポジトリ内で生成されるコミットメッセージ（GitHub Copilot 等の自動生成を含む）は日本語で記述すること。
- コミットメッセージを自動生成するツールを利用する場合、このリポジトリのスタイルに従い、日本語で意味の通る要約と詳細を出力するよう設定すること。
