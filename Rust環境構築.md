Rust本体のインストール

公式の rustup を使います。

Windows / Mac / Linux 共通

```
curl https://sh.rustup.rs -sSf | sh
```

インストール後：
```
rustc --version
cargo --version
```

プロジェクト作成
```
cargo new md_emulator
cd md_emulator
cargo run
```
これでHello Worldが動けばOK。

拡張機能
- rust-analyzer（必須）
- CodeLLDB（デバッグ）

フォーマット & Lint
```
rustup component add rustfmt clippy
cargo fmt
cargo clippy
```

ビルド高速化（重要）
```
cargo install sccache
```

環境変数：
```
RUSTC_WRAPPER=sccache
```


OSSチェック

ScanCode Toolkit

macOS で新規導入する場合:
```
brew install icu4c@78 libmagic
python3 -m pip install --user scancode-toolkit
```

ラッパースクリプト:
- `tools/run_scancode.sh` はユーザー Python 配下の `scancode` と Homebrew の `libmagic` を自動検出する。
- `scancode` の場所が特殊な場合は `SCANCODE_BIN=/path/to/scancode` を指定する。

```
bash ./tools/run_scancode.sh -clpieu --ignore '*/Cargo.toml' --html output.html ./crates
```

注記:
- 現在のローカル ScanCode では Cargo workspace の `workspace = true` 依存を package 解析できず失敗するため、VS Code タスクでは `Cargo.toml` を除外してレポート生成する。
- 元の `scancode -clpieu --html output.html ./crates` をそのまま使いたい場合は、workspace 依存を解釈できる ScanCode 版へ更新が必要。

VS Code タスク
- OSS: ScanCode HTML Report

jscpd
```
npm install
npm run check:duplication
```

コア実装のみ確認したい場合:
```
npm run check:duplication:core
```

注記:
- 既存の 14 件の clone は主に `tools/` 配下の診断スクリプト由来。
- 外部 OSS 混入の確認は `check:duplication:core` を優先するとノイズが少ない。

厳格チェック
```
npm run check:duplication:strict
```

VS Code タスク
- OSS: jscpd Report
- OSS: Core Duplicate Check
- OSS: jscpd Strict

Node依存ライセンス/GPLチェック
```
npm run check:licenses:node
npm run check:licenses:node:gpl
```

Rust依存ライセンス/GPLチェック
```
cargo install cargo-deny --locked
cargo deny check licenses
cargo deny check bans sources licenses
```

VS Code タスク
- OSS: Node License Summary
- OSS: Node GPL Policy
- OSS: Rust License Policy
- OSS: Rust Dependency Policy
- OSS: Run All Policies

jscpd
