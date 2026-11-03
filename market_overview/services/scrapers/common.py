"""Shared result types and helpers for market price scrapers."""

from typing import TypedDict


class ScrapingResult(TypedDict):
    """Scraped market price or miss comment from one price source."""

    price: float | None
    comment: str | None


class YieldTermRate(TypedDict):
    """One term on a scraped yield curve."""

    term: str
    rate: float


class YieldCurveScrapResult(TypedDict):
    """Scraped yield curve or an error message."""

    rates: list[YieldTermRate]
    error: str | None


def get_yield_curve_rate(curve: YieldCurveScrapResult, term: str) -> float | None:
    """Return the rate for 'term' on 'curve', or None if missing."""
    for point in curve["rates"]:
        if point["term"] == term:
            return point["rate"]
    return None


def get_yield_from_curve_by_ticker(
    ticker: str,
    ticker_to_term: dict[str, str],
    curve: YieldCurveScrapResult,
) -> ScrapingResult:
    """Map 'ticker' through 'ticker_to_term' onto a scraped yield curve."""
    # Usage of dict: keys are source ticker codes; values are curve term labels.
    term = ticker_to_term.get(ticker)
    if term is None:
        return ScrapingResult(price=None, comment="Ticker not found in mapping.")
    if curve["error"]:
        return ScrapingResult(price=None, comment=curve["error"])
    if not curve["rates"]:
        return ScrapingResult(price=None, comment="Yield curve not found.")
    return ScrapingResult(price=get_yield_curve_rate(curve, term), comment="")
