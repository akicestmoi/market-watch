"""Static URLs, calendars, and constants for central-bank / STIR services."""

from central_banks_overview.models import CentralBankChoices

# ---------------------------------------------------------------------------
# Meeting calendars
# ---------------------------------------------------------------------------
"""Policy-meeting calendar pages scraped for announcement dates."""

FOMC_MEETING_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BOJ_MPM_URL = "https://www.boj.or.jp/mopo/mpmsche_minu/index.htm"
ECB_MEETING_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

# ---------------------------------------------------------------------------
# Announcement wall clocks
# ---------------------------------------------------------------------------
"""Local announcement times (DST-aware → UTC on ingest) per central bank."""

FOMC_ANNOUNCEMENT_HOUR = 14
FOMC_ANNOUNCEMENT_MINUTE = 0
FOMC_SOURCE_TIMEZONE = "America/New_York"
ECB_ANNOUNCEMENT_HOUR = 14
ECB_ANNOUNCEMENT_MINUTE = 15
ECB_SOURCE_TIMEZONE = "Europe/Berlin"
# Press conference typically 15:30 JST → 07:30 Europe/Paris in winter (08:30 in summer).
BOJ_ANNOUNCEMENT_HOUR = 15
BOJ_ANNOUNCEMENT_MINUTE = 30
BOJ_SOURCE_TIMEZONE = "Asia/Tokyo"

# ---------------------------------------------------------------------------
# Date / month parsing
# ---------------------------------------------------------------------------
"""Month abbreviation helpers and how many upcoming meetings to ingest."""

NB_MEETINGS_TO_INGEST = 15
# Keep recently past meetings in the DB so market-recap / day-events can still
# show a rates decision after the announcement day (ingest otherwise deletes them).
MEETING_HISTORY_LOOKBACK_DAYS = 7

CENTRAL_BANKS_DATA_JSON = "central_banks_overview/data_sources/central_banks_data.json"

MONTH_NUMBER_BY_ABBREVIATION: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
CME_MONTH_CODE_BY_MONTH: dict[int, str] = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

# ---------------------------------------------------------------------------
# STIR futures
# ---------------------------------------------------------------------------
"""Fed Funds futures contract naming and TFX history / calendar sources."""

FF_FUTURES_PREFIX = "ZQ"
FF_FUTURES_SUFFIX = ".CBT"
FED_FUNDS_FUTURES_MONTHS = 15  # Number of months to fetch (1-15)
TFX_HISTORICAL_LOOKBACK_DAYS = 90
TFX_HISTORICAL_FUTURES_DATA_URL = "https://www.tfx.co.jp/historical/futures/result"
TFX_HISTORICAL_FUTURES_TRADING_CALENDAR_URL = (
    "https://www.tfx.co.jp/historical/futures/tradingcalendar.html"
)

# ---------------------------------------------------------------------------
# Rate-path probabilities
# ---------------------------------------------------------------------------
"""Step size, scenarios, and cutoffs for implied meeting probability paths."""

STEP_SIZE = 25
MAX_MEETINGS = 3
STANDARD_STEP_SCENARIOS = [
    i * STEP_SIZE for i in range(-MAX_MEETINGS, MAX_MEETINGS + 1)
]

PROBABILITY_EXTENSION_STEPS = 5
PROBABILITY_THRESHOLD = 1.0
MAX_MEETINGS_TO_COVER = 8

# ---------------------------------------------------------------------------
# Target-rate tickers
# ---------------------------------------------------------------------------
"""Central bank → overnight target / reference rate short name."""

TARGET_RATE_SHORT_NAME_BY_CENTRAL_BANK: dict[CentralBankChoices, str] = {
    CentralBankChoices.FRB: "EFFR",
    CentralBankChoices.ECB: "ESTR",
    CentralBankChoices.BOJ: "MUTAN",
}
