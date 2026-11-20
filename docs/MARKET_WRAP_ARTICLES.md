# Market-wrap article scrapers

How each catalog news source in `market_analysis` picks the daily close/wrap for a `reporting_date`, and how the article body is extracted.

Catalog: [`market_analysis/data_sources/news_sources.json`](../market_analysis/data_sources/news_sources.json)  
Dispatch: `SOURCE_SCRAP_MAP` in `market_analysis/services/article_extraction.py`  
Shared helpers: `market_analysis/services/scrapers/common.py`  
URLs / title cues: `market_analysis/services/config.py`

## What `reporting_date` means

`reporting_date` is the **market session day** the recap is about (usually the Market Watch as-of / previous business day), not “when the HTML page was generated” and not always the publisher’s local calendar day.

Matching therefore aims for: *which cash/session day does this wrap describe?* Sources disagree on clocks and labels, so each scraper uses the signal that best tracks that session:

| Signal | When we use it | Rationale |
| --- | --- | --- |
| **Session timezone calendar day** | Swissinfo (NY), The Edge (KL) | Wire timestamps can fall after midnight in Paris/UTC while still covering the prior US (or Asian-desk) session |
| **Date embedded in the URL / day index** | CNBC, Boursier, Tokyo Closing Bell (slug) | Editorial URL is the session label the outlet itself uses for that wrap |
| **Listing card date** | Newsquawk, TBS | Card already shows the session day the desk assigned; no need to open every article first |
| **Article publish meta after title filter** | Boursorama, Zonebourse | Listings mix opens, previews, and several days of closes; title cues narrow candidates, then `article:published_time` / `time[datetime]` confirms the session day |

Regions (`GLOBAL` / `US` / `EU` / `FR` / `JP`) are UI/catalog tags, not exchange calendars.

## Shared pipeline

1. **Discover** a candidate on a listing (or day index) page.
2. **Match** it to `reporting_date` with the source’s session signal (table above).
3. **Fetch** the article HTML and extract body text (`extract_main_text`, or a source-specific extractor).
4. Return a `ScrapingResult` (`url` / `title` / `content` / `comment`). Multi-region sources (Boursorama, Zonebourse) return a list of `TaggedScrapingResult` with catalog `regions`.

| Concern | Detail |
| --- | --- |
| HTTP client | Plain `requests` for most sources; **curl_cffi** with `impersonate="chrome"` for Boursier, Boursorama, Zonebourse, CNBC (bot walls / 403s) |
| Body text | Prefer `.article-body` / `.article-main` / `[itemprop=articleBody]` / `main` before a bare `<article>` (related-story cards often sit in earlier `<article>` nodes) |
| Close-title cues | Boursorama / Zonebourse: `MARKET_CLOSE_TITLE_CUES_BY_SOURCE_REGION` + `MARKET_WRAP_TITLE_EXCLUDE_CUES` (rejects opens, previews, monthly/weekly, etc.) |
| Published-date verify | Cue-based FR/EU/US feeds: fetch candidates in order and keep the first whose `article:published_time` / `time[datetime]` equals `reporting_date` (`pick_article_matching_published_date`) |

---

## By source

### Swissinfo — Bloomberg Markets Wrap (`SWISSINFO_MARKET_WRAP`)

| | |
| --- | --- |
| **Regions** | GLOBAL |
| **Listing** | Swissinfo Bloomberg list |
| **Client** | `requests` via `scrap_article_from_listing` |
| **Card pick** | `article.teaser-wide-card` whose title contains `"markets wrap"` |
| **Date match** | Teaser `time[datetime]` → calendar date in **America/New_York** |
| **Why that date** | The wrap covers the **US cash session**. Europe often publishes overnight; a Saturday 01:30 Paris stamp is still Friday’s US session. NY date tracks the session; UTC/Paris date would shift overnight posts onto the wrong recap day |
| **Body** | `extract_main_text` |

### The Edge — Global Markets (`THE_EDGE_GLOBAL_MARKETS`)

| | |
| --- | --- |
| **Regions** | GLOBAL |
| **Listing** | Global+Markets flash category |
| **Client** | `requests` via `scrap_article_from_listing` |
| **Card pick** | Listing `__NEXT_DATA__` → `pageProps.corporateData`; wrap-like title cues (stocks/bonds/markets/…); reject e.g. “haven from”, “hedge fund returns” |
| **Date match** | Flash `created` epoch-ms → calendar date in **Asia/Kuala_Lumpur** |
| **Why that date** | Edge is an Asia morning desk; the flash `created` stamp is local KL time and lines up with the dateline session they are summarizing better than NY or UTC |
| **Body** | Prefer article-page `__NEXT_DATA__` `content` HTML, else `extract_main_text` |

### CNBC — Stock Market Daily Recap (`CNBC_STOCK_MARKET_DAILY_RECAP`)

| | |
| --- | --- |
| **Regions** | US |
| **Listing** | Stock Market Daily Recap index |
| **Client** | curl_cffi chrome |
| **Card pick** | Anchor whose href contains `stock-market-today-live-update` and a usable title |
| **Date match** | `/YYYY/MM/DD/` segment in the article URL |
| **Why that date** | CNBC’s live-update URLs are dated by the **US trading day** the live blog belongs to. That path date is stabler than listing teaser times (which move as the blog updates) |
| **Body** | `extract_main_text` |

### Newsquawk — US Market Wrap (`NEWSQUAWK_US_MARKET_WRAP`)

| | |
| --- | --- |
| **Regions** | US |
| **Listing** | Headlines list |
| **Client** | `requests` via `scrap_article_from_listing` |
| **Card pick** | `article.group` with title containing `"us market wrap"` |
| **Date match** | Card `time[datetime]` **date** equals `reporting_date` |
| **Why that date** | One titled wrap per day; the card datetime is the desk’s publish day for that US wrap and already matches the session we want without opening the article |
| **Body** | `extract_main_text` |

### TBS Bloomberg — 米国市況 / 日本市況 (`TBS_US_MARKETS` / `TBS_JAPAN_MARKETS`)

| | |
| --- | --- |
| **Regions** | US / JP |
| **Listing** | CROSS DIG search URLs (US vs Japan fulltext) |
| **Client** | `requests` via `scrap_article_from_listing` |
| **Card pick** | First `article.m-article` (newest-first) whose title contains `【米国市況】` or `【日本市況】` |
| **Date match** | Prefer `time` `datetime` attr; else dotted listing text `YYYY.MM.DD` |
| **Why that date** | TBS labels each 市況 card with the **Japanese calendar day of the wrap** (including afternoon updates). Several cards can share a day; we take the newest matching title marker so we get the latest wrap for that session day |
| **Body** | `extract_main_text` (`.article-body` first — sidebar related stories use other `<article>` nodes) |

### Tokyo Closing Bell (`TOKYO_CLOSING_BELL`)

| | |
| --- | --- |
| **Regions** | JP |
| **Listing** | Homepage |
| **Client** | `requests` via `scrap_article_from_listing` |
| **Card pick** | Homepage `article` whose title contains `"nikkei"` |
| **Date match** | Prefer `YYYY-MM-DD` in the post URL slug; else `time[datetime]` date |
| **Why that date** | The slug date is the **Tokyo session day** the English wrap is written for. Prefer it over post `datetime` when both exist so a late edit does not re-key the article onto the next calendar day |
| **Body** | `extract_main_text` |

### Boursier — Clôture Paris (`BOURSIER_CLOTURE_PARIS`)

| | |
| --- | --- |
| **Regions** | FR |
| **Listing** | Day index `…/news-du-jour/{yyyymmdd}` |
| **Client** | curl_cffi chrome |
| **Card pick** | First link whose visible text starts with `Clôture Paris` / `Cloture Paris` |
| **Date match** | Implied by the day-index URL (no separate publish-date check) |
| **Why that date** | Boursier already buckets news by calendar day. Requesting `{reporting_date}` as `yyyymmdd` *is* the match; “Clôture Paris” on that page is that day’s Paris close wrap |
| **Body** | `extract_main_text` |

### Boursorama (`BOURSORAMA`)

| | |
| --- | --- |
| **Regions** | EU, FR (optional `region=` filter) |
| **Listing** | Marchés + Actualités feeds |
| **Client** | curl_cffi chrome |
| **Card pick** | `li.c-list-news__line` / `div.c-event` titles matching region close cues; exclude open/preview cues; rank wires Reuters → AFP → Zonebourse → Boursorama |
| **Date match** | Walk ranked candidates; keep first whose article publish meta date equals `reporting_date` |
| **Why that date** | Homepages are a stream of many days and story types. Title cues select *close* wraps for the region; publish meta then picks the one written for `reporting_date`. Ranking prefers cleaner wires when several same-day closes exist |
| **Body** | `extract_main_text` |

### Zonebourse (`ZONEBOURSE`)

| | |
| --- | --- |
| **Regions** | US, EU, FR (optional `region=` filter) |
| **Listing** | CAC 40 news, then Indices, then generic Actualités (Paris/Europe closes often fall off the generic list when US headlines dominate) |
| **Client** | curl_cffi chrome |
| **Card pick** | `/actualite-bourse/` links whose title matches region close cues (exclude cues apply); title length ≥ 20 |
| **Date match** | Same as Boursorama: first candidate with matching publish meta date |
| **Why that date** | Same stream problem as Boursorama: cue filter finds close-style headlines; article publish date binds the candidate to the session day. Multiple listings raise the chance the FR/EU close is still visible |
| **Body** | `extract_main_text` |

---

## Quick reference

| Source | Session signal | Why | Wrap selector |
| --- | --- | --- | --- |
| Swissinfo | NY date from teaser `datetime` | US session; overnight EU publish | Title “markets wrap” |
| The Edge | KL date from flash `created` | Asia morning desk dateline | Wrap-like flash title cues |
| CNBC | `/YYYY/MM/DD/` in live-update URL | Editorial US trading-day URL | Path `stock-market-today-live-update` |
| Newsquawk | Card `datetime` date | One US wrap card per day | Title “us market wrap” |
| TBS JP/US | Listing `datetime` / `YYYY.MM.DD` | Desk’s 市況 day; newest same-day | `【日本市況】` / `【米国市況】` |
| Tokyo Closing Bell | URL slug date (fallback `datetime`) | Slug = Tokyo session day | Title “nikkei” |
| Boursier | Day-index `{yyyymmdd}` | Site already buckets by day | Title starts “Clôture Paris” |
| Boursorama | Article publish meta after cues | Stream needs filter then day confirm | Region close cues + provider rank |
| Zonebourse | Article publish meta after cues | Same as Boursorama; multi-listing | Region close cues |
