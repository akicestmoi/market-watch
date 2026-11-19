"""Scrape ISM Manufacturing and Services PMI composite indexes."""

import logging
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    ISM_2026_RELEASE_DAY_BY_MONTH,
    ISM_EASTERN_RELEASE_HOUR,
    ISM_EASTERN_RELEASE_MINUTE,
    ISM_FORECASTS_NAPM_URL,
    ISM_MANUFACTURING_PMI_TICKER,
    ISM_PRNEWSWIRE_LIST_URL,
    ISM_PRNEWSWIRE_MAX_PAGES,
    ISM_PRNEWSWIRE_PAGE_SIZE,
    ISM_SERVICES_PMI_TICKER,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (Manufacturing and Services PMI)
# __________________________________________________________

_MONTH_NUMBER_BY_NAME: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_PRNEWSWIRE_TITLE_PATTERN = re.compile(
    r"(Manufacturing|Services)\s+PMI\D{0,10}at\s+(\d+(?:\.\d+)?)%\s*;\s*"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})",
    re.IGNORECASE,
)


def _parse_ism_prnewswire_listing_html(
    page_html: str,
) -> list[tuple[str, date, float]]:
    """Parse Manufacturing/Services PMI releases from a PR Newswire listing page."""
    soup = BeautifulSoup(page_html, "html.parser")
    parsed_releases: list[tuple[str, date, float]] = []
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text().split())
        match = _PRNEWSWIRE_TITLE_PATTERN.search(title)
        if match is None:
            continue
        kind = match.group(1).lower()
        data_value = float(match.group(2))
        month = _MONTH_NUMBER_BY_NAME[match.group(3).lower()]
        year = int(match.group(4))
        parsed_releases.append((kind, date(year, month, 1), data_value))
    return parsed_releases


def _scrape_ism_prnewswire_releases() -> list[tuple[str, date, float]]:
    """Walk ISM PR Newswire listing pages for Manufacturing/Services PMI titles."""
    scraped_releases: list[tuple[str, date, float]] = []
    for page_number in range(1, ISM_PRNEWSWIRE_MAX_PAGES + 1):
        response = requests.get(
            ISM_PRNEWSWIRE_LIST_URL,
            params={"page": page_number, "pagesize": ISM_PRNEWSWIRE_PAGE_SIZE},
            timeout=60,
        )
        if response.status_code >= 400:
            logger.warning(
                f"Error scraping ISM PR Newswire page {page_number}: "
                f"{response.status_code}"
            )
            break
        page_releases = _parse_ism_prnewswire_listing_html(response.text)
        if not page_releases:
            break
        scraped_releases.extend(page_releases)
    return scraped_releases


def _parse_forecasts_napm_html(page_html: str) -> list[ScrapingResult]:
    """Parse legacy ISM Manufacturing PMI levels embedded on forecasts.org."""
    economic_data: list[ScrapingResult] = []
    for year_month, value_text in re.findall(
        r"\['(\d{4}-\d{2}-\d{2})',\s*([0-9.]+)\]",
        page_html,
    ):
        period = date.fromisoformat(year_month)
        economic_data.append(
            ScrapingResult(
                period=period.replace(day=1),
                data_value=float(value_text),
                comment="",
            )
        )
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _scrape_forecasts_manufacturing_pmi() -> list[ScrapingResult]:
    """Fetch legacy Manufacturing PMI history from forecasts.org NAPM page."""
    response = requests.get(
        ISM_FORECASTS_NAPM_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping forecasts.org NAPM page: {response.status_code}"
        )
        return []
    return _parse_forecasts_napm_html(response.text)


def _merge_ism_manufacturing_series(
    prnewswire_releases: list[tuple[str, date, float]],
    forecasts_series: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Merge PR Newswire Manufacturing releases over forecasts.org history."""
    # Usage of dict: period keys are dynamic monthly observation dates.
    value_by_period: dict[date, float] = {}
    for scraping_result in forecasts_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None:
            continue
        value_by_period[period] = data_value
    for kind, period, data_value in prnewswire_releases:
        if kind != "manufacturing":
            continue
        # PR Newswire is the primary recent source and overwrites legacy observations.
        value_by_period[period] = data_value
    economic_data = [
        ScrapingResult(period=period, data_value=data_value, comment="")
        for period, data_value in value_by_period.items()
    ]
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


def _build_ism_services_series(
    prnewswire_releases: list[tuple[str, date, float]],
) -> list[ScrapingResult]:
    """Build Services PMI levels from PR Newswire titles only."""
    # Usage of dict: period keys are dynamic monthly observation dates.
    value_by_period: dict[date, float] = {}
    for kind, period, data_value in prnewswire_releases:
        if kind != "services":
            continue
        value_by_period[period] = data_value
    economic_data = [
        ScrapingResult(period=period, data_value=data_value, comment="")
        for period, data_value in value_by_period.items()
    ]
    economic_data.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return economic_data


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_data_from_ism(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.MONTHLY,
) -> list[ScrapingResult]:
    """Get an ISM composite PMI series.

    Supported tickers: 'ism_manufacturing_pmi' (PR Newswire + forecasts.org
    NAPM history) and 'ism_services_pmi' (PR Newswire titles).
    """
    if ticker not in {
        ISM_MANUFACTURING_PMI_TICKER,
        ISM_SERVICES_PMI_TICKER,
    }:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported ISM ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.MONTHLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported frequency for ISM scrape: {frequency}",
            )
        ]

    prnewswire_releases = _scrape_ism_prnewswire_releases()
    if ticker == ISM_MANUFACTURING_PMI_TICKER:
        economic_data = _merge_ism_manufacturing_series(
            prnewswire_releases,
            _scrape_forecasts_manufacturing_pmi(),
        )
    else:
        economic_data = _build_ism_services_series(prnewswire_releases)

    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"No ISM values found for ticker {ticker}.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (ISM releases)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_ism(name: str) -> list[datetime]:
    """Get upcoming ISM PMI dates from the official 2026 release calendar.

    Manufacturing is the first business-day slot; Services the third. Clock is
    10:00 America/New_York per ISM's Report On Business calendar. Live HTML is
    often blocked from this host, so we keep the published 2026 day table in
    config rather than inventing later years.
    """
    is_services = "Services" in name
    publication_datetimes: list[datetime] = []
    for month, (manufacturing_day, services_day) in sorted(
        ISM_2026_RELEASE_DAY_BY_MONTH.items()
    ):
        day = services_day if is_services else manufacturing_day
        publication_datetimes.append(
            convert_local_wall_time_to_utc(
                2026,
                month,
                day,
                ISM_EASTERN_RELEASE_HOUR,
                ISM_EASTERN_RELEASE_MINUTE,
                source_timezone="America/New_York",
            )
        )
    return filter_upcoming_publication_dates(publication_datetimes)
