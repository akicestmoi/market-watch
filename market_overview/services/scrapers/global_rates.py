"""Scrape interest rates from GlobalRates."""

import re
from datetime import date, datetime

from bs4 import Tag
from cachetools.func import ttl_cache

from core.cache import CACHE_MAXSIZE, CACHE_TTL_SECONDS
from core.services import fetch_html, logger
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.config import GLOBAL_RATES_URL


def _parse_euribor_rate_from_table(
    table: Tag, target_date: date | None
) -> ScrapingResult:
    """Parse EURIBOR rate from table for a specific date."""
    if target_date is None:
        return ScrapingResult(
            price=None, comment="Target date is required for EURIBOR rates"
        )

    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue

        raw_date = cells[0].get_text(strip=True)
        raw_rate = cells[1].get_text(strip=True)

        try:
            parsed_date = datetime.strptime(raw_date, "%m-%d-%Y").date()
        except ValueError:
            logger.debug(f"Could not parse date format: {raw_date}")
            continue

        if parsed_date == target_date:
            rate_str = raw_rate.replace("%", "").replace(",", ".").strip()
            try:
                return ScrapingResult(price=float(rate_str), comment="")
            except ValueError:
                return ScrapingResult(
                    price=None,
                    comment=f"Could not parse Euribor rate: {raw_rate}",
                )
    return ScrapingResult(price=None, comment="Euribor rate not found.")


def _parse_central_bank_rate_from_table(table: Tag) -> ScrapingResult:
    """Parse central bank rate from table (first row, second column)."""
    tbody = table.find("tbody")
    if not isinstance(tbody, Tag):
        return ScrapingResult(price=None, comment="Table has no <tbody>")

    first_row = tbody.find("tr")
    if not isinstance(first_row, Tag):
        return ScrapingResult(price=None, comment="Table contains no rows")

    cells = first_row.find_all("td")
    if len(cells) < 2:
        return ScrapingResult(price=None, comment="Row has insufficient columns")

    rate_text = cells[1].get_text(strip=True)
    if not rate_text:
        return ScrapingResult(price=None, comment="Rate cell is empty")

    match = re.search(r"([-+]?\d+(?:\.\d+)?)", rate_text)
    if not match:
        return ScrapingResult(
            price=None, comment=f"Could not extract rate from: {rate_text}"
        )

    try:
        return ScrapingResult(price=float(match.group(1)), comment="")
    except ValueError:
        return ScrapingResult(
            price=None, comment=f"Could not convert rate to float: {match.group(1)}"
        )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_from_global_rates(target_date: date | None, ticker: str) -> ScrapingResult:
    """Scrap rates from GlobalRates.

    Source: https://www.global-rates.com/en/
    """
    soup = fetch_html(f"{GLOBAL_RATES_URL}/{ticker}")
    if not soup:
        return ScrapingResult(
            price=None, comment=f"Failed to fetch HTML from {GLOBAL_RATES_URL}"
        )

    table = soup.find("table")
    if not isinstance(table, Tag):
        return ScrapingResult(
            price=None, comment="Could not find interest rates table on page"
        )

    rate_type = ticker.split("/")[0] if "/" in ticker else ticker
    match rate_type:
        case "euribor":
            result = _parse_euribor_rate_from_table(table, target_date)
        case "central-banks":
            result = _parse_central_bank_rate_from_table(table)
        case _:
            result = ScrapingResult(
                price=None, comment=f"Unsupported rate type: {rate_type}"
            )
    return result
