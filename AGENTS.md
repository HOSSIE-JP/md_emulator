# Codex 向け指示

このリポジトリには、GitHub Copilot 向けのガイダンスが `.github/`
配下にもあります。Codex は、このファイルで明示的に参照されている
場合に限り、その内容を利用できます。このファイルを Codex 向けの
入口として扱ってください。

## 最初に必ず読むもの

- エミュレータコア、API、WASM、フロントエンド連携、ドキュメントを
  変更する前に、`.github/copilot-instructions.md` を読んでください。
- 公開 API を変更する場合は、同じ作業内で `docs/` 配下の関連ファイルも
  更新してください。
- ライセンス安全性のルールに従い、外部リポジトリからコードをコピーしては
  いけません。外部情報は挙動を理解するためだけに使い、実装は独自に行って
  ください。

## タスク別の参照先

- MD Game Editor プラグイン関連の作業では、次を読んでください。
  - `.github/skills/md-game-editor-plugin/SKILL.md`
  - `.github/skills/md-game-editor-plugin/instructions.md`
  - `electron/PLUGIN.md`
- エミュレータのデバッグや診断作業では、次を読んでください。
  - `.github/skills/md-emulator-debug/SKILL.md`
- Mega Drive エミュレータのアーキテクチャやコア実装では、次を読んで
  ください。
  - `.github/skills/mega-drive-emulator-develop/SKILL.md`

## Codex スキルに関する補足

- `.github/skills/**/SKILL.md` は、このリポジトリ内の参照資料です。
  `~/.codex/skills` などの Codex スキルディレクトリへコピーまたは
  インストールされない限り、Codex スキルとして自動検出されるわけでは
  ありません。
- 将来インストールできるように、リポジトリ内の `SKILL.md` には
  Codex 互換の YAML フロントマター (`name` と `description`) を
  維持してください。

## 現在のプロジェクト運用

- 新しい抽象化を作るより、既存のプロジェクトパターンを優先してください。
- Electron の renderer、preload、main process の責務は分離してください。
- ファイルシステム IPC は現在のプロジェクト内に限定し、プロジェクトルート
  外へのパストラバーサルを拒否してください。
- 生成済みファイルやサンプルプロジェクトを編集する場合は、関係のない
  ユーザー変更を保持してください。

## 回帰テスト

- コードを変更した後は、関連する回帰テストを実行し、デグレードが発生して
  いないことを確認してください。
- 編集した範囲をカバーする最小限のテストコマンドを選び、共有挙動、公開 API、
  モジュール間契約に影響する変更ではテスト範囲を広げてください。
- テストを実行できない場合は、最終回答でその理由と残るリスクを説明して
  ください。

## コミットメッセージ方針

- Codex がこのリポジトリでコミットを作成する場合、コミットメッセージは
  日本語で書いてください。
- 件名は、実際の変更内容を表す簡潔な日本語にしてください。
- コミット本文が必要な場合も、日本語で書いてください。
- ユーザーが明示的に依頼した場合を除き、英語のコミット件名は使わないで
  ください。

## Windows / PowerShell での文字コード注意

- Windows 環境の PowerShell ターミナルは Shift_JIS / CP932 として表示・入出力されることがあり、UTF-8 の日本語を含む JSON / HTML / JS を既定設定のまま `Get-Content` / `Set-Content` すると文字化けや構文破壊を起こす可能性があります。
- 日本語を含むファイル、または既存ファイルの文字コードが不明なファイルを PowerShell で読む場合は、必ず UTF-8 を明示してください。

```powershell
Get-Content -LiteralPath path\to\file -Encoding UTF8
```