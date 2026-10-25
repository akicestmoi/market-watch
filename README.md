# Market Watch

A Django-based market monitoring platform that ingests market, economic, and central-bank data on a schedule, exposes it through a REST API and operator UI, and runs an LLM-assisted **market analysis** pipeline (daily T-1 news recap + chat).

## Stack

| Layer | Choice |
|---|---|
| **Backend** | Python, Django 4.2, Django REST Framework |
| **API docs** | OpenAPI via `drf-spectacular` (Swagger UI at `/api/docs/`) |
| **Database** | PostgreSQL (`psycopg2`) |
| **Cache / broker** | Redis (Celery broker/result backend, distributed locks, LLM article digests) |
| **Async jobs** | Celery + Celery Beat (Europe/Paris schedules); Flower for monitoring |
| **LLM** | PydanticAI + OpenAI (`OPENAI_API_KEY`, `LLM_MODEL_NAME`) |
| **Data / scraping** | pandas, yfinance, BeautifulSoup, requests, curl-cffi, pdfplumber |
| **Frontend (ops UI)** | Server-rendered Django templates + static CSS/JS (`data_visualization`) |
| **Tooling** | Docker Compose, Makefile, pytest, Black / Flake8 / isort / Pyright, ESLint / Stylelint |
| **Config** | `django-environ` (`.env`) |

**Runtime shape:** Django web app → Celery Beat → Redis → Celery workers. Domain logic lives in Django apps; visualization and analysis compose those domains rather than owning their own primary datasets.

## Quick Start

### For Local Development

1. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Unix/MacOS
   source venv/bin/activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   npm install  # For linters
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:

   ```env
   SECRET_KEY
   POSTGRES_DB
   POSTGRES_USER
   POSTGRES_PASSWORD
   DB_HOST
   DB_PORT
   CELERY_BROKER_URL
   CELERY_RESULT_BACKEND
   OPENAI_API_KEY
   ```

4. **Set up database and start server**:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py runserver
   ```

5. **Access the application**:
   - Main App: http://127.0.0.1:8000/
   - API Documentation: http://127.0.0.1:8000/api/docs/
   - Admin Panel: http://127.0.0.1:8000/admin/

### For Docker Development

1. **Start with Docker**:

   ```bash
   make start
   ```

2. **Access the application**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs/
   - Admin Panel: http://localhost:8000/admin/ (admin/admin123)
   - Celery Flower: http://localhost:5555 (Celery task monitoring)

3. **Port conflicts:**

   ```bash
   make stop
   ```

4. **View logs:**

   ```bash
   make logs-webapp  # Webapp container logs
   ```

5. Docker Commands
   Use the Makefile for convenient commands:

   ```bash
   make help            # Show all available commands
   make install         # Install dependencies
   make lint            # Lint the code
   make flake8          # Run Flake8
   make pyright         # Run Pyright
   make build           # Build the Docker image
   make start           # Start the application
   make stop            # Stop all containers
   make restart         # Restart all containers
   make logs            # Show logs from all containers
   make logs-webapp     # Show logs from webapp container
   make shell           # Open a shell in the webapp container
   make makemigrations  # Prepare database migrations
   make migrate         # Run database migrations
   make collectstatic   # Collect static files
   make celery-beat     # View Celery beat scheduler logs
   make celery-worker   # View Celery worker logs
   make flower          # View Celery Flower monitoring logs
   make test            # Run all tests (pytest)
   make test-coverage   # Run tests with coverage report (HTML + terminal)
   make test-app        # Run tests for a specific app (requires APP=name, uses pytest)
   make clean           # Clean up Docker resources
   make db-export       # Export database to SQL file
   make db-import       # Import database from SQL file (requires SQL_FILE=path)
   make trigger-task    # Manually trigger a scheduled Celery task (requires TASK=name)
   ```

## API Documentation

The application includes comprehensive OpenAPI documentation:

- **Swagger UI**: http://localhost:8000/api/docs/
- **Schema**: http://localhost:8000/api/schema/

## Celery Task Scheduling

The application includes automated data ingestion and maintenance tasks using Celery and Redis:
Django Web App ==> Celery Beat (Scheduler) ==> Redis (Broker) ==> Worker Process

### Scheduled Tasks Overview

All scheduled tasks run in **Europe/Paris timezone**. Tasks are organized into two categories:

#### **Data Ingestion Tasks** (Daily/Regular - Weekdays Only)

These tasks fetch and ingest data from external sources:

1. **Market Data Ingestion** - Runs **3 times daily** (8:00 AM, 2:00 PM, 8:00 PM)
   - Ingests asset prices: stocks, FX, crypto, commodities, government bond rates
   - Task: `market_overview.tasks.scheduled_market_data_ingestion`
   - On success, queues **Market Analysis Pipeline** for that price date (see [Market Analysis](#market-analysis))

2. **STIR Futures Prices Ingestion** - Runs **2 times daily** (8:00 AM, 8:40 PM)
   - Ingests Short-Term Interest Rate futures prices (FedFunds, ESTR, TONA)
   - Task: `central_banks_overview.tasks.scheduled_stir_prices_ingestion`

3. **Economic Data and Schedule Update** - Runs **daily** (8:00 AM)
   - Ingests economic indicators and updates publication schedules
   - Task: `economic_overview.tasks.scheduled_economic_data_and_schedule_update`

4. **Central Bank Meetings and STIR Futures Cleanup** - Runs **daily** (8:00 AM)
   - Updates central bank meeting dates
   - Cleans up old STIR futures prices (keeps last 7 days)
   - Task: `central_banks_overview.tasks.scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings`

#### **Maintenance Tasks** (Monthly - 1st of each month at 8:00 AM)

These tasks clean up old data and maintain database health:

1. **Price Update Logs Cleanup**
   - Deletes price update logs older than 1 month
   - Task: `market_overview.tasks.scheduled_price_update_logs_cleanup`

2. **STIR Futures Price Update Logs Cleanup**
   - Deletes STIR futures price update logs older than 1 month
   - Task: `central_banks_overview.tasks.scheduled_stir_futures_price_update_logs_cleanup`

3. **Economic Data Update Logs Cleanup**
   - Deletes economic data update logs older than 1 month
   - Task: `economic_overview.tasks.scheduled_economic_data_update_logs_cleanup`

4. **Holidays Ingestion**
   - Ingests holidays for all supported countries (US, FR, DE, JP)
   - Task: `market_overview.tasks.scheduled_holidays_ingestion`

### Task Schedule Summary

| Task | Frequency | Schedule | Time |
|------|-----------|----------|------|
| Market Data Ingestion | 3x daily | Weekdays | 8:00, 14:00, 20:00 |
| STIR Prices Ingestion | 2x daily | Weekdays | 8:00, 20:40 |
| Economic Data Update | Daily | Weekdays | 8:00 |
| CB Meetings & Cleanup | Daily | Weekdays | 8:00 |
| Logs Cleanup (All) | Monthly | 1st of month | 8:00 |
| Holidays Ingestion | Monthly | 1st of month | 8:00 |

### Manually Triggering Tasks

You can manually trigger any scheduled task using either the Makefile command or the Django management command:

**Using Makefile (Recommended for Docker):**
```bash
# Run task synchronously (direct function call)
make trigger-task TASK=scheduled_market_data_ingestion

# Run task asynchronously via Celery
make trigger-task TASK=scheduled_market_data_ingestion ASYNC=1
```

**Using Django Management Command:**
```bash
# Run task synchronously (direct function call)
python manage.py trigger_task <task_name>

# Run task asynchronously via Celery
python manage.py trigger_task <task_name> --async
```

**Available task names:**
- `scheduled_market_data_ingestion`
- `scheduled_analysis_pipeline` (requires `reporting_date=YYYY-MM-DD`; see Market Analysis)
- `scheduled_stir_prices_ingestion`
- `scheduled_economic_data_and_schedule_update`
- `scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings`
- `scheduled_price_update_logs_cleanup`
- `scheduled_stir_futures_price_update_logs_cleanup`
- `scheduled_economic_data_update_logs_cleanup`
- `scheduled_holidays_ingestion`

**Examples:**

Using Makefile:
```bash
# Trigger market data ingestion synchronously
make trigger-task TASK=scheduled_market_data_ingestion

# Trigger holidays ingestion asynchronously
make trigger-task TASK=scheduled_holidays_ingestion ASYNC=1

# Trigger economic data update
make trigger-task TASK=scheduled_economic_data_and_schedule_update
```

Using Django management command:
```bash
# Trigger market data ingestion synchronously
python manage.py trigger_task scheduled_market_data_ingestion

# Trigger holidays ingestion asynchronously
python manage.py trigger_task scheduled_holidays_ingestion --async
```

**Alternative methods:**

1. **Django Shell:**
   ```python
   python manage.py shell
   >>> from market_overview.tasks import scheduled_market_data_ingestion
   >>> scheduled_market_data_ingestion.delay()  # Async
   >>> scheduled_market_data_ingestion()  # Sync
   ```

2. **Celery CLI (if Celery worker is running):**
   ```bash
   celery -A core call market_overview.tasks.scheduled_market_data_ingestion
   ```

## Applications

Project-owned Django apps (see `INSTALLED_APPS` in `core/settings.py`). URL mounts are wired in `core/urls.py`. Together they form a pipeline: **ingest** (market / economic / CB) → **expose** (REST + admin) → **present** (HTML recaps/charts) → **interpret** (LLM daily analysis).

| App | Package | URL prefix | Purpose (short) |
|---|---|---|---|
| Core | `core` | *(project root)* | Project kernel: settings, Celery, shared utilities, OpenAPI |
| Market Overview | `market_overview` | `/markets/` | Asset catalog, daily closes, holidays, price audit logs |
| Economic Overview | `economic_overview` | `/economics/` | Macro indicators, observations, publication calendars |
| Central Banks | `central_banks_overview` | `/central-banks/` | CB meetings, STIR futures, implied rate-path probabilities |
| Data Visualization | `data_visualization` | `/` (site root pages) | Operator UI: HTML recaps, charts, DB management |
| Market Analysis | `market_analysis` | `/analysis/` | LLM T-1 news recap + interactive chat over verified data |

**Dependency sketch:** `core` ← all · `market_overview` → viz + some CB scrapers + analysis trigger · `economic_overview` / `central_banks_overview` → viz · `data_visualization` → UI only · `market_analysis` → LLM recaps after market price ingestion.

### Core (`core`)

**Purpose:** shared project kernel — wiring, cross-cutting helpers, and infra — not a domain API.

Owns Django settings, Celery app bootstrap, Redis locks, abstract base models, OpenAPI/Swagger mounts, and the `trigger_task` management command so every domain app can plug in without duplicating infrastructure.

- **Models:** abstract `BaseModel` (`date_added` / `last_modified`) and `BaseLogModel` (text logs). No concrete domain tables.
- **Services / helpers:** logging, HTML fetch, datetime parse, cache TTL constants, Redis distributed locks (`locks.py`), `BaseAPIView` + OpenAPI tag helpers, Celery app (`celery.py`) with task autodiscover.
- **URLs:** mounts other apps; also `admin/`, `api/schema/`, `api/docs/` (Swagger via `drf_spectacular`).
- **Management:** `trigger_task` to run scheduled Celery tasks manually (see [Celery Task Scheduling](#celery-task-scheduling)).
- **Celery tasks:** none defined here (broker/app only).

### Market Overview (`market_overview`)

**Purpose:** source of truth for *what* assets exist and *what* they closed at on each session day.

Catalogs equities, rates, FX, crypto, and commodities; ingests daily prices from multiple public sources; tracks market holidays and price-update audit logs. Successful weekday ingestion is also the trigger that queues the market-analysis pipeline for that price date.

- **Models:** `AssetModel` (metadata, ticker, source, location, class); `MarketPriceModel` (per-asset daily price, unique on asset+date); `PriceUpdateLogModel`; `HolidayModel`.
- **Services:** `price_ingestion_services` — scrape/ingest closes (Yahoo, US Treasury, NY Fed, Webstat, Bundesbank, BoJ, BB, GlobalRates, etc.); `market_data_services` — queries, missing prices, bulk/CSV updates, log cleanup; `holiday_services` — public holidays (e.g. Nager.Date for supported countries).
- **Data sources:** `data_sources/market_data.json` (seed assets), `data_sources/single_names.json`.
- **HTTP (`/markets/`):** `asset/*` (generate base data, names, details); `prices/*` (ingest, batch ingest, list, missing prices, bulk/CSV update, logs, mark-as-holiday); `holidays/*`.
- **Tasks:** `scheduled_market_data_ingestion` (then queues market analysis); `scheduled_price_update_logs_cleanup`; `scheduled_holidays_ingestion`.
- **Relations:** Feeds visualization recaps/charts; rate scrapers reused by central banks; successful ingestion triggers `market_analysis`.

### Economic Overview (`economic_overview`)

**Purpose:** track macro releases — indicator definitions, published values, and when the next prints are due.

Maintains the economic calendar and observation history used by the economic recap/charts and by market analysis when building daily context. Scheduled jobs refresh due indicators and scrape publication schedules so the UI and LLM stay aligned with official calendars.

- **Models:** `EconomicIndicatorInformationModel`; `PublicationScheduleModel`; `EconomicDataModel`; `EconomicDataUpdateLogModel`.
- **Services:** `data_ingestion_services` — scrape/ingest series (e.g. INSEE; JP Cabinet Office stubs); `economic_data_services` — due indicators, CRUD helpers, log cleanup; `publication_services` — scrape/update publication schedules.
- **Data sources:** `data_sources/economic_data.json` (seed indicators); series catalog and methodology notes in `docs/INDICATORS.md`.
- **HTTP (`/economics/`):** `indicator/generate-base-information`, `indicator/ingest` (latest), `indicator/ingest-historical`, `indicator/ingest-specific`, `indicator` (detail); `schedule/update`.
- **Tasks:** `scheduled_economic_data_and_schedule_update`; `scheduled_economic_data_update_logs_cleanup`.
- **Relations:** Consumed by `data_visualization` economic recap/charts; location concepts align with market holidays / CB calendar in upcoming-events UI.

### Central Banks Overview (`central_banks_overview`)

**Purpose:** central-bank calendar and market-implied policy path for Fed / ECB / BoJ.

Stores meeting dates, CB data series, and STIR futures prices, then derives meeting-by-meeting **probability matrices** for rate moves. That powers the central-banks recap and upcoming-events views, and complements market prices with a policy-path lens.

- **Models:** `CentralBankMeetingModel`; `CentralBankDataModel`; `StirFuturesModel` (e.g. Fed funds / ESTR / mutan futures); `StirFuturesPriceUpdateLogModel`. Reuses `market_overview` location enums via a CB location map.
- **Services:** `cb_data_services` — ingest/query CB series; `cb_meetings_services` — scrape FOMC/ECB/BoJ calendars; `stir_prices_ingestion_services` — Yahoo, TFX, ESTR PDF, bulk/CSV; `cb_inference_services` — probability matrices from STIR (Fed vs 3M futures methodologies).
- **Data sources:** `data_sources/central_banks_data.json`; Fed/ECB/BoJ sites; Yahoo; TFX; ESTR PDF; some rate scrapers shared with market overview.
- **HTTP (`/central-banks/`):** `data`, `data/ingest`; `meeting-dates`, `meeting-dates/ingest`; `stir-futures` (+ ingest, ESTR PDF, bulk/CSV); `probability-matrix`.
- **Tasks:** `scheduled_stir_prices_ingestion`; `scheduled_stir_futures_price_update_logs_cleanup`; `scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings`.
- **Relations:** Depends on `market_overview` for locations / some scrapes; powers CB recap and upcoming events in visualization.

### Data Visualization (`data_visualization`)

**Purpose:** human-facing operator console — browse recaps and charts without calling the API by hand.

Server-rendered HTML for market / economic / central-bank summaries, interactive charts, and a lightweight database management page. **No models of its own** — read-only composition over the domain apps.

- **Services:** `market_recap_services` / `market_chart_services` ← market overview; `economic_recap_services` / `economic_chart_services` ← economic (+ holidays/CB meetings for calendar); `central_bank_recap_services` ← CB data + probability matrices; `database_management_services` — table counts/sizes for the management page.
- **HTTP (site root):** `market-recap/`, `market-charts/`, `economic-recap/`, `economic-charts/`, `central-banks-recap/`, `management/`.
- **Static:** CSS/JS under `data_visualization/static/`; templates under `data_visualization/templates/`.
- **Celery:** none.
- **Relations:** Presentation layer for `market_overview`, `economic_overview`, and `central_banks_overview`.

### Market Analysis (`market_analysis`)

**Purpose:** turn verified T-1 prices + a small set of day-scoped news wraps into one persisted daily narrative, then allow follow-up Q&A via chat.

Cost-conscious research agent: scrape date-scoped market wraps, analyze them **in memory** with an LLM, persist a single `DailyRecap` tied to DB prices (not invented from headlines), and continue via client-sent `messages`. Mounted under **`/analysis/`**.

#### Goals and non-goals

| Does | Does not |
|---|---|
| One AI daily analysis per `reporting_date` | Store scraped articles in Postgres |
| Use verified `MarketPriceModel` prices in the recap prompt | Invent prices from news text |
| Cache same-day article digests in Redis (~24h) | Dedicated feedback / training pipeline |
| Improve behavior via repo markdown (skills / instructions) | Auto-train or self-modify prompts |

`reporting_date` is the **T-1 session / price date** (same calendar day as market data ingestion). It is **required** on pipeline, recap generate, and article-cache endpoints — there is no “default to today”.

#### What is stored

| Store | Contents |
|---|---|
| **Postgres** | `DailyRecapModel` only — one row per `reporting_date` (`title`, `analysis_content`, `source_urls`, `model_name`, `prompt_version`) |
| **Redis** | Optional article-analysis digests keyed by reporting date + article URL + `PROMPT_VERSION` (TTL 24h). Used to skip repeat LLM analysis on re-runs. Inspect via `GET /analysis/article-cache` |
| **Repo JSON** | `market_analysis/data_sources/news_sources.json` — which sources to scrape (`source` enum, `name`, `base_url`) |
| **Repo markdown** | `market_analysis/llm/skills/market-analysis.md` (injected into prompts) and `market_analysis/llm/instructions/*.md` (system prompts for analysis / recap / chat) |
| **Settings** | `OPENAI_API_KEY`, `LLM_MODEL_NAME` (full PydanticAI model id, e.g. `openai:gpt-6-luna`) in `core/settings.py` |

News source enum: `NewsSourceChoices` in `market_analysis/models.py`. Scrapers are mapped in code (`SOURCE_SCRAP_MAP`), not in the DB.

#### Pipeline flow

```
Price ingestion succeeds (reporting_date = price_date)
        │
        ▼
schedule_market_analysis_after_ingestion(price_date)
        │
        ▼
scheduled_analysis_pipeline(reporting_date)   # Celery, Redis lock per date
        │
        ▼
run_daily_analysis_pipeline(reporting_date)
  • skip if DailyRecap already exists (unless force)
        │
        ▼
extract_all_articles(reporting_date)          # in memory, one article / source
        │
        ▼
analyze_extracted_articles(...)               # LLM; Redis cache hit/miss
        │
        ▼
generate_daily_recap(reporting_date, analyses)
  • inject skills + bulk market context from DB
  • persist / overwrite DailyRecapModel
```

Orchestration: `market_analysis.services.market_analysis_services.run_daily_analysis_pipeline`.
Celery entry: `market_analysis.tasks.scheduled_analysis_pipeline` (requires ISO `reporting_date` string).
Queued after successful price ingestion from `market_overview.tasks`.

#### News extraction

Config-driven list in `news_sources.json`. Each entry has a dedicated scrap function in `article_extraction_services.py` (same pattern as price ingestion: `ScrapingResult`, `@ttl_cache`).

| Enum | Scraper | Discovery |
|---|---|---|
| `BOURSIER_CLOTURE_PARIS` | `scrap_boursier_cloture_paris` | `boursier.com/.../news-du-jour/{YYYYMMDD}` → **Clôture Paris** (HTTP via `curl_cffi` Chrome impersonation) |
| `SWISSINFO_MARKET_WRAP` | `scrap_swissinfo_market_wrap` | [Swissinfo Bloomberg listing](https://www.swissinfo.ch/eng/bloomberg/) → **Markets Wrap** for that calendar day |

- **One article per source** for the given `reporting_date`.
- Scraped body is treated as **untrusted data** (`safe_untrusted_content_wrapper` in `market_analysis/llm/config.py`) — never as agent instructions.
- Results stay in process memory (`ArticleData`); only URLs are copied onto the recap as `source_urls`.

#### LLM analysis and recap

| Piece | Module / path | Role |
|---|---|---|
| Structured outputs | `market_analysis/llm/schemas.py` | Pydantic models for article analysis, daily recap, chat |
| Constants / loaders | `market_analysis/llm/config.py` | `PROMPT_VERSION`, skill/instruction loaders, untrusted wrapper |
| Analysis + recap | `llm_market_recap_services.py` | Per-article analysis, bulk market context for recap, `DailyRecapModel` write |
| Redis digests | `analysis_cache_services.py` | Get/set/list cached analyses |
| Chat | `llm_interaction_services.py` | Shared chat agent; tools for recaps, prices, economic context, gated recap update |
| Skills | `llm/skills/market-analysis.md` | Zones, regime language, econ coverage, chat update rules |
| Instructions | `llm/instructions/{analysis,recap,chat}_system.md` | Agent system prompts |

**Article analysis fields** (in memory / Redis only): title, summary, `event_types` (list), companies, sectors, sentiment, key_facts, uncertainties, `source_url`. No tickers on analysis (news names rarely match your DB tickers); chat can pull verified prices for a date via the market-context tool.

**Recap**: combines analyzed news + market context + **economic indicator context** from `economic_overview`. Structure: Global → US → EU → Japan (see market-analysis skill). Idempotent one row per date; `force=True` overwrites.

**Chat**: may propose recap edits; persists via tool only after explicit user agreement or order. May propose a Cursor Agent prompt to edit `market-analysis.md` only after that update path is agreed.

Improving quality (no Feedback DB):

1. Edit `llm/skills/market-analysis.md` and/or `llm/instructions/*.md`
2. Edit `data_sources/news_sources.json` or scrapers / chat tools
3. Redeploy — next run loads files from disk (`PROMPT_VERSION` also keys the Redis cache)

PydanticAI does **not** learn from feedback by itself.

#### HTTP API (`/analysis/`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/analysis/recap` | Fetch latest recap, or filter by `reporting_date` / `id` |
| `POST` | `/analysis/recap/generate` | Run pipeline in-process (`reporting_date` required, optional `force`) |
| `POST` | `/analysis/chat` | Q&A; optional prior `messages` for continuity |
| `GET` | `/analysis/article-cache` | Inspect Redis digests for a `reporting_date` (optional `source_url`) |

OpenAPI: tag **Market Analysis** on Swagger UI (`/api/docs/`). Serializers live under `market_analysis/open_api/`.

#### Chat

- Shared agent instance (`get_chat_agent`) with fixed tools/instructions.
- Conversation continuity = client-sent `messages` in the request body.
- Tools: recent daily recaps, market prices for a reporting date, economic context, gated recap update.
- Skills stay in the prompt (not a tool).

#### Manual runs

```bash
# HTTP — runs extract → analyze → persist in the request (not queued)
# POST /analysis/recap/generate  {"reporting_date": "2026-10-23", "force": true}

# Scheduled / ops — Celery task after price ingestion (or call from shell)
python manage.py shell
>>> from market_analysis.tasks import scheduled_analysis_pipeline
>>> scheduled_analysis_pipeline.delay(reporting_date="2026-10-23", force=False)
```

Requires `OPENAI_API_KEY` and a valid `LLM_MODEL_NAME`. Pipeline skips when a daily recap already exists (unless `force`).

#### Layout (high level)

```text
market_analysis/
  data_sources/news_sources.json
  llm/
    config.py
    schemas.py
    skills/
    instructions/
  models.py                 # DailyRecapModel, NewsSourceChoices
  tasks.py
  services/
    market_analysis_services.py      # gates + pipeline
    article_extraction_services.py   # scrapers
    llm_market_recap_services.py     # analyze + recap
    analysis_cache_services.py       # Redis digests
    llm_interaction_services.py      # chat
  views/                             # API
  open_api/
  tests/
```

## Testing

The project uses **pytest** with **pytest-django** for comprehensive unit testing. Tests are organized by app and cover both views and services. Pytest provides detailed test summaries, progress indicators, and performance metrics.

### Running Tests

**Run all tests:**
```bash
make test
```

**Run tests with coverage report:**
```bash
make test-coverage
```
This generates:
- Terminal coverage report showing percentage coverage per module
- HTML coverage report in `htmlcov/` directory (open `htmlcov/index.html` in a browser)

**Run tests for a specific app:**
```bash
make test-app APP=market_overview
```

**Run tests using pytest directly:**
```bash
# All tests
python -m pytest

# Specific app
python -m pytest market_overview/tests

# Specific test file
python -m pytest market_overview/tests/views/test_market_overview_views.py

# Specific test class
python -m pytest market_overview/tests/views/test_market_overview_views.py::AssetDetailsViewTest

# Specific test method
python -m pytest market_overview/tests/views/test_market_overview_views.py::AssetDetailsViewTest::test_get_asset_details_success

# Run with coverage report (terminal only)
python -m pytest --cov=market_overview --cov-report=term

# Run with coverage report (HTML + terminal)
python -m pytest --cov --cov-report=term --cov-report=html

# Run only failed tests from last run
python -m pytest --lf

# Run tests matching a pattern
python -m pytest -k "test_get_asset"
```

### Test Configuration

Pytest configuration is defined in `pytest.ini`:
- **Test discovery**: Automatically finds tests in any `*/tests` directory
- **Verbose output**: Detailed test information by default
- **Color output**: Color-coded pass/fail indicators
- **Database reuse**: Reuses test database between runs for faster execution (`--reuse-db`)
- **Duration reporting**: Shows slowest 10 tests
- **Django integration**: Configured with `pytest-django` for Django-specific features

### Test Structure

Tests are organized in `tests/` directories within each app:
- `tests/views/` - API view tests
- `tests/services/` - Service function tests

Each test file follows Django's TestCase pattern and includes:
- Setup methods for test fixtures
- Tests for success scenarios
- Tests for error handling
- Tests for edge cases
