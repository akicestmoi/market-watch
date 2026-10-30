"""Static URLs and location lists for market price / holiday services."""

from market_overview.models import LocationChoices

# ---------------------------------------------------------------------------
# Interest-rate / yield scrapers
# ---------------------------------------------------------------------------
"""Source URLs for overnight rates, sovereign yields, and money-market series."""

GLOBAL_RATES_URL = "https://www.global-rates.com/en/interest-rates"
NY_FED_RATE_URL = "https://markets.newyorkfed.org/read?productCode=50&limit=25&startPosition=0&sort=postDt:-1&format=xml"
DEPT_TREASURY_RATE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve"
WEBSTAT_RATE_URL = "https://webstat.banque-france.fr/export/csv/fr/catalog"
BUNDESBANK_RATE_URL = "https://api.statistiken.bundesbank.de/rest/download/BBSSY"
BOJ_MUTAN_RATE_URL = "https://www.boj.or.jp/statistics/market/short/mutan/d_release"
BB_YIELD_CURVE_URL = "https://www.bb.jbts.co.jp/en/historical/main_rate.html"

# ---------------------------------------------------------------------------
# Public holidays
# ---------------------------------------------------------------------------
"""Nager.Date holiday API and locations used for market calendars."""

HOLIDAY_COUNTRIES: list[LocationChoices] = [
    LocationChoices.US,
    LocationChoices.FR,
    LocationChoices.JP,
]
HOLIDAY_API_URL = "https://date.nager.at/api/v3/publicholidays/"
