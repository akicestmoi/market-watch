# Timezone Management

**Backend: UTC, timezone-aware. Display: Europe/Paris.**

## Rules

| Layer | Convention |
|---|---|
| **Storage** (`DateTimeField`, scraped embargoes, meeting instants) | UTC-aware datetimes (`USE_TZ = True`) |
| **Comparisons / “now”** | Aware UTC (`django.utils.timezone.now()` or `datetime.now(timezone.utc)`) |
| **Source wall clocks** (Fed/US releases in New York time, ECB CET/CEST, BoJ JST, …) | Interpret in the source zone via `convert_local_wall_time_to_utc` / `parse_datetime(..., naive_timezone=…)` / `get_source_timezone(location_code)`, then store UTC |
| **Parsing** | Prefer aware input; **naive strings default to UTC** unless `naive_timezone` (or a location map) is passed |
| **User-facing clocks** (UI labels, upcoming-event times, date chips) | Convert with `core.services.convert_to_display_timezone` → **Europe/Paris** (`TIME_ZONE`) |
| **Calendar “today”** (filters, week focus for the ops UI) | `core.services.get_local_today()` / `timezone.localdate()` (Paris date, not container `date.today()`) |
| **Celery Beat** | Wall-clock schedules in **Europe/Paris** (`CELERY_TIMEZONE = TIME_ZONE`) |

Do **not** strip `tzinfo` before saving. Naive values with `USE_TZ` are reinterpreted as Paris local time and shift the instant.

Do **not** hardcode a fixed UTC hour for a local announcement (e.g. “FOMC = 13:00 UTC”). Use the source zone so DST is handled correctly.

## Helpers

| Helper | Returns | Use for |
|---|---|---|
| `parse_datetime` | UTC-aware `datetime` | Ingest / parse (optional `naive_timezone` for source wall clocks) |
| `get_source_timezone` | `ZoneInfo` for a location code | Look up US → `America/New_York`, EU → `Europe/Berlin`, … |
| `convert_local_wall_time_to_utc` | UTC-aware `datetime` | Calendar scrapers with known local hour/minute |
| `convert_to_display_timezone` | Paris `datetime` (same instant) | Clocks / `strftime` labels |
| `get_local_today` | Paris `date` (no time) | “Today” filters and week focus |

`SOURCE_TIMEZONE_BY_LOCATION_CODE` in `core.services` is the shared map for economic / market location codes.

`convert_to_display_timezone` and `get_local_today` are not interchangeable: one shifts a full timestamp for display; the other answers “what calendar day is it in Paris right now?”.

## Examples

- INSEE embargo `2025-12-05T07:45:00+00:00` → store `07:45 UTC` → show `08:45` in winter Paris.
- Eurostat release-calendar `start` `2025-01-17T11:00Z` → store `11:00 UTC` → show `12:00` winter Paris (`13:00` CEST).
- FOMC announcement `14:00` America/New_York → store `19:00 UTC` (EST) or `18:00 UTC` (EDT) → show **`20:00`** Paris either way.
- US economic release scraped as naive `2026-03-20T08:30:00` with `naive_timezone=America/New_York` → store the correct UTC instant → Economic Events shows Paris time.

## Out of scope / follow-ups

Some ingestion tasks still call `date.today()` (container OS date, often UTC in Docker). Prefer `get_local_today()` when the calendar day should match Paris ops schedules. Period fields that are `DateField` only (no clock) are timezone-agnostic calendar dates.
