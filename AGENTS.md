# AGENTS.md

## Git

**Never run any git command** (`status`, `diff`, `add`, `commit`, `push`, `pull`, `checkout`, `rebase`, etc.) unless the user explicitly asks for that git action in the current message. Do not stage, commit, or push as a side effect of finishing other work.

## Django migrations

**Never create, edit, squash, or run migrations** (`makemigrations`, `migrate`, new files under `*/migrations/`, etc.) unless the user explicitly asks for that in the current message. Changing models / `TextChoices` / field options is fine; leave schema sync for when they request it. Do not invent label-only or intermediate rename migrations — when a migration *is* requested, ship the **final** choices/schema in one step (no churn of temporary codes or display-string-only AlterFields).

If a change **needs** a schema/migration (models, `TextChoices` that are persisted, etc.), **stop and ask** before adding or running migration files — do not invent “compatibility” layers to avoid the conversation.

## No legacy / multi-environment shims

This is a **personal project with a single environment**. Do **not** keep parallel query params, bookmark aliases, dual encodings, or “compat with old URLs/clients” paths. Prefer the current contract only; delete obsolete names when renaming.

## Coding conventions

App layout (incl. `<app>/services/scrapers/` one module per source; `<app>/services/cache.py` for Redis-backed caches when needed; shared Redis helpers in `core/services/cache.py`), `@open_api` / serializers / `error_responses`, module clustering, typing (**TypedDict** vs Pydantic **`BaseModel`** / **`TypeAdapter`** vs Django **`BaseModel`**; third-party / Redis JSON → `TypeAdapter(TypedDict).validate_python`, not bare `dict` / `Protocol` / hand coerce), and tests: [`.cursor/rules/coding-conventions.mdc`](.cursor/rules/coding-conventions.mdc).

**Domain vs UI:** ingestion / scraping / backend domain logic **and** JSON API endpoint surface (`@open_api` views, serializers, app urls, management `ENDPOINTS`) stay in the **owning domain app**. Domain GETs return DB / domain data — not UI page payloads. UI-oriented page preparation (HTML context, display payloads, display caches, templates/static) lives in **`data_visualization`**.

**Missing required values raise** — do not silently fall back to `""` / `0` / empty stand-ins when a unit, ticker, or other required field is absent for the path you are on (see coding-conventions).

## Dates and timezones

Backend stores UTC-aware datetimes; user-facing clocks and Beat schedules use Europe/Paris. App-level overview: [README.md](README.md) (Dates and timezones). Coding rules / helpers: [`.cursor/rules/coding-conventions.mdc`](.cursor/rules/coding-conventions.mdc).

## Postman

Resolve the collection from `.cursor/postman.local.json` first (gitignored, per machine), then postman-sync defaults (workspace `Perso`, collection `market-watch`). Overview: [README.md](README.md) (Postman). Rules: [`.cursor/rules/postman-sync.mdc`](.cursor/rules/postman-sync.mdc). MCP is `.cursor/mcp.json`; per-PC overrides go in `~/.cursor/mcp.json`. **Do not sync Postman unless the user explicitly asks** — then use `check-endpoint` / `upsert-endpoint`.

## Management tab

Every new or changed JSON API endpoint must also be added or updated in the management console (`data_visualization/static/data_visualization/js/management.js` `ENDPOINTS`), in the same change as the route / OpenAPI work.
