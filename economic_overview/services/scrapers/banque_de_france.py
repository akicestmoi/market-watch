"""Scrape Banque de France Webstat economic series."""

import logging
import re
from datetime import date, datetime
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_HOUR,
    BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_MINUTE,
    BANQUE_DE_FRANCE_EMC_PUBLICATIONS_URL,
    BANQUE_DE_FRANCE_FRENCH_MONTH_NUMBER_BY_NAME,
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER,
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER,
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_REDEMPTIONS_TICKER,
    BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_DATASET,
    BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_TICKER,
    BANQUE_DE_FRANCE_MFG_NEW_ORDERS_TICKER,
    BANQUE_DE_FRANCE_SC1_DATASET,
    BANQUE_DE_FRANCE_WEBSTAT_CSV_URL,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
    subtract_scraping_results_by_period,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Banque de France Webstat series)
# __________________________________________________________

_BANQUE_DE_FRANCE_EMC_DATE_PATTERN = re.compile(
    r"(\d{1,2})\s+([A-Za-zàâäéèêëïîôùûüç]+)\s+(20\d{2})\s*-\s*Mensuel",
    flags=re.IGNORECASE,
)

_BANQUE_DE_FRANCE_SERIES_PATH_BY_TICKER: dict[str, str] = {
    BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_TICKER: (
        f"{BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_DATASET}/"
        f"{BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_TICKER}"
    ),
    BANQUE_DE_FRANCE_MFG_NEW_ORDERS_TICKER: (
        f"{BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_DATASET}/"
        f"{BANQUE_DE_FRANCE_MFG_NEW_ORDERS_TICKER}"
    ),
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER: (
        f"{BANQUE_DE_FRANCE_SC1_DATASET}/"
        f"{BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER}"
    ),
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER: (
        f"{BANQUE_DE_FRANCE_SC1_DATASET}/"
        f"{BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER}"
    ),
}

_BANQUE_DE_FRANCE_FREQUENCY_BY_TICKER: dict[
    str, EconomicPublicationFrequencyChoices
] = {
    BANQUE_DE_FRANCE_MFG_CAPACITY_UTILISATION_TICKER: (
        EconomicPublicationFrequencyChoices.MONTHLY
    ),
    BANQUE_DE_FRANCE_MFG_NEW_ORDERS_TICKER: (
        EconomicPublicationFrequencyChoices.MONTHLY
    ),
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER: (
        EconomicPublicationFrequencyChoices.QUARTERLY
    ),
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER: (
        EconomicPublicationFrequencyChoices.QUARTERLY
    ),
    BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_REDEMPTIONS_TICKER: (
        EconomicPublicationFrequencyChoices.QUARTERLY
    ),
}


def _parse_banque_de_france_decimal(
    raw_value: str | float | int | bool | None,
) -> float | None:
    """Parse French or English decimal strings from Webstat CSV cells."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return None
    text = str(raw_value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_banque_de_france_period(
    period_label: str | float | int | bool | None,
) -> date | None:
    """Parse Webstat 'time_period' labels to period start dates.

    Supports monthly ('YYYY-MM' / 'YYYY-MM-DD') and quarterly ('YYYY-Qn').
    """
    if period_label is None or (
        isinstance(period_label, float) and pd.isna(period_label)
    ):
        return None
    text = str(period_label).strip()
    quarterly_match = re.fullmatch(r"(\d{4})-Q([1-4])", text, flags=re.IGNORECASE)
    if quarterly_match:
        year = int(quarterly_match.group(1))
        quarter = int(quarterly_match.group(2))
        return date(year, (quarter - 1) * 3 + 1, 1)
    for date_format in ("%Y-%m-%d", "%Y-%m"):
        try:
            parsed = datetime.strptime(text, date_format).date()
        except ValueError:
            continue
        return date(parsed.year, parsed.month, 1)
    return None


def _parse_banque_de_france_webstat_csv(csv_text: str) -> list[ScrapingResult]:
    """Parse a Webstat catalog CSV into newest-first observations."""
    dataframe = pd.read_csv(StringIO(csv_text), sep=";")
    if "time_period" not in dataframe.columns or "obs_value" not in dataframe.columns:
        return []
    economic_data: list[ScrapingResult] = []
    for _, csv_row in dataframe.iterrows():
        period = _parse_banque_de_france_period(csv_row.get("time_period"))
        data_value = _parse_banque_de_france_decimal(csv_row.get("obs_value"))
        if period is None or data_value is None:
            continue
        economic_data.append(
            ScrapingResult(period=period, data_value=data_value, comment="")
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _get_banque_de_france_gg_debt_securities_redemptions_data(
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Derive principal repayments as gross minus net debt-security issuance."""
    gross_series = get_data_from_banque_de_france(
        BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_GROSS_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    net_series = get_data_from_banque_de_france(
        BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_NET_TICKER,
        target_period,
        EconomicPublicationFrequencyChoices.QUARTERLY,
    )
    redemptions_series = subtract_scraping_results_by_period(gross_series, net_series)
    if not redemptions_series:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Banque de France debt-security redemption values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        redemptions_series, target_period, frequency
    )


def _download_banque_de_france_webstat_series(
    ticker: str,
    series_path: str,
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Download and parse one Banque de France Webstat CSV series."""
    response = requests.get(
        f"{BANQUE_DE_FRANCE_WEBSTAT_CSV_URL}/{series_path}",
        timeout=90,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping Banque de France Webstat: {response.text[:500]}"
        )
        return [ScrapingResult(period=None, data_value=None, comment=response.text)]

    try:
        economic_data = _parse_banque_de_france_webstat_csv(response.text)
    except Exception as exc:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Error parsing Banque de France Webstat CSV: {exc}",
            )
        ]
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No Banque de France values for ticker={ticker}.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_banque_de_france(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get a Banque de France Webstat series by seed ticker.

    Supported tickers:
    - 'CONJ.M.N01.S.IN.000CZ.TUTSM000.10' manufacturing capacity utilisation (SA %)
    - 'CONJ.M.N01.S.IN.000CZ.CRTEM100.10' manufacturing new-orders opinion balance (SA)
    - 'SC1.Q.FR.1300.F33000.N.8.Z01.E.Z' general-government debt-security gross issuance
    - 'SC1.Q.FR.1300.F33000.N.4.Z01.E.Z' general-government debt-security net issuance
    - 'gg_debt_securities_redemptions' gross minus net (principal repayments)
    """
    expected_frequency = _BANQUE_DE_FRANCE_FREQUENCY_BY_TICKER.get(ticker)
    if expected_frequency is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Banque de France ticker: {ticker}",
            )
        ]
    if frequency != expected_frequency:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for Banque de France scrape: {frequency}",
            )
        ]

    if ticker == BANQUE_DE_FRANCE_GG_DEBT_SECURITIES_REDEMPTIONS_TICKER:
        return _get_banque_de_france_gg_debt_securities_redemptions_data(
            target_period, frequency
        )

    series_path = _BANQUE_DE_FRANCE_SERIES_PATH_BY_TICKER.get(ticker)
    if series_path is None:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Banque de France ticker: {ticker}",
            )
        ]

    return _download_banque_de_france_webstat_series(
        ticker, series_path, target_period, frequency
    )


# __________________________________________________________
# Publication dates (EMC manufacturing survey calendar)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_banque_de_france(name: str) -> list[datetime]:
    """Get upcoming EMC dates from the Banque de France publications list.

    Manufacturing survey technical names use the EMC card dates at 08:45
    Europe/Paris. General-government debt-security (SC1) series have no dated
    public calendar entry on the stats agenda, so those names return empty.
    """
    is_emc_survey = name in {
        "Monthly Business Survey in Industry",
        "Manufacturing new orders opinion balance",
    }
    if not is_emc_survey:
        logger.warning(
            "Banque de France publication schedule has no dated calendar for "
            f"technical_name={name}."
        )
        return []

    response = requests.get(
        BANQUE_DE_FRANCE_EMC_PUBLICATIONS_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping Banque de France EMC publications: {response.text}"
        )
        return []

    page_text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    publication_datetimes: list[datetime] = []
    for match in _BANQUE_DE_FRANCE_EMC_DATE_PATTERN.finditer(page_text):
        day = int(match.group(1))
        month_label = match.group(2).lower()
        year = int(match.group(3))
        month = BANQUE_DE_FRANCE_FRENCH_MONTH_NUMBER_BY_NAME.get(month_label)
        if month is None:
            continue
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                year,
                month,
                day,
                BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_HOUR,
                BANQUE_DE_FRANCE_EMC_PARIS_RELEASE_MINUTE,
                source_timezone="Europe/Paris",
            )
        )
    publication_datetimes = sorted(set(publication_datetimes))
    return filter_upcoming_publication_dates(publication_datetimes)
