---
name: upsert-endpoint
description: Checks Postman collections against this Django/DRF API's endpoints, then creates or updates the Postman requests needed to bring them back in sync via the Postman MCP — including nested folders matching each `/` in the path. Takes an optional endpoint name/path; without one, upserts every endpoint in the project. Autonomous — applies fixes without asking. Never deletes; the read-only counterpart is check-endpoint.
---

# Upsert Endpoint

Run the same drift check as `check-endpoint`, then **immediately fix** whatever is missing or outdated by creating/updating Postman requests through the Postman MCP. Fully autonomous — act, don't list and wait. This skill only ever **creates or updates**; it never deletes a Postman request.

`$ARGUMENTS`: an endpoint name, path, or view class (e.g. `prices`, `POST /markets/prices/ingest`, `IngestMarketPricesView`). When omitted, upsert **every** endpoint in the project.

**Target:** `.cursor/postman.local.json` first, then [docs/POSTMAN.md](../../../docs/POSTMAN.md). Workspace `Perso`, collection `market-watch`; IDs when present. The whole collection is this repo.

MCP is `.cursor/mcp.json` (`https://mcp.postman.com/mcp`). Per-PC MCP overrides: `~/.cursor/mcp.json`.

## CRITICAL BEHAVIOR RULES

1. **ACT, DON'T LIST.** Run the check, then apply the fixes for everything ❌ Missing or ⚠️ Outdated in the same pass. Do not stop to ask for confirmation on obvious upserts.
2. **NEVER DELETE FROM THE COLLECTION.** 👻 Orphaned Postman requests are never discarded. **Move** them into a collection-root folder named **`Deprecated`** (create the folder if missing). Do not leave orphans in their old live folders. Orphans already under `Deprecated` need no further move. Prefer MCP `transferCollectionRequests` (`mode: move`, target `Deprecated`). If transfer is unavailable, recreate under `Deprecated` (POST with `position.parent`), copy fields via JSON Patch, then remove only the old copy — the request must still exist under `Deprecated`.
3. **TARGETED PATCH, NOT BLIND OVERWRITE.** When updating an existing request, only change the fields that drifted (params, body, headers, method, URL, folder). Preserve description, saved example responses, and pre-request/test scripts. If the folder is wrong, **move** the request (an update, not a delete).
4. **MATCH THE COLLECTION'S CONVENTIONS.** New requests must look like they belong: Naming convention below, nested folders matching each `/` in the path, same base-URL variable (`{{base_url}}` or similar), same auth pattern as the rest of the collection.
5. **RENAME TO MATCH NAMING CONVENTION.** If a folder or request name is wrong (kebab-case, lowercase, or not descriptive), **rename** it. Do not leave drift on names.
6. **ALWAYS SET EXAMPLE PAYLOADS + PARAMS.** POST/PUT/PATCH (and body-bearing DELETE) must include a realistic example body from serializers/`request.data`. GET/DELETE with query params must include example `queryParams`. Path/URI params must remain in the URL. Never leave `{}` when fields are required.
7. **JSON BODY LANGUAGE, NOT TEXT.** For non-multipart JSON bodies set `dataMode: "raw"` and `dataOptions.raw.language: "json"`. Never leave language as `text` (Postman’s default Text mode).
8. **NO MANUAL CONTENT-TYPE ON BODY REQUESTS.** Do not put `Content-Type` in `headerData` when a body mode is set — Postman detects it. Strip redundant Content-Type headers when updating existing requests.
9. **ALWAYS SET DOCS.** Every create/update must set the request Docs tab (`description`) to the markdown structure in `check-endpoint`: opening summary; `## Path Parameters` / `## Query Parameters` tables; `## Request Body` + `## Example Payload`; `## Response` + `## Example Response` (omit sections that do not apply). Prefer `scripts/generate_postman_docs.py` from the OpenAPI schema. CLI: pass markdown via `--description "$(cat file.md)"` (inline text) — unlike `--body`, `--description` does **not** expand `@file` and will store the literal `@…` path if you pass one.

## Workflow

### 1–4. Check (identical to `check-endpoint`)

Resolve scope, discover Django/DRF endpoints, locate the collection, normalize paths, derive expected folders/names, and diff — see `check-endpoint` for the full detail (including Naming convention). Produce the same ✅/⚠️/❌/👻 breakdown before touching anything.

### 5. Confirm write access

Before making any change, confirm the Postman MCP exposes write tools (collection/request create & update, folder update). `.cursor/mcp.json` points at `/mcp` (full), which includes them.

- If write tools aren't available (server still on `/minimal` or `/code`): **stop**, report the missing capability, and tell the user to set the Postman MCP URL to `https://mcp.postman.com/mcp`, then restart Cursor and retry. Do not fake a write with a read tool.

### 6. Apply fixes

Process ❌ Missing first, then ⚠️ Outdated, then 👻 Orphaned (move into `Deprecated` only — never delete requests). Delete empty folders. Skip ✅ In sync and orphans already under `Deprecated`.

**❌ Missing → create a new request:**

- Method + fully resolved path from the code, with path params expressed the way the collection already expresses them (`:id` vs `{{id}}` vs `{id}` — match siblings).
- Query params with realistic example values.
- **Example request body** from the DRF serializer / parsed JSON keys (see Example payloads in `check-endpoint`). Never ship POST/PUT/PATCH with a blank/`{}` body when the code expects fields.
- Auth matching the view's `permission_classes` and how the collection sets auth (per-request vs inherited).
- Place it using Folder arrangement; set folder and request **names** per Naming convention.

**⚠️ Outdated → update the existing request/folder in place:**

- Patch only the drifted fields. **Move** the request if the folder is wrong. **Rename** the request and/or folders if the name violates Naming convention.
- Leave description, saved examples, and test scripts untouched unless they reference a field you just removed.

### Folder arrangement

Same rule as `check-endpoint` (keep in sync). Summary:

- Skip path-param segments. Build the set of static paths that are **strict prefixes** of other endpoints.
- Folder path = the request's **full** static path when that path has nested children; otherwise the longest such prefix. Resource roots like `GET/DELETE /markets/asset` belong in `Markets / Asset`, **not** in `Markets`.
- Leaf actions (`ingest`, `list-all`, …) are requests inside the parent resource folder — do **not** create a folder per action slug.
- Folder and request **display names** follow Naming convention (not raw path slugs).

**Create (❌ Missing):** walk folders from the collection root by **Title Case** folder names; reuse an existing folder of that name or create it; create the request **inside** the innermost folder with a descriptive Title Case name.

**Move (⚠️ wrong folder or 👻 orphan → `Deprecated`):** create any missing folders (including collection-root `Deprecated` for orphans), then move the existing request via MCP `transferCollectionRequests` / `transferCollectionFolders` when available. Do not leave a duplicate in the old folder. After a move, **delete any folders left empty**. Typical fix: resource-root GET/DELETE sitting in the parent must move into the resource folder (e.g. `Markets` → `Markets / Asset`). Collection-api note: `position` is set only on create — PATCH cannot re-parent; if transfer fails, recreate under the target parent, JSON-Patch the fields, then remove the old item.

**Rename (⚠️ wrong name):** update the folder/request `name` only (targeted patch).

**Reorder (⚠️ wrong order):** within each folder, put **CRUD** resource-root requests first (Create=`POST` → Read=`GET` → Update=`PUT`/`PATCH` → Delete=`DELETE`), then the rest **alphabetical** by display name. Use move/transfer to fix order; do not recreate requests.

**Example payload / params / headers (⚠️ missing/wrong):** See Example payloads, params, and headers in `check-endpoint`. When applying:

- JSON APIs (MCP): `dataMode: "raw"`, `dataOptions: { "raw": { "language": "json" } }`, `rawModeData` = JSON string from the serializer. **Never** use raw language `text`.
- JSON APIs (Postman CLI cloud): `-d 'json:{...}'` (the `json:` prefix sets body type to JSON, not Text).
- Multipart: `dataMode: "formdata"` / CLI `formdata:...` with real fields — not raw JSON.
- **Never** add `Content-Type` to `headerData` / `--headers` for body requests; Postman detects it from body mode. If an existing request has a redundant Content-Type header, **remove** it (replace `headerData` without that key; CLI: replace headers so Content-Type is gone).
- Always set `queryParams` / `--param` with example values when the view has query params; keep URI/path params in the URL matching the Django route.
- Always set Docs (`description`) per the Docs tab structure in `check-endpoint` (summary; Path/Query/Body/Response tables; Example Payload / Example Response JSON blocks).

### Naming convention

Same as `check-endpoint` — keep both skills in sync:

**Folders:** replace `-` with spaces; Title Case each word (`central-banks` → `Central Banks`).

**Requests:** Title Case; describe what the endpoint does in a few words (verb + object), e.g. `Get Market Prices`, `List Market Prices`, `Ingest Market Prices`, `Bulk Update Market Prices`. Never leave kebab-case or raw path-segment names.

### 7. Report

Summarize what changed — created, updated, orphaned (moved into `Deprecated`), already in sync. Do not just say "done".

## Notes

- If no endpoints are found, say so and stop — don't create speculative requests.
- If several Postman collections plausibly match, ask which is authoritative before writing.
- Framework-detection, folder-arrangement, and diff-classification detail lives in `check-endpoint`; keep the two skills in sync.
