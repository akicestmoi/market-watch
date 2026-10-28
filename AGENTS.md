# AGENTS.md

## Git

**Never run any git command** (`status`, `diff`, `add`, `commit`, `push`, `pull`, `checkout`, `rebase`, etc.) unless the user explicitly asks for that git action in the current message. Do not stage, commit, or push as a side effect of finishing other work.

## Coding conventions

App layout, `@open_api` / serializers / `error_responses`, module clustering, typing (**TypedDict** vs Pydantic **`BaseModel`** / **`TypeAdapter`** vs Django **`BaseModel`**; third-party / Redis JSON → `TypeAdapter(TypedDict).validate_python`, not bare `dict` / `Protocol` / hand coerce), and tests: [`.cursor/rules/coding-conventions.mdc`](.cursor/rules/coding-conventions.mdc).

## Timezone Management

Backend stores UTC-aware datetimes; user-facing clocks use Europe/Paris. See [docs/GUIDELINES.md](docs/GUIDELINES.md).

## Postman

Resolve the collection from `.cursor/postman.local.json` first (gitignored, per machine), then [docs/POSTMAN.md](docs/POSTMAN.md). MCP connection is `.cursor/mcp.json`; per-PC MCP overrides go in `~/.cursor/mcp.json`. Sync endpoints with `check-endpoint` / `upsert-endpoint` (`.cursor/rules/postman-sync.mdc`).
