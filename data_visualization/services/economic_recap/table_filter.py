"""Parse economic-recap region, as-of, and comparison toolbar filters."""

from calendar import monthrange
from datetime import date
from enum import Enum
from typing import NamedTuple

from core.services.calendar import get_local_today
from data_visualization.services.config import (
    ECONOMIC_RECAP_AS_OF_YEAR_START,
    ECONOMIC_RECAP_LOCATIONS,
    ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER,
)
from data_visualization.services.economic_recap.table_structure import (
    EconomicRecapCategoryGroup,
)
from economic_overview.models.common import EconomicDataLocationChoices


class EconomicRecapSelectedLocation(NamedTuple):
    """Selected recap region code and matching location enum."""

    selected_region: str
    selected_location: EconomicDataLocationChoices


def get_selected_location_for_economic_recap(
    region: str | None,
) -> EconomicRecapSelectedLocation:
    """Return the selected recap region code and location enum.

    Unknown or missing 'region' falls back to the first configured recap location.
    """
    region_codes = [location.value for location in ECONOMIC_RECAP_LOCATIONS]
    # First configured region is the default when the query omits or invents one.
    default_region = region_codes[0]
    selected_region = region if region in region_codes else default_region
    selected_location = EconomicDataLocationChoices(selected_region)
    return EconomicRecapSelectedLocation(
        selected_region=selected_region,
        selected_location=selected_location,
    )


def list_as_of_years_for_economic_recap(*, as_of: date | None = None) -> list[int]:
    """Return the fixed Year dropdown range, newest first (current year → 2010)."""
    reference_date = as_of if as_of is not None else get_local_today()
    return list(range(reference_date.year, ECONOMIC_RECAP_AS_OF_YEAR_START - 1, -1))


class EconomicRecapComparisonChoices(str, Enum):
    """Toolbar Comparison horizon for Previous (not a stored DB choice)."""

    LATEST = "Latest"
    YEAR = "Year"
    QUARTER = "Quarter"


def get_default_comparison_for_economic_recap(
    *,
    year: int | None,
    quarter: int | None,
    month: int | None,
) -> EconomicRecapComparisonChoices:
    """Return the Comparison default for the given As-of selection."""
    if year is None:
        return EconomicRecapComparisonChoices.LATEST
    if month is not None:
        return EconomicRecapComparisonChoices.LATEST
    if quarter is not None:
        return EconomicRecapComparisonChoices.QUARTER
    return EconomicRecapComparisonChoices.YEAR


def parse_economic_recap_comparison(
    comparison: str | None,
    *,
    year: int | None,
    quarter: int | None,
    month: int | None,
) -> EconomicRecapComparisonChoices:
    """Parse 'comparison' query param; fall back to the As-of default when invalid."""
    default_comparison = get_default_comparison_for_economic_recap(
        year=year, quarter=quarter, month=month
    )
    if comparison in {
        EconomicRecapComparisonChoices.LATEST.value,
        EconomicRecapComparisonChoices.YEAR.value,
        EconomicRecapComparisonChoices.QUARTER.value,
    }:
        parsed = EconomicRecapComparisonChoices(comparison)
        # Year-only As-of cannot use Comparison=Quarter (non-calendar shift).
        if (
            parsed is EconomicRecapComparisonChoices.QUARTER
            and year is not None
            and quarter is None
            and month is None
        ):
            return EconomicRecapComparisonChoices.YEAR
        return parsed
    return default_comparison


class EconomicRecapAsOfSelection(NamedTuple):
    """Parsed as-of toolbar selection for the economic recap page."""

    year: int | None
    quarter: int | None
    month: int | None
    end_date: date | None


def build_economic_recap_as_of_query_string(
    selection: EconomicRecapAsOfSelection,
    *,
    comparison: EconomicRecapComparisonChoices | None = None,
) -> str:
    """Build the as-of (+ optional comparison) query string; empty when Latest."""
    query_parts: list[str] = []
    if selection.year is not None:
        query_parts.append(f"as_of_year={selection.year}")
        if selection.quarter is not None:
            query_parts.append(f"as_of_quarter={selection.quarter}")
        elif selection.month is not None:
            query_parts.append(f"as_of_month={selection.month}")
    if comparison is not None:
        default_comparison = get_default_comparison_for_economic_recap(
            year=selection.year,
            quarter=selection.quarter,
            month=selection.month,
        )
        if comparison is not default_comparison:
            query_parts.append(f"comparison={comparison.value}")
    return "&".join(query_parts)


def _get_month_end_date(year: int, month: int) -> date:
    """Return the last calendar day of 'year'-'month'."""
    return date(year, month, monthrange(year, month)[1])


def _list_period_dates_from_recap_data(
    economic_data: list[EconomicRecapCategoryGroup],
) -> list[date]:
    """Collect every 'period_date' in the recap payload for availability checks."""
    period_dates: list[date] = []
    for category_group in economic_data:
        for subcategory_group in category_group["subcategories"]:
            for recap_item in subcategory_group["entries"]:
                for time_series_value in recap_item["time_series"]:
                    period_date_text = time_series_value["period_date"]
                    try:
                        period_dates.append(date.fromisoformat(period_date_text))
                    except ValueError:
                        continue
    return period_dates


class EconomicRecapAsOfAvailability(NamedTuple):
    """Years / quarters / months that have at least one value in the region."""

    years: frozenset[int]
    quarters: frozenset[int]
    months: frozenset[int]


def get_as_of_availability_for_economic_recap(
    economic_data: list[EconomicRecapCategoryGroup],
    *,
    year: int | None,
) -> EconomicRecapAsOfAvailability:
    """Return years / quarters / months that have ≥1 value in the recap payload.

    Quarters and months are scoped to 'year' when it is set; otherwise both sets
    are empty (the toolbar disables them until a year is chosen).
    """
    period_dates = _list_period_dates_from_recap_data(economic_data)
    available_years = frozenset(period_date.year for period_date in period_dates)
    if year is None:
        return EconomicRecapAsOfAvailability(
            years=available_years, quarters=frozenset(), months=frozenset()
        )
    year_period_dates = [
        period_date for period_date in period_dates if period_date.year == year
    ]
    available_months = frozenset(period_date.month for period_date in year_period_dates)
    available_quarters = frozenset((month - 1) // 3 + 1 for month in available_months)
    return EconomicRecapAsOfAvailability(
        years=available_years,
        quarters=available_quarters,
        months=available_months,
    )


def parse_economic_recap_as_of(
    *,
    as_of_year: str | None,
    as_of_quarter: str | None,
    as_of_month: str | None,
    today: date | None = None,
) -> EconomicRecapAsOfSelection:
    """Parse as-of query params into a year / quarter-or-month / end-date selection.

    Latest (no year) clears the as-of filter. Year alone defaults to 31 Dec of
    that year. Quarter and month are mutually exclusive; when both are present,
    month wins. Invalid values fall back toward Latest / year-only.
    """
    reference_today = today if today is not None else get_local_today()
    allowed_years = set(list_as_of_years_for_economic_recap(as_of=reference_today))
    try:
        year = int(as_of_year) if as_of_year not in (None, "") else None
    except (TypeError, ValueError):
        year = None
    if year not in allowed_years:
        return EconomicRecapAsOfSelection(
            year=None, quarter=None, month=None, end_date=None
        )

    try:
        month = int(as_of_month) if as_of_month not in (None, "") else None
    except (TypeError, ValueError):
        month = None
    if month is not None and month not in range(1, 13):
        month = None

    try:
        quarter = int(as_of_quarter) if as_of_quarter not in (None, "") else None
    except (TypeError, ValueError):
        quarter = None
    if quarter is not None and quarter not in range(1, 5):
        quarter = None

    # Month and quarter are mutually exclusive; month wins when both are set.
    if month is not None:
        quarter = None
        end_month = month
    elif quarter is not None:
        end_month = ECONOMIC_RECAP_QUARTER_END_MONTH_BY_QUARTER[quarter]
        month = None
    else:
        # Year alone → last month of that year (December); leave month unset in URL.
        end_month = 12
        month = None

    return EconomicRecapAsOfSelection(
        year=year,
        quarter=quarter,
        month=month,
        end_date=_get_month_end_date(year, end_month),
    )
