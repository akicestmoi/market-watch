"""Build economic-recap cell values and format them for display."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import NamedTuple, TypedDict

from data_visualization.services.config import TIME_SERIES_HISTORY_WINDOW
from economic_overview.models.common import (
    INDICATOR_CURRENCY_SYMBOL_BY_CODE,
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseCurrencyChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
    IndicatorExpansionRelationChoices,
    IndicatorMeasureTypeChoices,
    IndicatorPriceBasisChoices,
)
from economic_overview.services.config import (
    ANNUAL_GDP_GROWTH_SERIES_LABEL,
    ANNUALIZED_ABS_LEVEL_TICKERS,
    NOMINAL_PRICE_BASIS_SERIES_LABELS,
    NON_SEASONALLY_ADJUSTED_TICKERS,
    REAL_PRICE_BASIS_SERIES_LABELS,
    REALIZED_ANNUAL_GDP_GROWTH_SERIES_LABEL,
    VS_GDP_SERIES_LABELS,
)


class _GdpLevelPoint(NamedTuple):
    """One Real GDP or annual-growth level used by annual GDP growth math."""

    period: date
    data_value: float


class _ScaledAmount(NamedTuple):
    """Value scaled so its absolute magnitude stays at most 999."""

    value: float
    magnitude: IndicatorAmountMagnitudeChoices
    currency: IndicatorBaseCurrencyChoices | None


def get_indicator_price_basis(
    series_label: str,
) -> IndicatorPriceBasisChoices | None:
    """Return nominal / real when the printed level has a GDP price basis."""
    if series_label in REAL_PRICE_BASIS_SERIES_LABELS:
        return IndicatorPriceBasisChoices.REAL
    if series_label in NOMINAL_PRICE_BASIS_SERIES_LABELS:
        return IndicatorPriceBasisChoices.NOMINAL
    return None


def format_amount_unit_label(
    magnitude: IndicatorAmountMagnitudeChoices,
    currency: IndicatorBaseCurrencyChoices | None = None,
) -> str:
    """Build a compact amount label such as 'b$', 't€', or 'm'."""
    magnitude_label = magnitude.value.lower()
    if currency is None:
        return magnitude_label
    currency_symbol = INDICATOR_CURRENCY_SYMBOL_BY_CODE.get(currency, currency.value)
    return f"{magnitude_label}{currency_symbol}"


def _scale_amount_for_display(
    value: float,
    amount_magnitude: IndicatorAmountMagnitudeChoices,
    base_currency: IndicatorBaseCurrencyChoices | None = None,
) -> _ScaledAmount:
    """Divide by 1_000 until 'abs(value) <= 999', bumping K→M→B→T."""
    magnitude_order = IndicatorAmountMagnitudeChoices.ordered()
    scaled_magnitude = amount_magnitude
    scaled_value = float(value)
    while abs(scaled_value) > 999:
        next_magnitude_index = magnitude_order.index(scaled_magnitude) + 1
        if next_magnitude_index >= len(magnitude_order):
            break
        scaled_value /= 1000.0
        scaled_magnitude = magnitude_order[next_magnitude_index]
    return _ScaledAmount(
        value=scaled_value, magnitude=scaled_magnitude, currency=base_currency
    )


def _scale_value_to_magnitude(
    value: float,
    from_magnitude: IndicatorAmountMagnitudeChoices,
    to_magnitude: IndicatorAmountMagnitudeChoices,
) -> float:
    """Convert an amount along the K→M→B→T ladder to a fixed magnitude."""
    magnitude_order = IndicatorAmountMagnitudeChoices.ordered()
    from_index = magnitude_order.index(from_magnitude)
    to_index = magnitude_order.index(to_magnitude)
    return float(value) / (1000.0 ** (to_index - from_index))


def get_shared_amount_magnitude(
    *,
    current: float | None,
    previous: float | None,
    change: float | None,
    base_unit: str,
) -> IndicatorAmountMagnitudeChoices | None:
    """Pick one amount magnitude for Current / Previous / Change (Current first)."""
    if base_unit not in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        return None
    reference_value = (
        current if current is not None else previous if previous is not None else change
    )
    if reference_value is None:
        return IndicatorAmountMagnitudeChoices(base_unit)
    return _scale_amount_for_display(
        reference_value,
        IndicatorAmountMagnitudeChoices(base_unit),
        None,
    ).magnitude


def _format_spaced_number(value: float, digits: int = 2) -> str:
    """Format with space thousands separators, e.g. '1 234.56'."""
    sign = "-" if value < 0 else ""
    absolute_value = abs(value)
    formatted_number = f"{absolute_value:.{digits}f}"
    integer_part, _, decimal_part = formatted_number.partition(".")
    spaced_integer = ""
    digits_reversed = integer_part[::-1]
    for index, digit in enumerate(digits_reversed):
        if index and index % 3 == 0:
            spaced_integer += " "
        spaced_integer += digit
    spaced_integer = spaced_integer[::-1]
    if digits > 0:
        return f"{sign}{spaced_integer}.{decimal_part}"
    return f"{sign}{spaced_integer}"


def _format_raw_indicator_value_for_display(
    value: float,
    *,
    base_unit: str,
    base_currency: str,
    include_unit_label: bool,
    digits: int,
    amount_magnitude: IndicatorAmountMagnitudeChoices | None,
) -> str:
    """Format one raw or YTD-raw indicator value with unit labels when applicable."""
    if base_unit == IndicatorBaseUnitChoices.PERCENT:
        formatted_number = _format_spaced_number(value, digits=digits)
        return f"{formatted_number} %" if include_unit_label else formatted_number
    if base_unit in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        base_magnitude = IndicatorAmountMagnitudeChoices(base_unit)
        base_currency_enum = (
            IndicatorBaseCurrencyChoices(base_currency) if base_currency else None
        )
        if amount_magnitude is None:
            scaled_amount = _scale_amount_for_display(
                value, base_magnitude, base_currency_enum
            )
        else:
            scaled_amount = _ScaledAmount(
                value=_scale_value_to_magnitude(
                    value, base_magnitude, amount_magnitude
                ),
                magnitude=amount_magnitude,
                currency=base_currency_enum,
            )
        formatted_number = _format_spaced_number(scaled_amount.value, digits=digits)
        if not include_unit_label:
            return formatted_number
        unit_label = format_amount_unit_label(
            scaled_amount.magnitude, scaled_amount.currency
        )
        return f"{formatted_number} {unit_label}"
    # INDEX or undocumented blank unit — number only.
    return _format_spaced_number(value, digits=digits)


def format_indicator_value(
    value: float | None,
    *,
    base_unit: str = "",
    base_currency: str = "",
    mode: IndicatorDisplayModeChoices | str = IndicatorDisplayModeChoices.RAW,
    include_unit_label: bool = True,
    digits: int = 2,
    amount_magnitude: IndicatorAmountMagnitudeChoices | None = None,
) -> str:
    """Format a single indicator value for UI / LLM display.

    Amounts append a compact magnitude + currency symbol ('1.50 t$'). Pass
    'amount_magnitude' to keep Current / Previous / Change on one scale.
    Percent and growth modes append ' %'. Index series have no unit suffix.
    """
    if value is None:
        return ""
    mode_value = (
        mode.value if isinstance(mode, IndicatorDisplayModeChoices) else str(mode)
    )
    # YTDRaw keeps amount / index units; every other non-Raw mode is a percent.
    if mode_value not in {
        IndicatorDisplayModeChoices.RAW,
        IndicatorDisplayModeChoices.YTD_RAW,
    }:
        formatted_number = _format_spaced_number(value, digits=digits)
        return f"{formatted_number} %" if include_unit_label else formatted_number
    return _format_raw_indicator_value_for_display(
        value,
        base_unit=base_unit,
        base_currency=base_currency,
        include_unit_label=include_unit_label,
        digits=digits,
        amount_magnitude=amount_magnitude,
    )


class EconomicRecapTimeSeriesValue(TypedDict):
    """One printed level for client-side Raw/QoQ/QoQy/YoY transforms."""

    period: str  # Display period label
    period_date: str  # ISO date string for the UI
    value: float


class AnnualGdpGrowthTriplet(NamedTuple):
    """Current trailing-4Q estimate, sourced realized annual growth, and change."""

    current: float | None
    previous: float | None
    change: float | None
    period: str | None
    time_series: list[EconomicRecapTimeSeriesValue]


def _aggregate_quarter_window_level(
    quarter_levels: list[float], *, is_annualized: bool
) -> float:
    """Combine four quarter printed levels into one annual-comparable level."""
    if is_annualized:
        return sum(quarter_levels) / len(quarter_levels)
    return sum(quarter_levels)


def _calculate_growth_percent(
    current_level: float, previous_level: float
) -> float | None:
    """Return percent growth from previous_level to current_level."""
    if previous_level == 0:
        return None
    return round((current_level / previous_level - 1.0) * 100.0, 10)


class _RealizedAnnualGdpGrowth(NamedTuple):
    """Closed-year annual GDP growth percent and the calendar year it covers."""

    growth_percent: float | None
    year: int | None


def _get_sourced_realized_annual_gdp_growth(
    realized_values_newest_first: Sequence[_GdpLevelPoint],
    *,
    before_year: int,
) -> _RealizedAnnualGdpGrowth:
    """Return the latest closed-year annual GDP growth from a sourced series.

    Keeps the newest observation with 'period.year < before_year' so the
    Real GDP as-of year is never used as Previous.
    """
    for gdp_level_point in realized_values_newest_first:
        if gdp_level_point.period.year >= before_year:
            continue
        return _RealizedAnnualGdpGrowth(
            growth_percent=gdp_level_point.data_value,
            year=gdp_level_point.period.year,
        )
    return _RealizedAnnualGdpGrowth(growth_percent=None, year=None)


def _compute_calendar_year_growth_from_real_gdp(
    chronological_real_gdp: Sequence[_GdpLevelPoint],
    *,
    is_annualized: bool,
    before_year: int,
) -> _RealizedAnnualGdpGrowth:
    """Derive closed-year growth from quarterly Real GDP when no annual series exists.

    Used for Japan (Cabinet Office), where the annual value rides the same
    quarterly estimates release as Real GDP.
    """
    # Usage of dict: calendar year → the quarterly printed levels in that year.
    levels_by_calendar_year: dict[int, list[float]] = defaultdict(list)
    for gdp_level_point in chronological_real_gdp:
        levels_by_calendar_year[gdp_level_point.period.year].append(
            gdp_level_point.data_value
        )

    complete_years = sorted(
        year
        for year, year_levels in levels_by_calendar_year.items()
        if year < before_year and len(year_levels) >= 4
    )
    if len(complete_years) < 2:
        return _RealizedAnnualGdpGrowth(growth_percent=None, year=None)
    # Newest complete year before Period vs the year before it.
    realized_year = complete_years[-1]
    previous_year = complete_years[-2]
    if previous_year != realized_year - 1:
        return _RealizedAnnualGdpGrowth(growth_percent=None, year=None)
    # Annual growth uses the four calendar quarters of each complete year.
    current_year_level = _aggregate_quarter_window_level(
        levels_by_calendar_year[realized_year][:4],
        is_annualized=is_annualized,
    )
    # Same four-quarter window for the prior year.
    previous_year_level = _aggregate_quarter_window_level(
        levels_by_calendar_year[previous_year][:4],
        is_annualized=is_annualized,
    )
    return _RealizedAnnualGdpGrowth(
        growth_percent=_calculate_growth_percent(
            current_year_level, previous_year_level
        ),
        year=realized_year,
    )


def _get_trailing_four_quarter_gdp_growth_estimate(
    chronological_real_gdp: Sequence[_GdpLevelPoint],
    *,
    is_annualized: bool,
) -> float | None:
    """Return trailing-4Q-over-prior-4Q Real GDP growth when eight quarters exist."""
    if len(chronological_real_gdp) < 8:
        return None
    recent_window = chronological_real_gdp[-4:]
    prior_window = chronological_real_gdp[-8:-4]
    recent_level = _aggregate_quarter_window_level(
        [gdp_level_point.data_value for gdp_level_point in recent_window],
        is_annualized=is_annualized,
    )
    prior_level = _aggregate_quarter_window_level(
        [gdp_level_point.data_value for gdp_level_point in prior_window],
        is_annualized=is_annualized,
    )
    return _calculate_growth_percent(recent_level, prior_level)


def _build_annual_gdp_growth_recap_time_series(
    *,
    realized: float | None,
    realized_year: int | None,
    estimate: float | None,
    period_label: str,
    period_date: str,
) -> list[EconomicRecapTimeSeriesValue]:
    """Append realized-year and current-year estimate points for the recap sparkline."""
    time_series: list[EconomicRecapTimeSeriesValue] = []
    if realized is not None and realized_year is not None:
        time_series.append(
            EconomicRecapTimeSeriesValue(
                period=str(realized_year),
                period_date=f"{realized_year:04d}-01-01",
                value=realized,
            )
        )
    if estimate is not None:
        time_series.append(
            EconomicRecapTimeSeriesValue(
                period=period_label,
                period_date=period_date,
                value=estimate,
            )
        )
    return time_series


def _get_realized_annual_gdp_growth_for_triplet(
    chronological_real_gdp: Sequence[_GdpLevelPoint],
    realized_annual_values_newest_first: Sequence[_GdpLevelPoint],
    *,
    is_annualized: bool,
    period_year: int,
) -> _RealizedAnnualGdpGrowth:
    """Return sourced realized annual growth, or closed-year fallback from Real GDP."""
    realized_annual_gdp_growth = _get_sourced_realized_annual_gdp_growth(
        realized_annual_values_newest_first, before_year=period_year
    )
    if realized_annual_gdp_growth.growth_percent is not None:
        return realized_annual_gdp_growth
    return _compute_calendar_year_growth_from_real_gdp(
        chronological_real_gdp,
        is_annualized=is_annualized,
        before_year=period_year,
    )


def _build_annual_gdp_growth_triplet_from_chronological(
    chronological: Sequence[_GdpLevelPoint],
    realized_annual_values_newest_first: Sequence[_GdpLevelPoint],
    *,
    is_annualized: bool,
) -> AnnualGdpGrowthTriplet:
    """Build one annual GDP growth triplet from chronological Real GDP values."""
    # Period label is the calendar year of the newest published Real GDP quarter.
    latest_quarter = chronological[-1]
    period_year = latest_quarter.period.year
    period_label = str(period_year)
    period_date = f"{period_year:04d}-01-01"
    estimate = _get_trailing_four_quarter_gdp_growth_estimate(
        chronological, is_annualized=is_annualized
    )
    realized_annual_gdp_growth = _get_realized_annual_gdp_growth_for_triplet(
        chronological,
        realized_annual_values_newest_first,
        is_annualized=is_annualized,
        period_year=period_year,
    )
    realized = realized_annual_gdp_growth.growth_percent
    realized_year = realized_annual_gdp_growth.year
    change = (
        estimate - realized if estimate is not None and realized is not None else None
    )
    time_series = _build_annual_gdp_growth_recap_time_series(
        realized=realized,
        realized_year=realized_year,
        estimate=estimate,
        period_label=period_label,
        period_date=period_date,
    )
    return AnnualGdpGrowthTriplet(
        current=estimate,
        previous=realized,
        change=change,
        period=period_label,
        time_series=time_series,
    )


def _list_gdp_level_points_newest_first(
    economic_data_values_newest_first: Sequence[EconomicDataModel],
) -> list[_GdpLevelPoint]:
    """Keep dated GDP levels from newest-first economic data values."""
    gdp_level_points: list[_GdpLevelPoint] = []
    for economic_data_value in economic_data_values_newest_first:
        if economic_data_value.period is None or economic_data_value.data_value is None:
            continue
        gdp_level_points.append(
            _GdpLevelPoint(
                period=economic_data_value.period,
                data_value=float(economic_data_value.data_value),
            )
        )
    return gdp_level_points


def compute_annual_gdp_growth_triplet(
    real_gdp_values_newest_first: Sequence[_GdpLevelPoint],
    realized_annual_values_newest_first: Sequence[_GdpLevelPoint],
    *,
    is_annualized: bool,
) -> AnnualGdpGrowthTriplet:
    """Build Current (trailing-4Q estimate) and Previous (sourced realized year).

    Period is the calendar year of the latest Real GDP quarter (e.g. 26Q3 → 2026).
    Period-level values (FR / Eurostat) sum four quarters; SAAR / annualized prints
    (US / JP) averages the four quarterly values. Previous prefers a hidden
    national annual growth series; when that series is empty, falls back to
    closed-calendar-year growth from Real GDP (Japan Cabinet Office path).
    """
    empty = AnnualGdpGrowthTriplet(
        current=None, previous=None, change=None, period=None, time_series=[]
    )
    if not real_gdp_values_newest_first:
        return empty
    chronological = list(reversed(real_gdp_values_newest_first))
    return _build_annual_gdp_growth_triplet_from_chronological(
        chronological,
        realized_annual_values_newest_first,
        is_annualized=is_annualized,
    )


class RecapLineKey(NamedTuple):
    """Identity of one aligned recap table line."""

    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices
    line_name: str


class _IndicatorAtLocation(NamedTuple):
    """One indicator contributing a cell on a recap line."""

    location: EconomicDataLocationChoices
    indicator: EconomicIndicatorInformationModel


class _RecapLineGrouping(NamedTuple):
    """Indicators grouped by recap line, plus a template indicator per line."""

    # Usage of dict: keys are runtime (category, subcategory, line_name) pairs.
    indicators_at_locations_for_line: dict[RecapLineKey, list[_IndicatorAtLocation]]
    # Usage of dict: keys are the same line keys; value is the first indicator seen.
    template_indicator_by_line: dict[RecapLineKey, EconomicIndicatorInformationModel]


def _format_recap_line_unit_parenthesis(
    indicators: list[EconomicIndicatorInformationModel],
    *,
    mode: IndicatorDisplayModeChoices = IndicatorDisplayModeChoices.RAW,
) -> str:
    """Return a base-year suffix for index series; amount and percent stay off the name.

    Rates and amount magnitudes are shown on Current / Previous / Change cells
    instead of '(in %)' / amount units on the line title. When locations disagree
    on base year, join with ' / ' and short location codes
    (e.g. '(base year: 2010 US / 2025 FR)').
    """
    if mode != IndicatorDisplayModeChoices.RAW:
        return ""
    if not indicators:
        return ""

    base_units = {indicator.base_unit for indicator in indicators}
    if IndicatorBaseUnitChoices.INDEX not in base_units:
        return ""
    base_years_with_locations = [
        (indicator.base_year, indicator.location)
        for indicator in indicators
        if indicator.base_year is not None
    ]
    if not base_years_with_locations:
        return ""
    unique_base_years = {year for year, _ in base_years_with_locations}
    if len(unique_base_years) == 1:
        # All locations share one base year; [0][0] is that year from any pair.
        return f"(base year: {base_years_with_locations[0][0]})"
    base_year_parts = [
        f"{base_year} {location}"
        for base_year, location in base_years_with_locations
        if base_year is not None
    ]
    return f"(base year: {' / '.join(base_year_parts)})"


def group_indicators_by_recap_line(
    indicators: list[EconomicIndicatorInformationModel],
) -> _RecapLineGrouping:
    """Group indicators into cross-location recap lines."""
    # Usage of dict: keys are runtime (series label, category, location) triples.
    # Count within category so MACRO 'Business Investment' is not forced onto
    # the long series name just because BUSINESS also had that line.
    type_count_in_category_location: dict[tuple[str, str, str], int] = defaultdict(int)
    for indicator in indicators:
        type_count_in_category_location[
            (indicator.series_label, indicator.category, indicator.location)
        ] += 1

    # Usage of dict: keys are runtime line keys from the DB query.
    indicators_at_locations_for_line: dict[RecapLineKey, list[_IndicatorAtLocation]] = (
        defaultdict(list)
    )
    template_indicator_by_line: dict[
        RecapLineKey, EconomicIndicatorInformationModel
    ] = {}
    for indicator in indicators:
        # Shared series label when unique in-category; else full name (e.g. Tankan).
        line_name = (
            indicator.full_name
            if type_count_in_category_location[
                (indicator.series_label, indicator.category, indicator.location)
            ]
            > 1
            else indicator.series_label
        )
        recap_line_key = RecapLineKey(
            category=EconomicDataCategoryChoices(indicator.category),
            subcategory=EconomicDataSubcategoryChoices(indicator.subcategory),
            line_name=line_name,
        )
        indicators_at_locations_for_line[recap_line_key].append(
            _IndicatorAtLocation(
                location=EconomicDataLocationChoices(indicator.location),
                indicator=indicator,
            )
        )
        template_indicator_by_line.setdefault(recap_line_key, indicator)
    return _RecapLineGrouping(
        indicators_at_locations_for_line=indicators_at_locations_for_line,
        template_indicator_by_line=template_indicator_by_line,
    )


def get_time_series_by_indicator_id(
    indicator_ids: list[int],
) -> dict[
    int, list[EconomicDataModel]
]:  # Usage of dict: keys are runtime indicator PKs.
    """Fetch newest-first absolute economic data (cap: TIME_SERIES_HISTORY_WINDOW)."""
    if not indicator_ids:
        return {}
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]] = defaultdict(list)
    economic_data_values = (
        EconomicDataModel.objects.filter(
            indicator_id__in=indicator_ids,
            data_value__isnull=False,
            period__isnull=False,
        )
        .select_related("indicator")
        .order_by("indicator_id", "-period")
        .iterator(chunk_size=2000)
    )
    for economic_data_value in economic_data_values:
        indicator_pk = economic_data_value.indicator.pk
        economic_data_time_series = time_series_by_indicator_id[indicator_pk]
        if len(economic_data_time_series) >= TIME_SERIES_HISTORY_WINDOW:
            continue
        economic_data_time_series.append(economic_data_value)
    return time_series_by_indicator_id


class EconomicRecapItem(TypedDict):
    """One location cell in the economic recap table."""

    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices
    location: EconomicDataLocationChoices
    name: str
    display_name: str
    frequency: EconomicPublicationFrequencyChoices
    source: EconomicDataSourceChoices
    technical_name: str
    description: str
    source_url: str
    measure_type: IndicatorMeasureTypeChoices
    # True when the printed level is an annualized rate (SAAR / JP), not the period sum.
    is_annualized: bool
    # False for NSA Eurostat seeds (e.g. corporate GFCF); True otherwise.
    is_seasonally_adjusted: bool
    # Nominal / real price basis for the bubble and vsGDP denominator matching.
    price_basis: IndicatorPriceBasisChoices | None
    parent_series_label: str
    expansion_relation: IndicatorExpansionRelationChoices | str
    base_year: int | None
    base_unit: IndicatorBaseUnitChoices | None
    base_currency: IndicatorBaseCurrencyChoices | None
    default_mode: IndicatorDisplayModeChoices
    # True when the line offers vsGDP (outstanding / matching-price-basis GDP).
    supports_vs_gdp: bool
    current: float | None
    previous: float | None
    change: float | None
    period: str | None  # Display period label
    time_series: list[EconomicRecapTimeSeriesValue]


def _list_time_series_from_economic_data_values(
    economic_data_values: list[EconomicDataModel],
) -> list[EconomicRecapTimeSeriesValue]:
    """Build chronological time-series values from newest-first economic data."""
    return [
        EconomicRecapTimeSeriesValue(
            period=economic_data_value.get_period_display() or "",
            period_date=economic_data_value.period.isoformat(),
            value=float(economic_data_value.data_value),
        )
        for economic_data_value in reversed(economic_data_values)
        if economic_data_value.period is not None
        and economic_data_value.data_value is not None
    ]


class _RecapCurrentPreviousValues(NamedTuple):
    """Current and previous economic data values for one recap cell."""

    current_value: float | None
    previous_value: float | None
    period_display: str | None
    value_change: float | None


def _get_recap_current_previous_values(
    economic_data_values: list[EconomicDataModel],
) -> _RecapCurrentPreviousValues:
    """Read current, previous, period, and change from newest-first values."""
    padded_economic_data_values = economic_data_values + [None, None]
    # The series is newest-first, so index 0 is the current value (None if empty).
    current_economic_data_value = padded_economic_data_values[0]
    # The series is newest-first, so index 1 is the previous value for the change.
    previous_economic_data_value = padded_economic_data_values[1]
    current_value = (
        current_economic_data_value.data_value
        if current_economic_data_value is not None
        else None
    )
    previous_value = (
        previous_economic_data_value.data_value
        if previous_economic_data_value is not None
        else None
    )
    period_display = (
        current_economic_data_value.get_period_display()
        if current_economic_data_value is not None
        else None
    )
    value_change = (
        current_value - previous_value
        if current_value is not None and previous_value is not None
        else None
    )
    return _RecapCurrentPreviousValues(
        current_value=current_value,
        previous_value=previous_value,
        period_display=period_display,
        value_change=value_change,
    )


def build_recap_item_from_economic_data_values(
    indicator: EconomicIndicatorInformationModel,
    location: EconomicDataLocationChoices,
    line_name: str,
    economic_data_values: list[EconomicDataModel],
) -> EconomicRecapItem:
    """Build one location cell from newest-first economic data values."""
    current_previous = _get_recap_current_previous_values(economic_data_values)
    return EconomicRecapItem(
        category=EconomicDataCategoryChoices(indicator.category),
        subcategory=EconomicDataSubcategoryChoices(indicator.subcategory),
        location=location,
        name=line_name,
        display_name=indicator.get_display_name(),
        frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
        source=EconomicDataSourceChoices(indicator.source),
        technical_name=indicator.technical_name,
        description=indicator.description,
        source_url=indicator.source_url,
        measure_type=IndicatorMeasureTypeChoices(indicator.measure_type),
        is_annualized=indicator.ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
        is_seasonally_adjusted=(
            indicator.ticker not in NON_SEASONALLY_ADJUSTED_TICKERS
        ),
        price_basis=get_indicator_price_basis(indicator.series_label),
        parent_series_label=indicator.parent_series_label,
        expansion_relation=indicator.expansion_relation,
        base_year=indicator.base_year,
        base_unit=(
            IndicatorBaseUnitChoices(indicator.base_unit)
            if indicator.base_unit
            else None
        ),
        base_currency=(
            IndicatorBaseCurrencyChoices(indicator.base_currency)
            if indicator.base_currency
            else None
        ),
        default_mode=IndicatorDisplayModeChoices(indicator.default_mode),
        supports_vs_gdp=indicator.series_label in VS_GDP_SERIES_LABELS,
        current=current_previous.current_value,
        previous=current_previous.previous_value,
        change=current_previous.value_change,
        period=current_previous.period_display,
        time_series=_list_time_series_from_economic_data_values(economic_data_values),
    )


class _RecapLineSharedFields(NamedTuple):
    """Shared display and unit fields for every cell on one recap line."""

    display_name: str
    frequency: EconomicPublicationFrequencyChoices
    indicator_default_display_mode: IndicatorDisplayModeChoices
    base_year: int | None
    base_unit: IndicatorBaseUnitChoices | None
    base_currency: IndicatorBaseCurrencyChoices | None
    is_annual_gdp_growth_line: bool


def _get_recap_line_shared_fields(
    indicators_at_locations: list[_IndicatorAtLocation],
    template_indicator: EconomicIndicatorInformationModel,
) -> _RecapLineSharedFields:
    """Return display name, units, and mode shared by every location on one line."""
    present_indicators = [entry.indicator for entry in indicators_at_locations]
    indicator_default_display_mode = IndicatorDisplayModeChoices(
        template_indicator.default_mode
    )
    unit_parenthesis = _format_recap_line_unit_parenthesis(
        present_indicators, mode=indicator_default_display_mode
    )
    display_name = (
        f"{template_indicator.series_label} {unit_parenthesis}".strip()
        if unit_parenthesis
        else template_indicator.series_label
    )
    base_unit: IndicatorBaseUnitChoices | None = (
        IndicatorBaseUnitChoices(template_indicator.base_unit)
        if template_indicator.base_unit
        else None
    )
    base_currency = (
        IndicatorBaseCurrencyChoices(template_indicator.base_currency)
        if template_indicator.base_currency
        else None
    )
    return _RecapLineSharedFields(
        display_name=display_name,
        frequency=EconomicPublicationFrequencyChoices(template_indicator.frequency),
        indicator_default_display_mode=indicator_default_display_mode,
        base_year=template_indicator.base_year,
        base_unit=base_unit,
        base_currency=base_currency,
        is_annual_gdp_growth_line=(
            template_indicator.series_label == ANNUAL_GDP_GROWTH_SERIES_LABEL
        ),
    )


def _get_missing_location_recap_item(
    recap_line_key: RecapLineKey,
    location: EconomicDataLocationChoices,
    shared_fields: _RecapLineSharedFields,
    template_indicator: EconomicIndicatorInformationModel,
) -> EconomicRecapItem:
    """Return an empty cell so every location column stays aligned."""
    return EconomicRecapItem(
        category=recap_line_key.category,
        subcategory=recap_line_key.subcategory,
        location=location,
        name=recap_line_key.line_name,
        display_name=shared_fields.display_name,
        frequency=shared_fields.frequency,
        source=EconomicDataSourceChoices(template_indicator.source),
        technical_name=template_indicator.technical_name,
        description="",
        source_url="",
        measure_type=IndicatorMeasureTypeChoices(template_indicator.measure_type),
        is_annualized=template_indicator.ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
        is_seasonally_adjusted=(
            template_indicator.ticker not in NON_SEASONALLY_ADJUSTED_TICKERS
        ),
        price_basis=get_indicator_price_basis(recap_line_key.line_name),
        parent_series_label=template_indicator.parent_series_label,
        expansion_relation=template_indicator.expansion_relation,
        base_year=shared_fields.base_year,
        base_unit=shared_fields.base_unit,
        base_currency=shared_fields.base_currency,
        default_mode=shared_fields.indicator_default_display_mode,
        supports_vs_gdp=(recap_line_key.line_name in VS_GDP_SERIES_LABELS),
        current=None,
        previous=None,
        change=None,
        period=None,
        time_series=[],
    )


def _get_recap_item_for_location_on_line(
    recap_line_key: RecapLineKey,
    location: EconomicDataLocationChoices,
    indicator_for_location: EconomicIndicatorInformationModel,
    shared_fields: _RecapLineSharedFields,
    # Usage of dict: keys are runtime indicator primary keys from the DB query.
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
    # Usage of dict: location code → newest-first Real GDP economic data.
    real_gdp_series_by_location: dict[str, list[EconomicDataModel]],
    # Usage of dict: location code → Real GDP seed ticker (SAAR detection).
    real_gdp_ticker_by_location: dict[str, str],
    # Usage of dict: location code → newest-first sourced realized annual growth.
    realized_annual_series_by_location: dict[str, list[EconomicDataModel]],
) -> EconomicRecapItem:
    """Return one location cell for a recap line, including annual GDP growth math."""
    if shared_fields.is_annual_gdp_growth_line:
        real_gdp_ticker = real_gdp_ticker_by_location.get(location.value, "")
        growth_triplet = compute_annual_gdp_growth_triplet(
            _list_gdp_level_points_newest_first(
                real_gdp_series_by_location.get(location.value, [])
            ),
            _list_gdp_level_points_newest_first(
                realized_annual_series_by_location.get(location.value, [])
            ),
            is_annualized=real_gdp_ticker in ANNUALIZED_ABS_LEVEL_TICKERS,
        )
        recap_item = build_recap_item_from_economic_data_values(
            indicator_for_location,
            location,
            recap_line_key.line_name,
            [],
        )
        recap_item["current"] = growth_triplet.current
        recap_item["previous"] = growth_triplet.previous
        recap_item["change"] = growth_triplet.change
        recap_item["period"] = growth_triplet.period
        recap_item["time_series"] = growth_triplet.time_series
        recap_item["is_annualized"] = False
    else:
        recap_item = build_recap_item_from_economic_data_values(
            indicator_for_location,
            location,
            recap_line_key.line_name,
            time_series_by_indicator_id.get(indicator_for_location.id, []),
        )
    recap_item["display_name"] = shared_fields.display_name
    return recap_item


def _build_recap_items_for_one_line(
    recap_line_key: RecapLineKey,
    indicators_at_locations: list[_IndicatorAtLocation],
    template_indicator: EconomicIndicatorInformationModel,
    locations: list[EconomicDataLocationChoices],
    # Usage of dict: keys are runtime indicator primary keys from the DB query.
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
    # Usage of dict: location code → newest-first Real GDP economic data.
    real_gdp_series_by_location: dict[str, list[EconomicDataModel]],
    # Usage of dict: location code → Real GDP seed ticker (SAAR detection).
    real_gdp_ticker_by_location: dict[str, str],
    # Usage of dict: location code → newest-first sourced realized annual growth.
    realized_annual_series_by_location: dict[str, list[EconomicDataModel]],
) -> list[EconomicRecapItem]:
    """Build one cell per requested location for a single recap line."""
    shared_fields = _get_recap_line_shared_fields(
        indicators_at_locations, template_indicator
    )
    recap_items: list[EconomicRecapItem] = []
    for location in locations:
        indicator_for_location = next(
            (
                entry.indicator
                for entry in indicators_at_locations
                if entry.location == location
            ),
            None,
        )
        if indicator_for_location is None:
            recap_items.append(
                _get_missing_location_recap_item(
                    recap_line_key, location, shared_fields, template_indicator
                )
            )
            continue
        recap_items.append(
            _get_recap_item_for_location_on_line(
                recap_line_key,
                location,
                indicator_for_location,
                shared_fields,
                time_series_by_indicator_id,
                real_gdp_series_by_location,
                real_gdp_ticker_by_location,
                realized_annual_series_by_location,
            )
        )
    return recap_items


class _RealGdpSeriesByLocation(NamedTuple):
    """Real GDP time series and tickers keyed by location code."""

    # Usage of dict: location code → newest-first Real GDP economic data.
    series_by_location: dict[str, list[EconomicDataModel]]
    # Usage of dict: location code → Real GDP seed ticker (SAAR detection).
    ticker_by_location: dict[str, str]


def get_real_gdp_series_by_location(
    indicators: list[EconomicIndicatorInformationModel],
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
) -> _RealGdpSeriesByLocation:
    """Return Real GDP series and tickers per location for annual growth math."""
    series_by_location: dict[str, list[EconomicDataModel]] = {}
    ticker_by_location: dict[str, str] = {}
    for indicator in indicators:
        if indicator.series_label != "Real GDP":
            continue
        series_by_location[indicator.location] = time_series_by_indicator_id.get(
            indicator.id, []
        )
        ticker_by_location[indicator.location] = indicator.ticker
    return _RealGdpSeriesByLocation(
        series_by_location=series_by_location,
        ticker_by_location=ticker_by_location,
    )


def get_realized_annual_gdp_growth_series_by_location(
    locations: list[EconomicDataLocationChoices],
) -> dict[str, list[EconomicDataModel]]:
    """Return hidden national annual growth series per location for GDP Previous."""
    realized_annual_indicators = list(
        EconomicIndicatorInformationModel.objects.filter(
            location__in=[location.value for location in locations],
            series_label=REALIZED_ANNUAL_GDP_GROWTH_SERIES_LABEL,
            is_hidden=True,
        )
    )
    realized_time_series_by_indicator_id = get_time_series_by_indicator_id(
        [indicator.id for indicator in realized_annual_indicators]
    )
    # Usage of dict: location code → newest-first sourced realized annual growth.
    return {
        indicator.location: realized_time_series_by_indicator_id.get(indicator.id, [])
        for indicator in realized_annual_indicators
    }


def list_recap_lines_with_items(
    line_grouping: _RecapLineGrouping,
    locations: list[EconomicDataLocationChoices],
    time_series_by_indicator_id: dict[int, list[EconomicDataModel]],
    real_gdp_series: _RealGdpSeriesByLocation,
    realized_annual_series_by_location: dict[str, list[EconomicDataModel]],
) -> list[tuple[RecapLineKey, list[EconomicRecapItem]]]:
    """Build recap cells for every grouped line in catalog id discovery order."""
    recap_lines_by_key: list[tuple[RecapLineKey, list[EconomicRecapItem]]] = []
    for (
        recap_line_key,
        indicators_at_locations,
    ) in line_grouping.indicators_at_locations_for_line.items():
        recap_lines_by_key.append(
            (
                recap_line_key,
                _build_recap_items_for_one_line(
                    recap_line_key,
                    indicators_at_locations,
                    line_grouping.template_indicator_by_line[recap_line_key],
                    locations,
                    time_series_by_indicator_id,
                    real_gdp_series.series_by_location,
                    real_gdp_series.ticker_by_location,
                    realized_annual_series_by_location,
                ),
            )
        )
    return recap_lines_by_key
