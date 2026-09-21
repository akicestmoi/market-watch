---
name: check-endpoint
description: Checks that Postman collections match this Django/DRF API's endpoints (routes, folder path, params, request/response schemas, auth). Read-only — reports drift, never modifies Postman. Takes an optional endpoint name/path; without one, checks every endpoint in the project. Autonomous counterpart is upsert-endpoint, which applies the fixes this skill finds.
---

# Check Endpoint

Verify that the Postman collection for this repo matches the Django/DRF endpoints in code — method, path, folder placement, params, request/response shape, and auth. **Read-only**: never create, edit, or delete anything in Postman. Use `upsert-endpoint` to apply fixes.

`$ARGUMENTS`: an endpoint name, path, or view class (e.g. `prices`, `POST /markets/prices/ingest`, `IngestMarketPricesView`). When omitted, check **every** endpoint in the project.

**Target:** read `.cursor/postman.local.json` first (gitignored, per machine), then [POSTMAN.md](../../../POSTMAN.md). Default workspace name `Perso`, collection name `market-watch`. Prefer `id`/`uid` when present. Extra keys in the local file are machine-specific — honor them. The **whole collection** is this repo (no extra parent folder).

MCP connection is `.cursor/mcp.json` (full profile `https://mcp.postman.com/mcp`). Per-PC MCP overrides belong in `~/.cursor/mcp.json`, not git.

## Workflow

### 1. Resolve scope

- `$ARGUMENTS` given → narrow discovery (step 2) to endpoints whose path, view name, or route matches it (case-insensitive substring). If nothing matches, say so and stop — don't silently fall back to a full scan.
- `$ARGUMENTS` omitted → full project scan.

### 2. Discover endpoints

This repo is **Django + DRF**. Grep `path(...)` / `re_path(...)` in `urls.py`, class-based `APIView` / `GenericAPIView` subclasses, `@api_view([...])`, and any `router.register(...)` (list/retrieve/create/update/partial_update/destroy). Resolve `include(...)` prefixes from `core/urls.py` onto each app route.

For every match, extract:

- HTTP method(s) and the **fully resolved** path (prefix + route)
- Path params (`<int:id>`, `<uuid:id>`, `<slug:name>`)
- Query params (`request.query_params`, `request.GET`, DRF filter/query serializers)
- Request body shape from DRF serializers / parsed JSON keys
- Response shape from `open_api/` serializers or explicit serializer classes
- Auth: DRF `permission_classes`, `authentication_classes`, `@permission_classes`
- `file:line` of the view, for the report

Build one row per **(method, resolved path)**. If nothing is found, report that plainly and stop.

### 3. Locate the matching Postman collection

Use the Postman MCP (read-only tools are enough):

1. Resolve workspace + collection from `.cursor/postman.local.json` → else workspace `Perso` / collection `market-watch`. Use IDs when set.
2. If several collections plausibly match, **list them and ask** which is authoritative — do not guess.
3. Fetch the full collection (folders + requests): method, URL (path/query params), headers, body, and folder ancestry of every request. Treat every folder in that collection as this repo.

### 4. Normalize and diff

- Normalize path-param syntax on **both** sides to `{param}`: `<int:id>` → `{id}`, Postman's `:id` → `{id}` (so `{{base_url}}/x/:id` becomes `{{base_url}}/x/{id}`).
- Match each code endpoint to a Postman request by **(method, normalized path)**. If a path was clearly renamed (same view, different path), match by request name/folder instead — but flag it.
- Derive the **expected folder path** from the normalized URL (see Folder arrangement) and compare it to the request's actual folder ancestry.
- For each match, compare folder ancestry, path & query params, request body fields, auth headers, and HTTP method.
- Classify:

| Status          | Meaning                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------ |
| ✅ **In sync**  | Postman request matches the code exactly, including folder path                                  |
| ⚠️ **Outdated** | A Postman request exists but has drifted from the code (list the exact fields, including folder) |
| ❌ **Missing**  | Endpoint exists in code, no Postman request at all                                               |
| 👻 **Orphaned** | Postman request has no matching code endpoint (removed, renamed, or moved)                       |

A request whose method, params, and body match but that sits in the wrong folder is ⚠️ **Outdated**.
A request/folder whose **name** does not follow Naming convention is also ⚠️ **Outdated** (even if method/path/folder placement match).
Requests in a folder that are not ordered per Request ordering are also ⚠️ **Outdated**.
A body-capable request (POST / PUT / PATCH, or DELETE with a body) that has an empty/`{}` body when the code expects fields — or whose example payload is missing required keys — is ⚠️ **Outdated**.

### Folder arrangement

Every `/` in the path is a folder boundary. After stripping the collection's base-URL variable (e.g. `{{base_url}}`) and any query string, split on `/` and drop empty segments. **Skip every path-param segment** (`{id}`, `{pk}`, `:id`, `<int:id>`, leftover `{{id}}`). Never create a folder named `{id}` or `{{id}}`.

On the remaining **static** segments, derive the **folder path** as follows:

1. Across **all** discovered endpoints, collect every path that is a **strict prefix** of another endpoint's static path (a resource that has nested routes under it).
2. For the endpoint being placed, its folder path is:
   - the **full** static path, if that path is itself such a prefix (resource root with children), **or**
   - otherwise the **longest** prefix of its static path that appears in that prefix set.
3. Each folder segment is named per Naming convention. The request (named per Naming convention — not the raw path segment) sits **inside** that deepest folder.
4. Leaf action segments (`ingest`, `list-all`, `bulk-update`, …) that are **not** prefixes of any other endpoint are **not** folders — those requests stay in the parent resource folder.
5. One static segment only with no nested routes → request at collection root.
6. Several HTTP methods on the same path are sibling requests in that same folder (distinct Title Case names, e.g. `Get Market Prices` vs `Delete Market Prices`).

Examples:

- `GET /markets/asset` and `DELETE /markets/asset` → `Markets / Asset` (because `/markets/asset/...` children exist). **Never** leave them in `Markets` alone.
- `GET /markets/prices` → `Markets / Prices`; `POST /markets/prices/ingest` → also `Markets / Prices` (not a nested `Ingest` folder).
- `/markets/prices/{id}/ingest` → `{id}` skipped; request in `Markets / Prices`.
- `GET /central-banks/probability-matrix` → `Central Banks` when nothing nests under that path.

### Request ordering

Within each folder, requests must appear in this order:

1. **CRUD first** (at most the resource-root quartet) — requests whose path equals the folder's resource path (no extra action segment), ordered:
   - **C**reate → `POST`
   - **R**ead → `GET`
   - **U**pdate → `PUT` / `PATCH`
   - **D**elete → `DELETE`
   Skip any CRUD slot that has no request. Example in `Markets / Asset`: `Get Asset Details` then `Delete Asset`.
2. **Then alphabetical** — every remaining request in that folder, sorted by display name (case-insensitive).

Wrong order is ⚠️ **Outdated**.

### Example payloads

Every request that accepts a body (**POST**, **PUT**, **PATCH**, and **DELETE** when the view reads a body) **must** include a realistic example payload in Postman:

1. Derive fields from the DRF serializer, `request.data` / parsed JSON keys, or `open_api/` schema — not invented keys.
2. Use `raw` + `Content-Type: application/json` unless the endpoint is multipart/file upload (then `formdata` with the real field names).
3. Fill **required** fields with plausible example values (dates as `YYYY-MM-DD`, tickers, short arrays of 1–2 items). Optional fields may be included when they clarify usage.
4. GET requests: no body. Prefer example **query params** when the view reads query params.
5. An empty `{}` is only valid when the view truly accepts an empty body (no required fields). Otherwise missing/empty example payload is drift.

### Naming convention

**Folders** (from each static path segment):

1. Replace every `-` with a space.
2. Capitalize the first letter of every word (Title Case).
3. Examples: `markets` → `Markets`; `central-banks` → `Central Banks`; `stir-futures` → `Stir Futures`; `meeting-dates` → `Meeting Dates`.

**Requests** (display name in Postman — not the URL path):

1. Title Case: capitalize the first letter of every word; replace `-` with spaces when deriving from a slug.
2. Name must **describe what the endpoint does** in a few words (prefer verb + object), not the raw last path segment alone.
3. Prefer intent from the HTTP method + view purpose. Examples:
   - `GET /markets/prices` → `Get Market Prices`
   - `GET /markets/prices/list-all` → `List Market Prices`
   - `POST /markets/prices/ingest` → `Ingest Market Prices`
   - `DELETE /markets/asset` → `Delete Asset`
   - `PATCH /markets/prices/bulk-update` → `Bulk Update Market Prices`
4. A wrong casing or kebab-case name (`list-all`, `get-asset-names`) is drift — flag ⚠️ **Outdated**.

### 5. Report

Output one table, most severe first (❌ → ⚠️ → 👻 → ✅). Do **not** modify anything. If drift was found and the user wants it fixed, point them to `upsert-endpoint`.

## Notes

- Never call a Postman write tool from this skill.
- 👻 Orphaned entries are informational only — never suggested for deletion.
