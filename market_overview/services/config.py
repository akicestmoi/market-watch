"""Static URLs and location lists for market price / holiday services."""

from market_overview.models.common import EquityIndexChoices, LocationChoices

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

# ---------------------------------------------------------------------------
# Sector analysis (single names + index weight proxies)
# ---------------------------------------------------------------------------
"""Catalog path and public weight-proxy URLs for SPX / CAC 40 / Nikkei 225."""

SINGLE_NAMES_JSON = "market_overview/data_sources/single_names.json"
EARNINGS_WATCHLIST_JSON = "market_overview/data_sources/earnings_watchlist.json"
IVV_HOLDINGS_CSV_URL = (
    "https://www.ishares.com/us/products/239726/"
    "ishares-core-s-p-500-etf/latest-holdings.csv"
)
NIKKEI_WEIGHT_CSV_URL = (
    "https://indexes.nikkei.co.jp/nkave/archives/file/"
    "nikkei_stock_average_weight_en.csv"
)
CAC40_WEIGHTS_PAGE_URL = "https://whichindex.com/indexes/cac-40/"

# Usage of dict: whichindex / Euronext symbols that are not plain CODE.PA on Yahoo.
CAC_YAHOO_TICKER_BY_INDEX_SYMBOL: dict[str, str] = {
    "MT": "MT.AS",
}

EQUITY_INDEX_BY_LOCATION: dict[LocationChoices, EquityIndexChoices] = {
    LocationChoices.US: EquityIndexChoices.SPX,
    LocationChoices.FR: EquityIndexChoices.CAC40,
    LocationChoices.JP: EquityIndexChoices.NIKKEI225,
}

LOCATION_BY_EQUITY_INDEX: dict[EquityIndexChoices, LocationChoices] = {
    EquityIndexChoices.SPX: LocationChoices.US,
    EquityIndexChoices.CAC40: LocationChoices.FR,
    EquityIndexChoices.NIKKEI225: LocationChoices.JP,
}
