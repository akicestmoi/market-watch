## Postman

This repo maps to **one Postman collection** in workspace **Perso**. Every folder in that collection belongs to this project. The collection name is **`market-watch`**.

Machine-specific IDs (and any extra per-PC fields) live in **`.cursor/postman.local.json`**, which is gitignored. Copy `.cursor/postman.local.json.example` on a new machine and fill in that PC's workspace/collection IDs.

### Lookup order (skills)

1. `.cursor/postman.local.json` if it exists — use `workspace` / `collection` (prefer `id` / `uid` when set). Honor any extra keys on that machine.
2. Else search Postman for workspace name `Perso` and collection name `market-watch`.
3. If several collections still match, list them and ask — do not guess.

Shared defaults when a field is omitted locally:

- Workspace name: `Perso`
- Collection name: `market-watch`
- Local API: http://127.0.0.1:8000/
- OpenAPI: http://127.0.0.1:8000/api/docs/

The whole collection is this repo (no extra parent folder). Nested folders still follow each `/` in the path — see `check-endpoint`.

### MCP vs collection identity

- **MCP** (how Cursor talks to Postman) is `.cursor/mcp.json`: full profile `https://mcp.postman.com/mcp`. OAuth is per machine automatically.
- **Target** (which workspace/collection to edit) is `.cursor/postman.local.json`.
- If this PC needs a *different* MCP server (EU URL, API key, extra servers), put it in **`~/.cursor/mcp.json`** so it stays off git. Do not commit secrets. A `mcp` key in `postman.local.json` is advisory only; Cursor does not read that file for MCP.

When HTTP endpoints change, use `check-endpoint` / `upsert-endpoint` (`.cursor/rules/postman-sync.mdc`).
