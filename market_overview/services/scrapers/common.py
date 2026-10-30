"""Shared result types and helpers for market price scrapers."""

from typing import TypedDict


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

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
    """Return the rate for ``term`` on ``curve``, or None if missing."""
    for point in curve["rates"]:
        if point["term"] == term:
            return point["rate"]
    return None
