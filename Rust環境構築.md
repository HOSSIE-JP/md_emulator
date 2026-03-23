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
scancode -clpieu --html output.html ./crates

jscpd
