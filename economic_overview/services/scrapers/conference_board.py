"""Scrape The Conference Board Measure of CEO Confidence from PR Newswire."""

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache

from core.services.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services.calendar import convert_local_wall_time_to_utc
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_HOUR,
    CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_MINUTE,
    CONFERENCE_BOARD_CEO_CONFIDENCE_PAGE_URL,
    CONFERENCE_BOARD_CEO_CONFIDENCE_TICKER,
    CONFERENCE_BOARD_PRNEWSWIRE_LIST_URL,
    CONFERENCE_BOARD_PRNEWSWIRE_MAX_PAGES,
    CONFERENCE_BOARD_PRNEWSWIRE_ORIGIN,
    CONFERENCE_BOARD_PRNEWSWIRE_PAGE_SIZE,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    filter_scraping_results_by_target_period,
    filter_upcoming_publication_dates,
)

logger = logging.getLogger(__name__)

# __________________________________________________________
# Values (CEO Confidence)
# __________________________________________________________

_CEO_RELEASE_HREF_MARKER = "/news-releases/"
_CEO_VALUE_PATTERN = re.compile(
    r"Measure of CEO Confidence.{0,160}?\bto\s+(\d{2})\s+in\s+Q([1-4])\s+(\d{4})",
    re.IGNORECASE | re.DOTALL,
)
_QUARTER_START_MONTH_BY_NUMBER: dict[int, int] = {
    1: 1,
    2: 4,
    3: 7,
    4: 10,
}
_NEXT_CEO_RELEASE_PATTERN = re.compile(
    r"next release is on\s+\w+,\s+(January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?",
    re.IGNORECASE,
)
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


def _parse_ceo_confidence_article_html(page_html: str) -> ScrapingResult | None:
    """Parse one CEO Confidence headline value from a PR Newswire article."""
    text = BeautifulSoup(page_html, "html.parser").get_text(" ", strip=True)
    match = _CEO_VALUE_PATTERN.search(text)
    if match is None:
        return None
    data_value = float(match.group(1))
    quarter = int(match.group(2))
    year = int(match.group(3))
    return ScrapingResult(
        period=date(year, _QUARTER_START_MONTH_BY_NUMBER[quarter], 1),
        data_value=data_value,
        comment="",
    )


def _list_ceo_confidence_article_urls(list_html: str) -> list[str]:
    """Collect CEO Confidence release URLs from a Conference Board listing page."""
    soup = BeautifulSoup(list_html, "html.parser")
    article_urls: list[str] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text().split())
        href = anchor["href"]
        if "CEO Confidence" not in title:
            continue
        if _CEO_RELEASE_HREF_MARKER not in href:
            continue
        article_url = (
            href
            if href.startswith("http")
            else urljoin(CONFERENCE_BOARD_PRNEWSWIRE_ORIGIN, href)
        )
        if article_url in seen_urls:
            continue
        seen_urls.add(article_url)
        article_urls.append(article_url)
    return article_urls


def _scrape_ceo_confidence_series() -> list[ScrapingResult]:
    """Walk Conference Board PR Newswire pages and parse CEO Confidence articles."""
    # Usage of dict: period keys are dynamic quarter-start observation dates.
    value_by_period: dict[date, float] = {}
    for page_number in range(1, CONFERENCE_BOARD_PRNEWSWIRE_MAX_PAGES + 1):
        list_response = requests.get(
            CONFERENCE_BOARD_PRNEWSWIRE_LIST_URL,
            params={
                "page": page_number,
                "pagesize": CONFERENCE_BOARD_PRNEWSWIRE_PAGE_SIZE,
            },
            timeout=60,
        )
        if list_response.status_code >= 400:
            logger.warning(
                "Error scraping Conference Board PR Newswire page "
                f"{page_number}: {list_response.status_code}"
            )
            break
        article_urls = _list_ceo_confidence_article_urls(list_response.text)
        if not article_urls and page_number > 1:
            break
        for article_url in article_urls:
            article_response = requests.get(
                article_url,
                timeout=60,
            )
            if article_response.status_code >= 400:
                continue
            scraping_result = _parse_ceo_confidence_article_html(article_response.text)
            if scraping_result is None:
                continue
            period = scraping_result["period"]
            data_value = scraping_result["data_value"]
            if period is None or data_value is None:
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
def get_data_from_conference_board(
    ticker: str,
    target_period: str | None = None,
    frequency: EconomicPublicationFrequencyChoices = EconomicPublicationFrequencyChoices.QUARTERLY,
) -> list[ScrapingResult]:
    """Get The Conference Board Measure of CEO Confidence.

    Supported ticker: 'ceo_confidence'. Values come from PR Newswire releases.
    """
    if ticker != CONFERENCE_BOARD_CEO_CONFIDENCE_TICKER:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=f"Unsupported Conference Board ticker: {ticker}",
            )
        ]
    if frequency != EconomicPublicationFrequencyChoices.QUARTERLY:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    f"Unsupported frequency for Conference Board scrape: {frequency}"
                ),
            )
        ]

    economic_data = _scrape_ceo_confidence_series()
    if not economic_data:
        return [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No Conference Board CEO Confidence values found.",
            )
        ]
    return filter_scraping_results_by_target_period(
        economic_data, target_period, frequency
    )


# __________________________________________________________
# Publication dates (CEO Confidence releases)
# __________________________________________________________


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_publication_dates_from_conference_board(_: str) -> list[datetime]:
    """Get the next CEO Confidence date from the Conference Board topic page.

    Clock is 06:00 America/New_York (matches PR Newswire embargo stamps). The
    page only advertises the next release, so we return at most one upcoming
    slot rather than inventing later quarters.
    """
    response = requests.get(
        CONFERENCE_BOARD_CEO_CONFIDENCE_PAGE_URL,
        timeout=60,
    )
    if response.status_code >= 400:
        logger.warning(
            f"Error scraping Conference Board CEO Confidence page: {response.text}"
        )
        return []

    page_text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    match = _NEXT_CEO_RELEASE_PATTERN.search(page_text)
    if match is None:
        logger.warning("No next CEO Confidence release date found on topic page.")
        return []

    month = _MONTH_NUMBER_BY_NAME[match.group(1).lower()]
    day = int(match.group(2))
    today = date.today()
    # Page omits the year; pick the next civil occurrence of that month/day.
    year = today.year
    if date(year, month, day) < today:
        year += 1
    publication_datetime = convert_local_wall_time_to_utc(
        year,
        month,
        day,
        CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_HOUR,
        CONFERENCE_BOARD_CEO_CONFIDENCE_EASTERN_RELEASE_MINUTE,
        source_timezone="America/New_York",
    )
    return filter_upcoming_publication_dates([publication_datetime])
