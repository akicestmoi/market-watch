"""Static paths and URLs for market-analysis article extraction."""

# ---------------------------------------------------------------------------
# News source registry
# ---------------------------------------------------------------------------
"""JSON catalog of scrapable news outlets."""

NEWS_SOURCES_JSON = "market_analysis/data_sources/news_sources.json"

# ---------------------------------------------------------------------------
# Article list URLs
# ---------------------------------------------------------------------------
"""Day / listing URLs and HTTP timeout for article extraction."""

BOURSIER_DAY_URL_TEMPLATE = (
    "https://www.boursier.com/actualites/news-du-jour/{yyyymmdd}"
)
SWISSINFO_LIST_URL = "https://www.swissinfo.ch/eng/bloomberg/"
HTTP_REQUEST_TIMEOUT_SECONDS = 180
