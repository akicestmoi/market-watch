"""Static URLs, dataset templates, and ticker maps for economic ingestion / schedules."""

from dataclasses import dataclass
from typing import NamedTuple, Required, TypedDict

from economic_overview.models import EconomicPublicationFrequencyChoices

# ---------------------------------------------------------------------------
# INSEE
# ---------------------------------------------------------------------------
"""INSEE BDM series CSV download: frequency → ZIP member basename and URL template."""

INSEE_SERIES_CSV_URL_TEMPLATE = "https://bdm.insee.fr/series/{ticker}/csv"
# INSEE publication schedule (agenda-diffusion) search endpoint.
INSEE_PUBLICATION_SCHEDULE_URL = "https://www.insee.fr/fr/agenda-diffusion"
# ZIP member basename (no ``.csv``) for the values file inside each BDM series ZIP.
INSEE_CSV_NAME_BY_FREQUENCY: dict[EconomicPublicationFrequencyChoices, str] = {
    EconomicPublicationFrequencyChoices.MONTHLY: "valeurs_mensuelles",
    EconomicPublicationFrequencyChoices.QUARTERLY: "valeurs_trimestrielles",
    EconomicPublicationFrequencyChoices.ANNUAL: "valeurs_annuelles",
}


# ---------------------------------------------------------------------------
# Eurostat
# ---------------------------------------------------------------------------
"""Eurostat Statistics API observations, series templates, and publication calendar.

Configured series IDs match ``economic_data.json`` tickers (e.g. ``namq_10_gdp``).
Geo comes from the indicator ``location`` (same codes as Eurostat), except our ``EU``
location uses Eurostat geo ``EA`` (``EUROSTAT_GEO_FOR_EU_LOCATION``). ``dataset`` is
the Statistics API path segment (may differ from ``series_id`` for unit variants).
"""


class EurostatQueryParams(TypedDict, total=False):
    """Eurostat Statistics API query filters for one series (API key names)."""

    freq: Required[str]
    sinceTimePeriod: Required[str]
    unit: str
    geo: str
    coicop18: str
    na_item: str
    s_adj: str
    sector: str
    indic_bt: str
    nace_r2: str
    age: str
    sex: str
    purchase: str
    bop_item: str
    partner: str
    stk_flow: str
    currency: str
    sector10: str
    sectpart: str


class EurostatApiDefaultParams(TypedDict):
    """Default Eurostat Statistics API query args."""

    format: str
    lang: str


class EurostatTickerParams(TypedDict):
    """Resolved request ready for the Statistics API."""

    dataset: str
    params: EurostatQueryParams


@dataclass(frozen=True)
class EurostatSeriesTemplate:
    """One Eurostat series keyed by our configured series ID (seed ticker).

    Frozen dataclass: needs ``EurostatSeriesTemplate(...)``.
    """

    series_id: str
    dataset: str
    params: EurostatQueryParams


EUROSTAT_STATISTICS_API_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
)
EUROSTAT_API_DEFAULT_PARAMS: EurostatApiDefaultParams = {
    "format": "JSON",
    "lang": "en",
}
# Eurostat ``geo`` for our ``EU`` location (euro area);
# other locations use their code as-is.
EUROSTAT_GEO_FOR_EU_LOCATION = "EA"

EUROSTAT_SERIES_TEMPLATES: list[EurostatSeriesTemplate] = [
    # HICP ECOICOP v2 monthly index 2025=100 (EU seed → geo EA; DE/ES/IT use location).
    EurostatSeriesTemplate(
        series_id="prc_hicp_minr",
        dataset="prc_hicp_minr",
        params={
            "freq": "M",
            "sinceTimePeriod": "2015-01",
            "unit": "I25",
            "coicop18": "TOTAL",
        },
    ),
    # Real GDP, chain-linked volumes 2020, million euro, SCA.
    EurostatSeriesTemplate(
        series_id="namq_10_gdp",
        dataset="namq_10_gdp",
        params={
            "freq": "Q",
            "sinceTimePeriod": "2010-Q1",
            "unit": "CLV20_MEUR",
            "na_item": "B1GQ",
            "s_adj": "SCA",
        },
    ),
    # General government consolidated gross debt, % of GDP.
    EurostatSeriesTemplate(
        series_id="gov_10q_ggdebt_pct",
        dataset="gov_10q_ggdebt",
        params={
            "freq": "Q",
            "sinceTimePeriod": "2010-Q1",
            "unit": "PC_GDP",
            "na_item": "GD",
            "sector": "S13",
        },
    ),
    # General government consolidated gross debt, million euro.
    EurostatSeriesTemplate(
        series_id="gov_10q_ggdebt_mio",
        dataset="gov_10q_ggdebt",
        params={
            "freq": "Q",
            "sinceTimePeriod": "2010-Q1",
            "unit": "MIO_EUR",
            "na_item": "GD",
            "sector": "S13",
        },
    ),
    # Industrial production volume index (2021=100), SCA.
    EurostatSeriesTemplate(
        series_id="sts_inpr_m",
        dataset="sts_inpr_m",
        params={
            "freq": "M",
            "sinceTimePeriod": "2015-01",
            "unit": "I21",
            "indic_bt": "PRD",
            "nace_r2": "B-D",
            "s_adj": "SCA",
        },
    ),
    # Retail trade volume of sales index (2021=100), SCA.
    EurostatSeriesTemplate(
        series_id="sts_trtu_m",
        dataset="sts_trtu_m",
        params={
            "freq": "M",
            "sinceTimePeriod": "2015-01",
            "unit": "I21",
            "indic_bt": "VOL_SLS",
            "nace_r2": "G47",
            "s_adj": "SCA",
        },
    ),
    # Unemployment rate, % of active population, SA.
    EurostatSeriesTemplate(
        series_id="une_rt_m",
        dataset="une_rt_m",
        params={
            "freq": "M",
            "sinceTimePeriod": "2015-01",
            "unit": "PC_ACT",
            "s_adj": "SA",
            "age": "TOTAL",
            "sex": "T",
        },
    ),
    # House price index, 2015=100, quarterly.
    EurostatSeriesTemplate(
        series_id="prc_hpi_q",
        dataset="prc_hpi_q",
        params={
            "freq": "Q",
            "sinceTimePeriod": "2010-Q1",
            "unit": "I15_Q",
            "purchase": "TOTAL",
        },
    ),
    # Goods trade balance (BoP), million euro.
    EurostatSeriesTemplate(
        series_id="bop_c6_m",
        dataset="bop_c6_m",
        params={
            "freq": "M",
            "sinceTimePeriod": "2015-01",
            "bop_item": "G",
            "partner": "WRL_REST",
            "stk_flow": "BAL",
            "currency": "MIO_EUR",
            "sector10": "S1",
            "sectpart": "S1",
        },
    ),
    # Maastricht B9 deficit/surplus % of GDP — annual.
    EurostatSeriesTemplate(
        series_id="tec00127_pct",
        dataset="tec00127",
        params={
            "freq": "A",
            "sinceTimePeriod": "2010",
            "unit": "PC_GDP",
            "sector": "S13",
            "na_item": "B9",
        },
    ),
    # Maastricht B9 deficit/surplus million euro — annual.
    EurostatSeriesTemplate(
        series_id="tec00127_mio",
        dataset="tec00127",
        params={
            "freq": "A",
            "sinceTimePeriod": "2010",
            "unit": "MIO_EUR",
            "sector": "S13",
            "na_item": "B9",
        },
    ),
]

# Eurostat publication schedule API URL.
EUROSTAT_PUBLICATION_SCHEDULE_URL = (
    "https://ec.europa.eu/eurostat/o/calendars/eventsJson"
)
# FullCalendar feed is range-bounded; ~13 months covers monthly euro-indicators.
EUROSTAT_PUBLICATION_LOOKAHEAD_DAYS = 400

# ---------------------------------------------------------------------------
# FRED (Federal Reserve of St. Louis)
# ---------------------------------------------------------------------------
"""FRED observations endpoint and release-dates calendar for publication schedules."""

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_OBSERVATION_START = "2010-01-01"

# FRED release calendar API URL.
FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"
# Seeded indicator ``technical_name`` → FRED release id (from ``fred/series/release``).
FRED_RELEASE_ID_BY_TECHNICAL_NAME: dict[str, int] = {
    "Gross Domestic Product": 53,
    "Consumer Price Index": 10,
    "Advance Monthly Sales for Retail and Food Services": 9,
    "G.17 Industrial Production and Capacity Utilization": 13,
    "Employment Situation": 50,
    "House Price Index": 171,
    "Surveys of Consumers": 91,
    # GFDEBTN — FRED often has no *future* dates for this release.
    "Federal Debt": 80,
    # FYFSD — federal surplus/deficit (fiscal year)
    "Fiscal Year Budget Data": 81,
    # GFDEGDQ188S / FYFSDFYGDP
    "Debt to Gross Domestic Product Ratios": 263,
}


# ---------------------------------------------------------------------------
# Statistics of Japan (e-Stat Dashboard)
# ---------------------------------------------------------------------------
"""e-Stat Statistics Dashboard API (no appId). Ticker = 19-digit IndicatorCode."""


class StatOfJpDefaultParams(TypedDict):
    """Default e-Stat Dashboard getData query args (API key names)."""

    Lang: str
    RegionCode: str
    TimeFrom: str


class StatOfJpSeriesParams(TypedDict):
    """e-Stat cycle / seasonal-adjustment filters (API key names)."""

    Cycle: str
    IsSeasonalAdjustment: str


class StatOfJpSeriesConfig(TypedDict):
    """Configured series mapped to an e-Stat IndicatorCode + filters."""

    ticker: str
    name: str
    indicator_code: str
    params: StatOfJpSeriesParams


STAT_OF_JP_DATA_URL = "https://dashboard.e-stat.go.jp/api/1.0/Json/getData"
STAT_OF_JP_DEFAULT_PARAMS: StatOfJpDefaultParams = {
    "Lang": "EN",
    "RegionCode": "00000",
    "TimeFrom": "20100100",
}
STAT_OF_JP_SERIES_BY_TICKER: dict[str, StatOfJpSeriesConfig] = {
    "0703010601010090000": {
        "ticker": "0703010601010090000",
        "name": "Japan CPI",
        "indicator_code": "0703010601010090000",
        "params": {"Cycle": "1", "IsSeasonalAdjustment": "1"},
    },
    "0301010000020020010": {
        "ticker": "0301010000020020010",
        "name": "Japan Unemployment Rate",
        "indicator_code": "0301010000020020010",
        "params": {"Cycle": "1", "IsSeasonalAdjustment": "2"},
    },
    "0502070301000090010": {
        "ticker": "0502070301000090010",
        "name": "Japan Industrial Production",
        "indicator_code": "0502070301000090010",
        "params": {"Cycle": "1", "IsSeasonalAdjustment": "2"},
    },
    "0601010201010010000": {
        "ticker": "0601010201010010000",
        "name": "Japan Retail Sales",
        "indicator_code": "0601010201010010000",
        "params": {"Cycle": "1", "IsSeasonalAdjustment": "1"},
    },
}


# ---------------------------------------------------------------------------
# Japan Cabinet Office (ESRI / SNA)
# ---------------------------------------------------------------------------
"""Cabinet Office quarterly SNA CSVs, SDDS Plus debt Excel, and annual table 18."""

JP_CAO_YEAR_ARCHIVE_URL = (
    "https://www.esri.cao.go.jp/en/sna/data/sokuhou/files/{year}/toukei_{year}.html"
)
JP_CAO_SITE_ORIGIN = "https://www.esri.cao.go.jp"
JP_CAO_SDDS_PLUS_PAGE_URL = (
    "https://www.esri.cao.go.jp/en/sna/sddsplus/sddsplus_top.html"
)
JP_CAO_ANNUAL_ACCOUNTS_TOP_URL = (
    "https://www.esri.cao.go.jp/en/sna/kakuhou/kakuhou_top.html"
)
# Filename prefix of the real SA expenditure CSV on the quarterly-estimates menu
# (e.g. ``gaku-jk`` matches ``gaku-jk2622.csv``). Columns are 0-based.
JP_CAO_REAL_SA_CSV_FILENAME_PREFIX = "gaku-jk"
JP_CAO_REAL_SA_COLUMN_BY_TICKER: dict[str, int] = {
    "gaku-jk": 1,  # GDP (expenditure approach)
    "gaku-jk-hh": 3,  # Consumption of Households
    "gaku-jk-gov": 8,  # Government Consumption
    "gaku-jk-gfcf": 27,  # Gross Fixed Capital Formation
    "gaku-jk-nx": 11,  # Net Exports (goods & services)
    "gaku-jk-ex": 12,  # Exports
    "gaku-jk-im": 13,  # Imports
}

# Filename prefix of the nominal SA GDP CSV on the quarterly-estimates menu
# (annualized levels; used as debt / % GDP denominator).
JP_CAO_NOMINAL_SA_CSV_FILENAME_PREFIX = "gaku-mk"
JP_CAO_DEBT_OUTSTANDING_TICKER = "ggd_total"
JP_CAO_DEBT_PCT_GDP_TICKER = "ggd_pct_gdp"
# Annual SNA table 18 — general government net lending (+) / net borrowing (−).
JP_CAO_DEFICIT_OUTSTANDING_TICKER = "net_lending_gg_cy"
JP_CAO_DEFICIT_PCT_GDP_TICKER = "net_lending_gg_cy_pct_gdp"
JP_CAO_NET_LENDING_AMOUNT_SHEET = "C.Y(1)Amount"
JP_CAO_NET_LENDING_PCT_SHEET = "C.Y(2)% of GDP"
JP_CAO_NET_LENDING_GENERAL_GOVERNMENT_LABEL = "(3) General government"
# End-of-quarter month (3/6/9/12) → quarter-start month for debt outstanding dates.
JP_CAO_GGD_QUARTER_START_MONTH_BY_END_MONTH: dict[int, int] = {
    3: 1,
    6: 4,
    9: 7,
    12: 10,
}


# ---------------------------------------------------------------------------
# MLIT — Residential Property Price Index
# ---------------------------------------------------------------------------
"""MLIT nationwide seasonally adjusted Residential Property Price Index Excel."""

MLIT_RPPI_PAGE_URL = (
    "https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html"
)
MLIT_SITE_ORIGIN = "https://www.mlit.go.jp"
MLIT_RPPI_TICKER = "residential_property_sa"
MLIT_RPPI_SHEET = "全国Japan季節調整"

# ---------------------------------------------------------------------------
# Bank of Japan — Tankan
# ---------------------------------------------------------------------------
"""BoJ Tankan summary ZIP: TABLE1 current-survey Actual columns by size × sector."""


class BojTankanSeries(NamedTuple):
    """Configured Tankan series mapped to TABLE1 sector × size."""

    ticker: str
    name: str
    sector_label: str
    size: str


# Latest ``tkaYYMM.zip`` is linked from the Tankan English index (not gaiyo/index).
BOJ_TANKAN_INDEX_URL = "https://www.boj.or.jp/en/statistics/tk/index.htm"
BOJ_SITE_ORIGIN = "https://www.boj.or.jp"
BOJ_TANKAN_CURRENT_ACTUAL_COLUMN_BY_SIZE: dict[str, int] = {
    "large": 4,
    "medium": 10,
    "small": 16,
}
BOJ_TANKAN_SERIES_BY_TICKER: dict[str, BojTankanSeries] = {
    "business_conditions_large_mfg": BojTankanSeries(
        ticker="business_conditions_large_mfg",
        name="Japan Tankan Large Enterprises Manufacturing DI",
        sector_label="Manufacturing",
        size="large",
    ),
    "business_conditions_medium_mfg": BojTankanSeries(
        ticker="business_conditions_medium_mfg",
        name="Japan Tankan Medium-sized Enterprises Manufacturing DI",
        sector_label="Manufacturing",
        size="medium",
    ),
    "business_conditions_small_mfg": BojTankanSeries(
        ticker="business_conditions_small_mfg",
        name="Japan Tankan Small Enterprises Manufacturing DI",
        sector_label="Manufacturing",
        size="small",
    ),
    "business_conditions_large_nonmfg": BojTankanSeries(
        ticker="business_conditions_large_nonmfg",
        name="Japan Tankan Large Enterprises Nonmanufacturing DI",
        sector_label="Nonmanufacturing",
        size="large",
    ),
    "business_conditions_medium_nonmfg": BojTankanSeries(
        ticker="business_conditions_medium_nonmfg",
        name="Japan Tankan Medium-sized Enterprises Nonmanufacturing DI",
        sector_label="Nonmanufacturing",
        size="medium",
    ),
    "business_conditions_small_nonmfg": BojTankanSeries(
        ticker="business_conditions_small_nonmfg",
        name="Japan Tankan Small Enterprises Nonmanufacturing DI",
        sector_label="Nonmanufacturing",
        size="small",
    ),
}
