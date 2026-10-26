# Timezone Management

**Backend: UTC, timezone-aware. Display: Europe/Paris.**

## Rules

| Layer | Convention |
|---|---|
| **Storage** (`DateTimeField`, scraped embargoes, meeting instants) | UTC-aware datetimes (`USE_TZ = True`) |
| **Comparisons / “now”** | Aware UTC (`django.utils.timezone.now()` or `datetime.now(timezone.utc)`) |
| **Parsing** | Prefer aware input; **naive strings are assumed UTC** (`core.services.parse_datetime`) |
| **User-facing clocks** (UI labels, upcoming-event times, date chips) | Convert with `core.services.convert_to_display_timezone` → **Europe/Paris** (`TIME_ZONE`) |
| **Calendar “today”** (filters, week focus for the ops UI) | `core.services.get_local_today()` / `timezone.localdate()` (Paris date, not container `date.today()`) |
| **Celery Beat** | Wall-clock schedules in **Europe/Paris** (`CELERY_TIMEZONE = TIME_ZONE`) |

Do **not** strip `tzinfo` before saving. Naive values with `USE_TZ` are reinterpreted as Paris local time and shift the instant.

## Helpers

| Helper | Returns | Use for |
|---|---|---|
| `parse_datetime` | UTC-aware `datetime` | Ingest / parse |
| `get_display_timezone` | `ZoneInfo` (Europe/Paris) | When you need the zone object |
| `convert_to_display_timezone` | Paris `datetime` (same instant) | Clocks / `strftime` labels |
| `get_local_today` | Paris `date` (no time) | “Today” filters and week focus |

`convert_to_display_timezone` and `get_local_today` are not interchangeable: one shifts a full timestamp for display; the other answers “what calendar day is it in Paris right now?”.

## Examples

- INSEE embargo `2025-12-05T07:45:00+00:00` → store `07:45 UTC` → show `08:45` in winter Paris.
- FOMC meeting stored as `13:00 UTC` → show `14:00` in winter Paris (date-only labels use the Paris calendar day).

## Out of scope / follow-ups

Some ingestion tasks still call `date.today()` (container OS date, often UTC in Docker). Prefer `get_local_today()` when the calendar day should match Paris ops schedules. Period fields that are `DateField` only (no clock) are timezone-agnostic calendar dates.
