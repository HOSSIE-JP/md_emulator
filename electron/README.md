# md-game-editor-electron

Electron ベースの **Mega Drive ゲームエディタ & エミュレータ** シェルです。  
`frontend/pkg/` にビルドされた WASM コアと、`md-api` REST サーバーを内包し、デスクトップアプリとして動作します。

---

## 目次

1. [ディレクトリ構成](#ディレクトリ構成)
2. [前提条件](#前提条件)
3. [初期セットアップ](#初期セットアップ)
4. [開発モードで起動](#開発モードで起動)
5. [パッケージング (配布ビルド)](#パッケージング-配布ビルド)
6. [ポータブルモード](#ポータブルモード)
7. [アプリ名・アイコンの変更](#アプリ名アイコンの変更)
8. [利用プロジェクトでの拡張方法](#利用プロジェクトでの拡張方法)
9. [アンインストール](#アンインストール)

---

## ディレクトリ構成

```
electron/
├── main.js                  # メインプロセス (ウィンドウ管理 / IPC ハブ)
├── preload.js               # メインウィンドウ向け contextBridge
├── debug-preload.js         # デバッグウィンドウ向け contextBridge
├── testplay-preload.js      # テストプレイウィンドウ向け contextBridge
├── testplay-settings-preload.js  # テストプレイ設定ウィンドウ向け contextBridge
├── setup-manager.js         # ツール (SGDK / JRE / marsdev) の管理
├── build-system.js          # SGDK ビルドオーケストレーション
├── electron-builder.yml     # パッケージング設定
├── package.json
├── renderer/                # レンダラープロセス (HTML / CSS / JS)
│   ├── index.html           # メイン画面 (プロジェクト設定 / ビルド)
│   ├── testplay.html        # テストプレイ画面
│   ├── testplay-settings.html  # 入力設定画面
│   ├── debug-wasm.html      # WASM デバッグビューア
│   └── style.css
├── scripts/
│   ├── copy-pkg.js          # frontend/pkg → electron/pkg コピー
│   └── prepare-dist.js      # パッケージ前ビルド (WASM + md-api バイナリ)
├── sample/                  # サンプルゲームソース (main.c 等)
├── pkg/                     # 実行時 WASM アセット (自動生成)
└── bin/                     # 同梱バイナリ (自動生成): md-api.exe 等
```

---

## 前提条件

| ツール | バージョン | 用途 |
|---|---|---|
| Node.js | 20 LTS 以上 | Electron / npm |
| Rust + cargo | 1.75 以上 | md-api バイナリのビルド |
| wasm-pack | 最新 | WASM コアのビルド |
| SGDK | 2.0 以上 | ゲーム ROM ビルド (任意) |

### インストール確認

```powershell
node -v
cargo -v
wasm-pack -V
```

---

## 初期セットアップ

```powershell
# リポジトリルートで
cd d:\path\to\md_emulator

# 1. WASM コアのビルド
wasm-pack build crates/md-wasm --target web --out-dir ../../frontend/pkg

# 2. Electron 依存関係のインストール
cd electron
npm install

# 3. WASM アセットを electron/pkg にコピー
npm run copy-pkg
```

> **注意**: `electron/pkg/` は `.gitignore` 対象です。`copy-pkg` または `prepare:dist` で都度生成してください。

---

## 開発モードで起動

```powershell
cd electron
npm start          # copy-pkg → electron . を実行
# または
npm run dev        # start と同等
```

VSCode タスクからも起動できます:

- `Emulator: Launch All` — md-api サーバー起動 + ブラウザフロントエンド同時起動

---

## Rescomp アセット管理（メイン画面 Assets）

メイン画面の Assets ページは、SGDK プロジェクトの `res/*.res` を読み取り、定義をファイル単位で管理できます。

### できること

- `.res` ファイルの選択と新規作成
- 定義一覧の検索フィルタ（名前 / 種別 / 入力パス）
- 対応タイプの定義編集
  - `PALETTE`, `IMAGE`, `BITMAP`, `SPRITE`, `XGM`, `XGM2`, `WAV`, `MAP`, `TILEMAP`, `TILESET`
- アセット登録（ファイルダイアログ）
  - 選択したファイルを `res/` 配下へコピー（サブディレクトリ指定可）
  - その相対パスで `.res` に定義を追加

### 画像減色（16色化）

画像系アセット登録時、16色を超える場合は減色ダイアログを開けます。

- 透明色（パレット 0）の扱い
  - 指定なし
  - 元画像の透明情報を利用
  - 指定色を透明色として利用
- ディザリング
  - ON/OFF
  - ウェイト調整
  - パターン選択（`diagonal4`, `diagonal2`, `horizontal4`, `horizontal2`, `vertical4`, `vertical2`）
- 変換前/変換後をリアルタイムプレビュー

Assets ページ上部の `res ディレクトリを開く` ボタンで、現在のプロジェクトの `res/` をエクスプローラーで直接開けます。

---

## パッケージング (配布ビルド)

### Windows (既定: ポータブル ZIP)

```powershell
cd electron
npm run build:win
# → electron/dist/MegaDriveGameEditor-0.1.0-x64.zip
```

この ZIP は既に portable モード用に構成されており、展開後すぐに実行できます。
実行ファイルと同階層に `portable` マーカーを自動同梱するため、設定・ツール・プロジェクトは ZIP 展開先の `data/` に保存されます。

### Windows (任意: NSIS インストーラー)

```powershell
cd electron
npm run build:win:installer
# → electron/dist/MegaDriveGameEditor-0.1.0-x64.exe
```

### macOS (DMG)

```bash
cd electron
npm run build:mac
# → electron/dist/MegaDriveEmulator-0.1.0.dmg
```

内部で実行されること (`prepare:dist`):

1. `wasm-pack build` で WASM コアを再ビルド
2. `cargo build --release -p md-api` で API バイナリを生成
3. バイナリを `electron/bin/` にコピー

VSCode タスクからも実行できます:

- `Electron: Prepare Dist Assets` — アセットのみ準備
- `Electron: Package (Windows)` — Windows 向けパッケージング
- `Electron: Package (macOS)` — macOS 向けパッケージング

---

## ポータブルモード

通常、アプリのデータ（設定・ツール・プロジェクトファイル）は OS のユーザープロファイル下に保存されます。

| OS | デフォルトパス |
|---|---|
| Windows | `%APPDATA%\MegaDriveEmulator` |
| macOS | `~/Library/Application Support/MegaDriveEmulator` |
| Linux | `~/.config/MegaDriveEmulator` |

**ポータブルモード**を有効にすると、すべてのデータをアプリ実行ファイルと同じフォルダ内の `data/` ディレクトリに格納します。USB ドライブなどへの持ち運びや、環境を汚さずに複数バージョンを共存させる用途に適しています。

### 有効化方法

#### パッケージ済みアプリ (配布版)

Windows の既定ビルド (`npm run build:win`) では、この `portable` ファイルは自動で含まれます。
手動で作成するのは、インストーラー版などを portable 化したい場合だけです。

`.exe` または `.app` と同じディレクトリに `portable` という名前の**空ファイル**を置きます:

```
MegaDriveEmulator.exe
portable            ← このファイルを作成
resources/
data/               ← ポータブルモード時にここにデータが保存される
```

```powershell
# Windows PowerShell 例 (exe と同じフォルダで実行)
New-Item -ItemType File -Name portable
```

#### 開発モード

`electron/` フォルダ内に `.portable` ファイルを置きます:

```powershell
# electron/ ディレクトリで
New-Item -ItemType File -Name ".portable"
npm start
```

### ポータブルモードの解除

対応するマーカーファイル (`portable` / `.portable`) を削除すれば、次回起動からデフォルトの OS ユーザープロファイルに戻ります。

> **注意**: ポータブルモードのデータとデフォルトモードのデータは共有されません。引き継ぐ場合は `data/` フォルダを手動でコピーしてください。

---

## アプリ名・アイコンの変更

### アプリ名の変更

`electron/electron-builder.yml` の `productName` を変更します:

```yaml
# electron-builder.yml
appId: com.yourcompany.yourgame    # ← アプリの一意 ID も変更推奨
productName: YourGameEditor        # ← ここを変更
```

`electron/package.json` の `name` も合わせて変更しておくとよいです:

```json
{
  "name": "your-game-editor",
  "version": "1.0.0",
  "description": "Your Game Editor for Mega Drive"
}
```

### アイコンの変更

1. アイコンファイルを用意します:
   - Windows: `electron/build/icon.ico` (256×256 推奨)
   - macOS: `electron/build/icon.icns`
   - Linux: `electron/build/icon.png` (512×512 推奨)

2. `electron-builder.yml` で参照します:

```yaml
win:
  icon: build/icon.ico
  target:
    - nsis
    - zip
mac:
  icon: build/icon.icns
  target:
    - dmg
linux:
  icon: build/icon.png
```

> `electron-builder` はデフォルトで `build/` フォルダを探すため、ファイルを置くだけで自動認識される場合もあります。

---

## 利用プロジェクトでの拡張方法

このリポジトリはサンプル実装です。独自ゲームプロジェクト用に以下を拡張してください。

### 1. IPC の追加 (バックエンド処理)

`electron/main.js` に IPC ハンドラを追加します:

```js
// main.js
ipcMain.handle('myFeature:doSomething', async (_event, arg) => {
  // Node.js / OS API を自由に呼べる
  return { result: 'ok' };
});
```

対応する `preload.js` に公開 API を追加します:

```js
// preload.js
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('myFeatureAPI', {
  doSomething: (arg) => ipcRenderer.invoke('myFeature:doSomething', arg),
});
```

レンダラー側では `window.myFeatureAPI.doSomething(...)` として呼び出します。

### 2. ビルドシステムのカスタマイズ

`electron/build-system.js` を編集します:

- `getProjectDir()` — プロジェクトの保存先を変更
- `buildRom()` — 独自のビルドコマンドを差し替え
- スキーマ: `title` / `serial` / `author` フィールドを追加・変更可能

### 3. 設定のカスタマイズ

`electron/setup-manager.js` を編集します:

- `getDefaultTestPlaySettings()` — デフォルトのキーマップや設定値を変更
- `getToolsDir()` は `app.getPath('userData')` ベースで構築されているため、ポータブルモード対応も自動で有効になります

### 4. サンプル ROM の差し替え

`electron/sample/src/main.c` を編集するか、`electron/sample/` の内容を差し替えます。  
ビルドコマンドは `build-system.js` の `buildRom()` が制御しています。

### 5. 画面レイアウトの変更

`electron/renderer/` 以下の HTML / CSS を編集します:

- `index.html` + `renderer.js` — メイン設定画面
- `testplay.html` — テストプレイ画面
- `debug-wasm.html` — WASM デバッグビューア

---

## アンインストール

### Windows (インストーラー版)

**方法 A**: `コントロールパネル → プログラムと機能` から `MegaDriveEmulator` を選択してアンインストール。

**方法 B**: インストーラー (`MegaDriveEmulator Setup x.x.x.exe`) を再実行すると「アンインストール」オプションが表示されます。

アンインストール後もユーザーデータが残る場合は手動で削除します:

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\MegaDriveEmulator"
```

### Windows (ポータブル ZIP 版)

アプリフォルダをそのまま削除するだけです。レジストリや OS への書き込みは一切ありません。

```powershell
Remove-Item -Recurse -Force "C:\path\to\MegaDriveEmulator"
```

### macOS

`/Applications/MegaDriveEmulator.app` をゴミ箱に捨てます。  
ユーザーデータを削除する場合:

```bash
rm -rf ~/Library/Application\ Support/MegaDriveEmulator
rm -rf ~/Library/Logs/MegaDriveEmulator
```

### macOS (ポータブルモード)

`.app` バンドルと同階層の `data/` フォルダごと削除します。

### データ保存場所まとめ

| 環境 | データ保存先 |
|---|---|
| Windows (通常) | `%APPDATA%\MegaDriveEmulator` |
| Windows (ポータブル) | `<アプリフォルダ>\data\` |
| macOS (通常) | `~/Library/Application Support/MegaDriveEmulator` |
| macOS (ポータブル) | `<.appバンドルの親フォルダ>\data\` |
| 開発モード (通常) | OS デフォルトの userData パス |
| 開発モード (ポータブル) | `electron/data\` |

---

## テスト

Electron 配下の JavaScript テストは Node.js 標準の `node:test` で実行します。Electron 本体は起動せず、`electron` モジュールをテスト用モックに差し替えるため、main process 用モジュールや preload の IPC ブリッジを軽量に検証できます。

### コマンドラインで実行

リポジトリルートから実行します。

```powershell
npm --prefix electron test
```

または `electron/` に移動してから実行します。

```powershell
cd electron
npm test
```

### VSCode タスクで実行

VSCode の `Terminal: Run Task` から次のタスクを選択します。

- `Electron: Run Tests`

### テスト対象

- `tests/build-system.test.js`: プロジェクト作成、既存プロジェクトを開く処理、プラグイン選択保存、ツールチェーン未設定時の失敗経路
- `tests/setup-manager.test.js`: テストプレイ設定の正規化、SGDK / Marsdev パス検出
- `tests/preload.test.js`: renderer に公開する preload API と IPC チャンネル
- `tests/plugin-manager.test.js`: プラグイン manifest 正規化、有効化と依存関係処理
- `tests/rescomp-manager.test.js`: `.res` 解析、生成、更新、削除、パストラバーサル拒否

新しい Electron 側機能を追加した場合は、対象モジュールに近い `electron/tests/*.test.js` にケースを追加してください。Electron の実ウィンドウを必要としないロジックは、既存の `tests/helpers/mock-electron.js` を使って `app` / `ipcRenderer` / `contextBridge` をモックします。
