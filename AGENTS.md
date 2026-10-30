# AGENTS.md

## Git

**Never run any git command** (`status`, `diff`, `add`, `commit`, `push`, `pull`, `checkout`, `rebase`, etc.) unless the user explicitly asks for that git action in the current message. Do not stage, commit, or push as a side effect of finishing other work.

## Django migrations

**Never create, edit, squash, or run migrations** (`makemigrations`, `migrate`, new files under `*/migrations/`, etc.) unless the user explicitly asks for that in the current message. Changing models / `TextChoices` / field options is fine; leave schema sync for when they request it. Do not invent label-only or intermediate rename migrations — when a migration *is* requested, ship the **final** choices/schema in one step (no churn of temporary codes or display-string-only AlterFields).

If a change **needs** a schema/migration (models, `TextChoices` that are persisted, etc.), **stop and ask** before adding or running migration files — do not invent “compatibility” layers to avoid the conversation.

## No legacy / multi-environment shims

This is a **personal project with a single environment**. Do **not** keep parallel query params, bookmark aliases, dual encodings, or “compat with old URLs/clients” paths. Prefer the current contract only; delete obsolete names when renaming.

## Coding conventions

App layout (incl. `<app>/services/scrapers/` one module per source; `<app>/services/cache.py` for Redis-backed caches when needed; shared Redis helpers in `core/cache.py`), `@open_api` / serializers / `error_responses`, module clustering, typing (**TypedDict** vs Pydantic **`BaseModel`** / **`TypeAdapter`** vs Django **`BaseModel`**; third-party / Redis JSON → `TypeAdapter(TypedDict).validate_python`, not bare `dict` / `Protocol` / hand coerce), and tests: [`.cursor/rules/coding-conventions.mdc`](.cursor/rules/coding-conventions.mdc).

## Timezone Management

Backend stores UTC-aware datetimes; user-facing clocks use Europe/Paris. See [docs/GUIDELINES.md](docs/GUIDELINES.md).

## Postman

Resolve the collection from `.cursor/postman.local.json` first (gitignored, per machine), then [docs/POSTMAN.md](docs/POSTMAN.md). MCP connection is `.cursor/mcp.json`; per-PC MCP overrides go in `~/.cursor/mcp.json`. Sync endpoints with `check-endpoint` / `upsert-endpoint` (`.cursor/rules/postman-sync.mdc`).
