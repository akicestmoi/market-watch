"""Shared types and helpers for economic data scrapers."""

from datetime import date, datetime
from typing import TypedDict

from django.utils import timezone

from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)


class ScrapingResult(TypedDict):
    """Scraped economic indicator value for one period, or add a miss comment."""

    period: date | None
    data_value: float | None
    comment: str


class ScrapedIndustryProfitability(TypedDict):
    """One industry-year profitability figure from a source scrape."""

    industry_code: str
    industry_label: str
    period: date
    turnover: float | None
    operating_profit: float | None
    gva: float | None


class ScrapedTradeRanking(TypedDict):
    """One Top-N product or partner ranking from a customs scrape."""

    period: date
    flow: str
    breakdown: str
    rank: int
    item_code: str
    item_label: str
    trade_value: float


class ScrapedTradeProductPartnerRanking(TypedDict):
    """One product×partner Top-N cell from a customs scrape."""

    period: date
    flow: str
    product_code: str
    product_label: str
    partner_code: str
    partner_label: str
    rank: int
    trade_value: float


class TradeProductCodesByPeriodFlow(TypedDict):
    """Product codes for one trade year (period date) and import/export flow."""

    period: date
    flow: str
    product_codes: list[str]


def filter_upcoming_publication_dates(
    publication_datetimes: list[datetime],
    *,
    as_of: datetime | None = None,
    limit: int = 2,
) -> list[datetime]:
    """Keep upcoming publication datetimes (at most 'limit').

    At most two are returned by default: schedule update maps [0]/[1] onto
    current/next after rolling the just-released slot into previous; past dates
    must not be fed again.
    """
    reference_datetime = as_of if as_of is not None else timezone.now()
    upcoming_publication_dates = [
        publication_datetime
        for publication_datetime in publication_datetimes
        if publication_datetime >= reference_datetime
    ]
    # Default limit 2 keeps current and next; past dates must not be fed again.
    return upcoming_publication_dates[:limit]


def filter_scraping_results_by_target_period(
    economic_data: list[ScrapingResult],
    target_period: str | None,
    frequency: EconomicPublicationFrequencyChoices,
) -> list[ScrapingResult]:
    """Filter scraped values to a single target period label when requested."""
    if not target_period:
        return economic_data
    for scraping_result in economic_data:
        period = scraping_result["period"]
        if period is None:
            continue
        if frequency == EconomicPublicationFrequencyChoices.MONTHLY:
            if period.strftime("%Y-%m") == target_period:
                return [scraping_result]
        elif frequency == EconomicPublicationFrequencyChoices.QUARTERLY:
            quarter = (period.month - 1) // 3 + 1
            if target_period in {
                period.strftime("%Y-%m"),
                f"{period.year}-Q{quarter}",
                f"{period.year}-T{quarter}",
            }:
                return [scraping_result]
        elif frequency == EconomicPublicationFrequencyChoices.ANNUAL:
            if period.strftime("%Y") == target_period:
                return [scraping_result]
    return [
        ScrapingResult(period=None, data_value=None, comment="Target period not found.")
    ]


def deflate_scraping_results_by_period(
    nominal_series: list[ScrapingResult],
    deflator_series: list[ScrapingResult],
    *,
    deflator_is_index_base_100: bool = False,
) -> list[ScrapingResult]:
    """Turn nominal levels into real levels via a matching-period price deflator.

    When 'deflator_is_index_base_100' is true, uses 'nominal / (deflator / 100)'.
    Otherwise the deflator is treated as a raw price ratio (e.g. current / volume).
    """
    # Usage of dict: keys are observation periods; values are deflator levels.
    deflator_by_period: dict[date, float] = {}
    for scraping_result in deflator_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None or data_value == 0:
            continue
        deflator_by_period[period] = data_value

    deflated_series: list[ScrapingResult] = []
    for scraping_result in nominal_series:
        period = scraping_result["period"]
        nominal_value = scraping_result["data_value"]
        if period is None or nominal_value is None:
            continue
        deflator_value = deflator_by_period.get(period)
        if deflator_value is None:
            continue
        price_ratio = (
            deflator_value / 100.0 if deflator_is_index_base_100 else deflator_value
        )
        if price_ratio == 0:
            continue
        deflated_series.append(
            ScrapingResult(
                period=period,
                data_value=nominal_value / price_ratio,
                comment="",
            )
        )
    deflated_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return deflated_series


def sum_scraping_results_by_period(
    series_list: list[list[ScrapingResult]],
) -> list[ScrapingResult]:
    """Sum series that share the same period (missing series count as 0)."""
    # Usage of dict: keys are observation periods; values accumulate component levels.
    totals_by_period: dict[date, float] = {}
    for series in series_list:
        for scraping_result in series:
            period = scraping_result["period"]
            data_value = scraping_result["data_value"]
            if period is None or data_value is None:
                continue
            totals_by_period[period] = totals_by_period.get(period, 0.0) + data_value
    summed_series = [
        ScrapingResult(period=period, data_value=total, comment="")
        for period, total in totals_by_period.items()
    ]
    summed_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return summed_series


def subtract_scraping_results_by_period(
    left_series: list[ScrapingResult],
    right_series: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Subtract right from left on shared periods (e.g. exports − imports)."""
    # Usage of dict: keys are observation periods; values are right-hand levels.
    right_by_period: dict[date, float] = {}
    for scraping_result in right_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None:
            continue
        right_by_period[period] = data_value
    difference_series: list[ScrapingResult] = []
    for scraping_result in left_series:
        period = scraping_result["period"]
        left_value = scraping_result["data_value"]
        if period is None or left_value is None:
            continue
        right_value = right_by_period.get(period)
        if right_value is None:
            continue
        difference_series.append(
            ScrapingResult(
                period=period,
                data_value=left_value - right_value,
                comment="",
            )
        )
    difference_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return difference_series


def calculate_ratio_scraping_results_as_percent(
    numerator_series: list[ScrapingResult],
    denominator_series: list[ScrapingResult],
    *,
    denominator_scale: float = 1.0,
) -> list[ScrapingResult]:
    """Build '100 * numerator / (denominator * denominator_scale)' on shared periods.

    Use 'denominator_scale=4' when a quarterly flow must be annualised before the
    ratio (e.g. debt stock / annual disposable income).
    """
    # Usage of dict: keys are observation periods; values are denominator levels.
    denominator_by_period: dict[date, float] = {}
    for scraping_result in denominator_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None:
            continue
        denominator_by_period[period] = data_value

    ratio_series: list[ScrapingResult] = []
    for scraping_result in numerator_series:
        period = scraping_result["period"]
        numerator_value = scraping_result["data_value"]
        if period is None or numerator_value is None:
            continue
        denominator_value = denominator_by_period.get(period)
        if denominator_value is None:
            continue
        scaled_denominator = denominator_value * denominator_scale
        if scaled_denominator == 0:
            continue
        ratio_series.append(
            ScrapingResult(
                period=period,
                data_value=100.0 * numerator_value / scaled_denominator,
                comment="",
            )
        )
    ratio_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return ratio_series


def divide_scraping_results_by_period(
    numerator_series: list[ScrapingResult],
    denominator_series: list[ScrapingResult],
) -> list[ScrapingResult]:
    """Divide numerator by denominator on shared periods (raw ratio, not percent)."""
    # Usage of dict: keys are observation periods; values are denominator levels.
    denominator_by_period: dict[date, float] = {}
    for scraping_result in denominator_series:
        period = scraping_result["period"]
        data_value = scraping_result["data_value"]
        if period is None or data_value is None:
            continue
        denominator_by_period[period] = data_value

    ratio_series: list[ScrapingResult] = []
    for scraping_result in numerator_series:
        period = scraping_result["period"]
        numerator_value = scraping_result["data_value"]
        if period is None or numerator_value is None:
            continue
        denominator_value = denominator_by_period.get(period)
        if denominator_value is None or denominator_value == 0:
            continue
        ratio_series.append(
            ScrapingResult(
                period=period,
                data_value=numerator_value / denominator_value,
                comment="",
            )
        )
    ratio_series.sort(
        key=lambda scraping_result: scraping_result["period"] or date.min,
        reverse=True,
    )
    return ratio_series


def calculate_equal_group_gini(group_means: list[float]) -> float:
    """Return the discrete equal-group Gini coefficient from group means (0–1).

    For n equal-sized groups with means m_1 … m_n (ordered poorest → richest):
    G = 2 Σ i m_i / (n Σ m_i) − (n + 1) / n.
    Within-group inequality is ignored, so the estimate is slightly low.
    """
    if not group_means:
        raise ValueError("group_means must not be empty.")
    group_count = len(group_means)
    total_mean = sum(group_means)
    if total_mean == 0:
        raise ValueError("group_means sum must be non-zero.")
    weighted_rank_sum = sum(
        (group_index + 1) * group_mean
        for group_index, group_mean in enumerate(group_means)
    )
    return (2.0 * weighted_rank_sum) / (group_count * total_mean) - (
        group_count + 1
    ) / group_count


def calculate_palma_from_decile_means(decile_means: list[float]) -> float:
    """Return Palma = top-decile mean / sum of bottom-four decile means."""
    if len(decile_means) != 10:
        raise ValueError("decile_means must have exactly 10 equal-decile means.")
    # Palma's denominator is the sum of the four lowest (poorest) decile means.
    bottom_forty_total = sum(decile_means[:4])
    if bottom_forty_total == 0:
        raise ValueError("Bottom-four decile means must sum to a non-zero value.")
    # Index 9 is the richest equal-sized decile mean.
    return decile_means[9] / bottom_forty_total
