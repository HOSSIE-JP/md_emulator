# MD Game Editor AI Control API

AI Control は、Codex / Claude / Copilot などの外部 AI ツールが MD Game Editor を操作するための localhost 専用 API です。

## 起動

Editor の `AI Control` タブで `Start` を押すと、`127.0.0.1` のみで REST / MCP bridge が起動します。外部公開は行いません。

- 既定 port: `17777`
- 認証: `Authorization: Bearer <token>` または `X-MD-Editor-Token: <token>`
- token は起動ごとに生成され、`AI Control` タブに表示されます。
- `Origin` header がある場合、`localhost` / `127.0.0.1` / `[::1]` 以外は拒否します。

## REST

### `GET /v1/status`

サーバー状態、base URL、公開 tool 数、直近ログを返します。

### `GET /v1/tools`

AI が呼び出せる tool 一覧を返します。

### `GET /v1/resources`

AI が読める resource 一覧を返します。

### `POST /v1/resources/read`

```json
{ "uri": "md-editor://project/config" }
```

### `POST /v1/tools/call`

```json
{
  "name": "asset_list",
  "arguments": {},
  "dryRun": false,
  "confirm": false
}
```

書き込み、削除、ビルド、エクスポートなど project state を変える tool は、`dryRun: true` または `confirm: true` が必要です。

## MCP

Editor 起動中の REST bridge に接続する stdio sidecar を用意しています。

```powershell
$env:MD_EDITOR_CONTROL_URL = "http://127.0.0.1:17777"
$env:MD_EDITOR_CONTROL_TOKEN = "<AI Control tab token>"
npm run mcp
```

MCP sidecar は stdout に JSON-RPC メッセージだけを書き、ログは stderr に出します。

## Tools

- `editor_status`
- `project_list`
- `project_open`
- `project_create`
- `project_config_get`
- `project_config_update`
- `asset_list`
- `asset_add`
- `asset_update`
- `asset_delete`
- `code_tree`
- `code_read`
- `code_write`
- `plugin_list`
- `plugin_set_role`
- `plugin_run_generator`
- `build_run`
- `testplay_open`
- `export_rom`
- `export_html`

## Resources

- `md-editor://project/current`
- `md-editor://project/config`
- `md-editor://project/resources`
- `md-editor://project/source/<path>`

## Prompts

- `create_game_from_assets`
- `fix_build_error`
- `add_asset_and_rebuild`
