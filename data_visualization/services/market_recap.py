"""Build market recap payloads for the visualization UI."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Literal, NamedTuple, TypedDict

import pandas as pd
from dateutil.relativedelta import relativedelta
from django.db.models import Q

import market_overview.services.earnings as earnings
import market_overview.services.holidays as holidays
from central_banks_overview.services.central_banks_data import (
    get_decision_day_key_rates,
)
from core.services.calendar import convert_to_display_timezone
from core.services.time_series_calculation import TimeSeriesPoint
from data_visualization.services.config import (
    FX_MATRIX_ORDER,
    FX_PAIRS_FILTER,
    MARKET_RECAP_LOCATIONS_BY_GROUP,
    MarketRecapLocationEnum,
)
from data_visualization.services.economic_recap.table_content import (
    format_indicator_value,
    get_shared_amount_magnitude,
)
from data_visualization.services.time_series import (
    build_year_to_date_cumulative_time_series,
    build_ytd_yoy_time_series,
)
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorAmountMagnitudeChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.economic_data import (
    TimedEconomicDataValue,
    change_triplet_values_for_mode,
    get_number_of_months_to_calculate_mode_change,
)
from market_overview.models.common import LocationChoices
from market_overview.models.earnings import EarningsWatchlistModel
from market_overview.models.market_prices import (
    AssetClassChoices,
    AssetTypeChoices,
    MarketPriceModel,
)
from market_overview.services.config import HOLIDAY_COUNTRIES
from market_overview.services.market_data import calculate_price_change


class _DisplayAsset(TypedDict):
    """Asset display fields for one market-recap table cell."""

    country: LocationChoices | Literal["-"]
    asset: str
    name: str
    maturity: float | None
    price: float | None
    previous_price: float | None
    price_change: float | None
    price_change_pct: float | None


class _DisplayAssetbyLocation(TypedDict):
    """Market-recap assets grouped under one display location."""

    location: str  # MarketRecapLocationEnum value (e.g. "North America")
    assets: list[_DisplayAsset]


class _DisplayData(TypedDict):
    """Market-recap section for one asset class across locations."""

    asset_class: str  # human-readable AssetClassChoices label
    locations: list[_DisplayAssetbyLocation]


def _list_display_assets_from_group(group: pd.DataFrame) -> list[_DisplayAsset]:
    """Helper to create _DisplayAsset list from a DataFrame group."""
    return [
        _DisplayAsset(
            country=(
                asset_series["location"] if pd.notna(asset_series["location"]) else "-"
            ),
            asset=asset_series["short_name"],
            name=asset_series["full_name"],
            maturity=asset_series["maturity"],
            price=asset_series["price"],
            previous_price=asset_series["price_previous"],
            price_change=asset_series["price_change"],
            price_change_pct=asset_series["price_change_pct"],
        )
        for _, asset_series in group.iterrows()
        if asset_series["short_name"] not in FX_PAIRS_FILTER
    ]


def _sort_by_location_and_maturity(
    group: pd.DataFrame, location_group: str
) -> pd.DataFrame:
    """Helper to sort a location group by location order and maturity."""
    location_order = {
        loc.value: i
        for i, loc in enumerate(
            MARKET_RECAP_LOCATIONS_BY_GROUP.get(
                MarketRecapLocationEnum(location_group), []
            )
        )
    }
    return group.assign(
        location_order=group["location"].map(lambda x: location_order.get(x, 999))
    ).sort_values(["location_order", "maturity"], na_position="last")


def format_market_prices_for_recap_display(
    reference_market_prices: list[MarketPriceModel],
    previous_market_prices: list[MarketPriceModel],
) -> list[_DisplayData]:
    """Format market price data for structured display."""
    price_diff = calculate_price_change(reference_market_prices, previous_market_prices)
    if not price_diff:
        # If there is a price, there should always be a price diff (None)
        # If no price diff, then there is no data to display
        return []

    df = pd.DataFrame(price_diff).replace({float("nan"): None})

    # Map countries to location groups
    country_to_location = {
        country.value: location_group.value
        for location_group, locations in MARKET_RECAP_LOCATIONS_BY_GROUP.items()
        for country in locations
    }
    df["location_group"] = df["location"].map(
        lambda location: country_to_location.get(
            location, MarketRecapLocationEnum.NO_LOCATION.value
        )
    )
    df = df.sort_values(by="asset_id")

    data_to_display: list[_DisplayData] = []
    for asset_class, asset_group in df.groupby("asset_class", sort=False):
        locations = []
        for location_group, loc_group in asset_group.groupby(
            "location_group", sort=False
        ):
            sorted_group = _sort_by_location_and_maturity(
                loc_group, str(location_group)
            )
            assets = _list_display_assets_from_group(sorted_group)
            if assets:
                locations.append(
                    _DisplayAssetbyLocation(
                        location=MarketRecapLocationEnum(str(location_group)).value,
                        assets=assets,
                    )
                )
        if locations:
            data_to_display.append(
                _DisplayData(
                    asset_class=str(AssetClassChoices(str(asset_class)).label),
                    locations=locations,
                )
            )

    return data_to_display


class FxMatrixEntry(TypedDict):
    """One base-currency line of the FX % change matrix for the UI."""

    currency: str
    EUR: float
    USD: float
    GBP: float
    JPY: float
    CHF: float
    AUD: float
    CNY: float


class _FxPairPrice(NamedTuple):
    """One FX spot pair price."""

    pair: str
    price: float


def _lookup_fx_pair_price(fx_prices: list[_FxPairPrice], pair: str) -> float | None:
    """Return the price for an FX pair short name, if present."""
    for item in fx_prices:
        if item.pair == pair:
            return item.price
    return None


def _load_fx_pair_prices(price_date: date) -> list[_FxPairPrice]:
    """Load FX spot prices for a date as pair/price pairs."""
    fx_pair_prices: list[_FxPairPrice] = []
    for short_name, price in (
        MarketPriceModel.objects.filter(
            asset__asset_type=AssetTypeChoices.FX_SPOT_RATE,
            date=price_date,
        )
        .select_related("asset")
        .values_list("asset__short_name", "price")
    ):
        if price is None:
            continue
        fx_pair_prices.append(_FxPairPrice(pair=str(short_name), price=float(price)))
    return fx_pair_prices


def _get_fx_quote_levels_by_currency(
    fx_prices: list[_FxPairPrice], currencies: list[str]
) -> dict[str, list[float]]:
    """Build base→quote FX levels keyed by currency for 'pd.DataFrame'.

    Returns a 'dict' (not a TypedDict): keys are the caller’s currency codes
    (typically 'FX_MATRIX_ORDER') and are not a closed set at this boundary;
    values are quote-level prices in that same order. Pandas takes this mapping
    as column data before transpose in 'get_fx_prices_matrix'.
    """
    # Usage of dict: keys are FX matrix currency codes; values are quote-level
    # prices in the same order as 'currencies'.
    fx_dict: dict[str, list[float]] = {}
    for base_currency in currencies:
        prices: list[float] = []
        for quote_currency in currencies:
            if base_currency == quote_currency:
                prices.append(0.0)
                continue

            direct_pair = f"{base_currency}{quote_currency}"
            direct_price = _lookup_fx_pair_price(fx_prices, direct_pair)
            if direct_price is not None:
                prices.append(direct_price)
                continue

            inverted_pair = f"{quote_currency}{base_currency}"
            inverted_price = _lookup_fx_pair_price(fx_prices, inverted_pair)
            if inverted_price is not None:
                prices.append(1.0 / inverted_price)
                continue

            prices.append(0.0)
        fx_dict[base_currency] = prices
    return fx_dict


def get_fx_prices_matrix(
    price_date: date,
    previous_price_date: date,
) -> list[FxMatrixEntry]:
    """Get FX prices matrix showing percentage change between two dates."""
    fx_quote_levels_current = _get_fx_quote_levels_by_currency(
        _load_fx_pair_prices(price_date), FX_MATRIX_ORDER
    )
    fx_quote_levels_previous = _get_fx_quote_levels_by_currency(
        _load_fx_pair_prices(previous_price_date), FX_MATRIX_ORDER
    )

    # Transpose so each base currency is a row (not a column).
    fx_df_current = pd.DataFrame(
        fx_quote_levels_current, index=FX_MATRIX_ORDER
    ).transpose()
    fx_df_previous = pd.DataFrame(
        fx_quote_levels_previous, index=FX_MATRIX_ORDER
    ).transpose()

    fx_matrix = (
        (fx_df_current - fx_df_previous)
        .divide(fx_df_previous)
        .where((fx_df_current != 0) & (fx_df_previous != 0), 0)
        .multiply(100)
    )
    fx_matrix = fx_matrix.fillna(0.0)
    fx_matrix["currency"] = FX_MATRIX_ORDER

    fx_matrix_entries: list[FxMatrixEntry] = []
    for _, currency_series in fx_matrix.iterrows():
        fx_matrix_entries.append(
            FxMatrixEntry(
                currency=str(currency_series["currency"]),
                EUR=float(currency_series["EUR"]),
                USD=float(currency_series["USD"]),
                GBP=float(currency_series["GBP"]),
                JPY=float(currency_series["JPY"]),
                CHF=float(currency_series["CHF"]),
                AUD=float(currency_series["AUD"]),
                CNY=float(currency_series["CNY"]),
            )
        )
    return fx_matrix_entries


class _DayEventChangeClass(str, Enum):
    """CSS modifier for day-event change direction."""

    POSITIVE = "is-positive"
    NEGATIVE = "is-negative"
    UNCHANGED = "is-unchanged"
    NONE = ""


class _DayEvent(TypedDict):
    """Event that occurred on the market-recap target date."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
    mode: str  # Indicator display mode label; empty for holidays / key rates
    value: str  # Formatted current release value; empty for holidays / unknown
    previous: str  # Formatted prior-period value; empty when unavailable
    change: str  # Signed level change vs previous; empty when unavailable
    change_class: _DayEventChangeClass
    is_holiday: bool


class _DayEventsLocationGroup(TypedDict):
    """Same-day events for one location card."""

    location: str
    events: list[_DayEvent]


class _DayEventFormattedChange(NamedTuple):
    """Signed change text and CSS class for a day-event card cell."""

    change: str
    change_class: _DayEventChangeClass


def _format_day_event_change(
    change: float | None,
    *,
    base_unit: str = "",
    base_currency: str = "",
    mode: IndicatorDisplayModeChoices | str = IndicatorDisplayModeChoices.RAW,
    amount_magnitude: IndicatorAmountMagnitudeChoices | None = None,
) -> _DayEventFormattedChange:
    """Build signed change text and CSS class for a day-event card cell."""
    if change is None:
        return _DayEventFormattedChange(
            change="",
            change_class=_DayEventChangeClass.NONE,
        )
    formatted_magnitude = format_indicator_value(
        abs(change),
        base_unit=base_unit,
        base_currency=base_currency,
        mode=mode,
        include_unit_label=True,
        digits=2,
        amount_magnitude=amount_magnitude,
    )
    if change > 0:
        return _DayEventFormattedChange(
            change=f"+{formatted_magnitude}",
            change_class=_DayEventChangeClass.POSITIVE,
        )
    if change < 0:
        return _DayEventFormattedChange(
            change=f"-{formatted_magnitude}",
            change_class=_DayEventChangeClass.NEGATIVE,
        )
    return _DayEventFormattedChange(
        change="(unch)",
        change_class=_DayEventChangeClass.UNCHANGED,
    )


def _get_day_holiday_events(event_date: date) -> list[_DayEvent]:
    """Return holiday events that fall on 'event_date'."""
    day_events: list[_DayEvent] = []
    for location in HOLIDAY_COUNTRIES:
        for holiday in holidays.get_holidays(
            location=location,
            year=event_date.year,
            months=[event_date.month],
        ):
            if holiday.date != event_date:
                continue
            day_events.append(
                _DayEvent(
                    name=holiday.name,
                    location=str(LocationChoices(holiday.location).label),
                    mode="",
                    value="",
                    previous="",
                    change="",
                    change_class=_DayEventChangeClass.NONE,
                    is_holiday=True,
                )
            )
    return day_events


def _does_publication_schedule_match_event_date(
    publication_schedule: PublicationScheduleModel, event_date: date
) -> bool:
    """True when current or previous publication falls on 'event_date' (display TZ).

    After ingest, a just-released value often moves from 'current' to
    'previous' while 'current' advances to the next slot — both must count.
    """
    for publication_date in (
        publication_schedule.current_publication_date,
        publication_schedule.previous_publication_date,
    ):
        if publication_date is None:
            continue
        if convert_to_display_timezone(publication_date).date() == event_date:
            return True
    return False


def _list_publication_schedules_near_event_date(
    event_date: date,
) -> list[PublicationScheduleModel]:
    """Return schedules whose current or previous slot is near 'event_date'."""
    day_start = datetime.combine(
        event_date - timedelta(days=1), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(
        event_date + timedelta(days=1), datetime.max.time()
    ).replace(tzinfo=timezone.utc)
    return list(
        PublicationScheduleModel.objects.filter(indicator__is_hidden=False)
        .filter(
            Q(
                current_publication_date__gte=day_start,
                current_publication_date__lte=day_end,
            )
            | Q(
                previous_publication_date__gte=day_start,
                previous_publication_date__lte=day_end,
            )
        )
        .select_related("indicator")
        .order_by("indicator__location", "indicator__series_label")
    )


def _get_economic_data_time_series_for_day_event(
    indicator: EconomicIndicatorInformationModel,
    *,
    indicator_default_display_mode: IndicatorDisplayModeChoices,
    indicator_frequency: EconomicPublicationFrequencyChoices,
) -> list[TimedEconomicDataValue]:
    """Load enough history to format current / previous / change for a day-event card."""
    latest_economic_data = (
        EconomicDataModel.objects.filter(
            indicator=indicator,
            data_value__isnull=False,
            period__isnull=False,
        )
        .order_by("-period", "-last_modified")
        .first()
    )
    if latest_economic_data is None or latest_economic_data.period is None:
        return []
    history_start_period = latest_economic_data.period - relativedelta(
        months=get_number_of_months_to_calculate_mode_change(
            indicator_frequency, indicator_default_display_mode
        )
    )
    return [
        TimedEconomicDataValue(
            period=time_series_point.period,
            value=float(time_series_point.data_value),
        )
        for time_series_point in EconomicDataModel.objects.filter(
            indicator=indicator,
            data_value__isnull=False,
            period__gte=history_start_period,
        ).order_by("-period", "-last_modified")
        if time_series_point.period is not None
        and time_series_point.data_value is not None
    ]


def _list_timed_values_for_day_event_display_mode(
    economic_data_time_series: list[TimedEconomicDataValue],
    *,
    indicator_default_display_mode: IndicatorDisplayModeChoices,
    indicator_frequency: EconomicPublicationFrequencyChoices,
) -> list[TimedEconomicDataValue]:
    """Apply YTD transforms so day-event cards match the indicator default mode."""
    if indicator_default_display_mode not in {
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
    }:
        return economic_data_time_series
    ytd_points = build_year_to_date_cumulative_time_series(
        [
            TimeSeriesPoint(period=timed_value.period, value=timed_value.value)
            for timed_value in economic_data_time_series
        ],
        frequency=indicator_frequency,
    )
    if indicator_default_display_mode == IndicatorDisplayModeChoices.YTD_YOY:
        ytd_points = build_ytd_yoy_time_series(ytd_points)
    return [
        TimedEconomicDataValue(period=point.period, value=point.value)
        for point in sorted(ytd_points, key=lambda point: point.period, reverse=True)
    ]


def _get_day_event_triplet_mode(
    indicator_default_display_mode: IndicatorDisplayModeChoices,
) -> IndicatorDisplayModeChoices:
    """Return the triplet mode after any YTD pre-transform on the series."""
    # YTD helpers already return display-ready levels / YoY percents.
    if indicator_default_display_mode in {
        IndicatorDisplayModeChoices.YTD_RAW,
        IndicatorDisplayModeChoices.YTD_YOY,
    }:
        return IndicatorDisplayModeChoices.RAW
    return indicator_default_display_mode


class _DayEventValueTriplet(NamedTuple):
    """Current / previous / change values for one day-event card."""

    current: float | None
    previous: float | None
    change: float | None


def _format_indicator_as_day_event(
    indicator: EconomicIndicatorInformationModel,
    *,
    indicator_default_display_mode: IndicatorDisplayModeChoices,
    indicator_value_triplet: _DayEventValueTriplet,
) -> _DayEvent:
    """Build one publication day-event card from a formatted value triplet."""
    shared_amount_magnitude = (
        get_shared_amount_magnitude(
            current=indicator_value_triplet.current,
            previous=indicator_value_triplet.previous,
            change=indicator_value_triplet.change,
            base_unit=indicator.base_unit,
        )
        if indicator_default_display_mode
        in {
            IndicatorDisplayModeChoices.RAW,
            IndicatorDisplayModeChoices.YTD_RAW,
        }
        else None
    )
    formatted_value_change = _format_day_event_change(
        indicator_value_triplet.change,
        base_unit=indicator.base_unit,
        base_currency=indicator.base_currency,
        mode=indicator_default_display_mode,
        amount_magnitude=shared_amount_magnitude,
    )
    return _DayEvent(
        name=indicator.series_label,
        location=str(EconomicDataLocationChoices(indicator.location).label),
        mode=indicator_default_display_mode.value,
        value=format_indicator_value(
            indicator_value_triplet.current,
            base_unit=indicator.base_unit,
            base_currency=indicator.base_currency,
            mode=indicator_default_display_mode,
            include_unit_label=True,
            digits=2,
            amount_magnitude=shared_amount_magnitude,
        ),
        previous=format_indicator_value(
            indicator_value_triplet.previous,
            base_unit=indicator.base_unit,
            base_currency=indicator.base_currency,
            mode=indicator_default_display_mode,
            include_unit_label=True,
            digits=2,
            amount_magnitude=shared_amount_magnitude,
        ),
        change=formatted_value_change.change,
        change_class=formatted_value_change.change_class,
        is_holiday=False,
    )


def _format_publication_schedule_as_day_event(
    publication_schedule: PublicationScheduleModel,
) -> _DayEvent:
    """Format one publication schedule as a market-recap day-event card."""
    indicator = publication_schedule.indicator
    indicator_default_display_mode = IndicatorDisplayModeChoices(indicator.default_mode)
    indicator_frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
    economic_data_time_series = _list_timed_values_for_day_event_display_mode(
        _get_economic_data_time_series_for_day_event(
            indicator,
            indicator_default_display_mode=indicator_default_display_mode,
            indicator_frequency=indicator_frequency,
        ),
        indicator_default_display_mode=indicator_default_display_mode,
        indicator_frequency=indicator_frequency,
    )
    indicator_value_triplet = change_triplet_values_for_mode(
        economic_data_time_series,
        frequency=indicator_frequency,
        mode=_get_day_event_triplet_mode(indicator_default_display_mode),
    )
    return _format_indicator_as_day_event(
        indicator,
        indicator_default_display_mode=indicator_default_display_mode,
        indicator_value_triplet=_DayEventValueTriplet(
            current=indicator_value_triplet.current,
            previous=indicator_value_triplet.previous,
            change=indicator_value_triplet.change,
        ),
    )


def _get_day_publication_events(event_date: date) -> list[_DayEvent]:
    """Return economic releases scheduled for 'event_date' (display TZ)."""
    day_events: list[_DayEvent] = []
    for publication_schedule in _list_publication_schedules_near_event_date(event_date):
        if not _does_publication_schedule_match_event_date(
            publication_schedule, event_date
        ):
            continue
        day_events.append(
            _format_publication_schedule_as_day_event(publication_schedule)
        )
    return day_events


def _get_day_central_bank_events(event_date: date) -> list[_DayEvent]:
    """Return key interest rates for monetary-policy decisions on 'event_date'.

    On a meeting day, emit one card per key rate (current / previous / change)
    instead of a generic 'Rates Decision' label.
    """
    day_events: list[_DayEvent] = []
    for decision_day_key_rate in get_decision_day_key_rates(event_date):
        location_label = str(
            LocationChoices(decision_day_key_rate["central_bank"].get_location()).label
        )
        formatted_value_change = _format_day_event_change(
            decision_day_key_rate["change_value"],
            base_unit=IndicatorBaseUnitChoices.PERCENT,
        )
        day_events.append(
            _DayEvent(
                name=decision_day_key_rate["full_name"],
                location=location_label,
                mode="",
                value=format_indicator_value(
                    decision_day_key_rate["current_value"],
                    base_unit=IndicatorBaseUnitChoices.PERCENT,
                    include_unit_label=True,
                    digits=2,
                ),
                previous=format_indicator_value(
                    decision_day_key_rate["previous_value"],
                    base_unit=IndicatorBaseUnitChoices.PERCENT,
                    include_unit_label=True,
                    digits=2,
                ),
                change=formatted_value_change.change,
                change_class=formatted_value_change.change_class,
                is_holiday=False,
            )
        )
    return day_events


def _does_earnings_announcement_match_event_date(
    announcement_datetime: datetime | None,
    event_date: date,
) -> bool:
    """Return whether an earnings announcement falls on 'event_date' in display TZ."""
    if announcement_datetime is None:
        return False
    return convert_to_display_timezone(announcement_datetime).date() == event_date


def _format_earnings_eps_value(eps_value: float | None) -> str:
    """Format an EPS figure for the market-recap day-event card."""
    if eps_value is None:
        return ""
    return f"{eps_value:.2f}"


def _get_day_event_for_earnings_announcement(
    earnings_watchlist: EarningsWatchlistModel,
    *,
    eps_actual: float | None,
    eps_expected: float | None,
) -> _DayEvent:
    """Return a market-recap day event for one earnings announcement."""
    location = earnings.get_location_for_earnings_watchlist(earnings_watchlist)
    surprise: float | None = None
    if eps_actual is not None and eps_expected is not None:
        surprise = eps_actual - eps_expected
    formatted_surprise = _format_day_event_change(surprise)
    return _DayEvent(
        name=f"{earnings_watchlist.company} earnings",
        location=str(location.label),
        mode="EPS",
        value=_format_earnings_eps_value(eps_actual),
        previous=_format_earnings_eps_value(eps_expected),
        change=formatted_surprise.change,
        change_class=formatted_surprise.change_class,
        is_holiday=False,
    )


def _get_day_earnings_events(event_date: date) -> list[_DayEvent]:
    """Return watchlist earnings announcements that fall on 'event_date'."""
    lookback_utc = datetime.combine(
        event_date - timedelta(days=1), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    window_end_utc = datetime.combine(event_date, datetime.max.time()).replace(
        tzinfo=timezone.utc
    )
    day_events: list[_DayEvent] = []
    for (
        earnings_watchlist
    ) in earnings.list_earnings_watchlist_models_for_announcement_window(
        lookback_utc,
        window_end_utc,
    ):
        if _does_earnings_announcement_match_event_date(
            earnings_watchlist.upcoming_announcement_datetime,
            event_date,
        ):
            day_events.append(
                _get_day_event_for_earnings_announcement(
                    earnings_watchlist,
                    eps_actual=None,
                    eps_expected=earnings_watchlist.upcoming_eps_expected,
                )
            )
    return day_events


def get_day_events_grouped_by_location(
    event_date: date,
) -> list[_DayEventsLocationGroup]:
    """Build same-day economic releases for the market recap card by location.

    Holidays are listed first within each location. Returns an empty list when
    there are no major events that day (UI shows "No major event").
    """
    events_by_location: dict[str, list[_DayEvent]] = {}
    for day_event in (
        _get_day_holiday_events(event_date)
        + _get_day_publication_events(event_date)
        + _get_day_central_bank_events(event_date)
        + _get_day_earnings_events(event_date)
    ):
        events_by_location.setdefault(day_event["location"], []).append(day_event)

    result: list[_DayEventsLocationGroup] = []
    for location in LocationChoices.ordered():
        location_label = str(location.label)
        location_events = events_by_location.pop(location_label, None)
        if not location_events:
            continue
        location_events.sort(
            key=lambda event: (not event["is_holiday"], event["name"].lower())
        )
        result.append(
            _DayEventsLocationGroup(location=location_label, events=location_events)
        )
    for location_label in sorted(events_by_location.keys()):
        location_events = events_by_location[location_label]
        location_events.sort(
            key=lambda event: (not event["is_holiday"], event["name"].lower())
        )
        result.append(
            _DayEventsLocationGroup(location=location_label, events=location_events)
        )
    return result
