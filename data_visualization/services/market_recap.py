"""Build market recap payloads for the visualization UI."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Literal, NamedTuple, TypedDict

import pandas as pd
from django.db.models import Q

import market_overview.services.holidays as holidays
from central_banks_overview.services.central_banks_data import (
    get_decision_day_key_rates,
)
from core.services import convert_to_display_timezone
from data_visualization.services.config import (
    FX_MATRIX_ORDER,
    FX_PAIRS_FILTER,
    MarketRecapLocationEnum,
)
from data_visualization.services.economic_recap import format_indicator_value
from economic_overview.models import (
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicPublicationFrequencyChoices,
    IndicatorBaseUnitChoices,
    IndicatorDisplayModeChoices,
    PublicationScheduleModel,
)
from economic_overview.services.economic_data import (
    change_indicator_values_mode,
    get_lag_for_mode_change_calculation,
)
from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)
from market_overview.services.config import HOLIDAY_COUNTRIES
from market_overview.services.market_data import calculate_price_change


class _DisplayAsset(TypedDict):
    """Display asset dictionnary."""

    country: LocationChoices | Literal["-"]
    asset: str
    name: str
    maturity: float | None
    price: float | None
    previous_price: float | None
    price_change: float | None
    price_change_pct: float | None


class _DisplayAssetbyLocation(TypedDict):
    """Display asset classes dictionnary."""

    location: str  # MarketRecapLocationEnum value (e.g. "North America")
    assets: list[_DisplayAsset]


class _DisplayData(TypedDict):
    """Display data dictionnary."""

    asset_class: str  # human-readable AssetClassChoices label
    locations: list[_DisplayAssetbyLocation]


def _build_assets(group: pd.DataFrame) -> list[_DisplayAsset]:
    """Helper to create _DisplayAsset list from a DataFrame group."""
    return [
        _DisplayAsset(
            country=row["location"] if pd.notna(row["location"]) else "-",
            asset=row["short_name"],
            name=row["full_name"],
            maturity=row["maturity"],
            price=row["price"],
            previous_price=row["price_previous"],
            price_change=row["price_change"],
            price_change_pct=row["price_change_pct"],
        )
        for _, row in group.iterrows()
        if row["short_name"] not in FX_PAIRS_FILTER
    ]


def _sort_by_location_and_maturity(
    group: pd.DataFrame, location_group: str
) -> pd.DataFrame:
    """Helper to sort a location group by location order and maturity."""
    location_order = {
        loc.value: i
        for i, loc in enumerate(MarketRecapLocationEnum(location_group).get_locations())
    }
    return group.assign(
        location_order=group["location"].map(lambda x: location_order.get(x, 999))
    ).sort_values(["location_order", "maturity"], na_position="last")


def format_data_for_market_recap_display(
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
        country: location_group.value
        for location_group in MarketRecapLocationEnum
        for country in location_group.get_locations()
    }
    df["location_group"] = df["location"].map(
        lambda x: country_to_location.get(x, MarketRecapLocationEnum.NO_LOCATION.value)
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
            assets = _build_assets(sorted_group)
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


class FxMatrixRow(TypedDict):
    """One row of the FX % change matrix for the UI."""

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
    """Load FX spot prices for a date as pair/price rows."""
    rows: list[_FxPairPrice] = []
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
        rows.append(_FxPairPrice(pair=str(short_name), price=float(price)))
    return rows


def _build_fx_price_dict(
    fx_prices: list[_FxPairPrice], currencies: list[str]
) -> dict[str, list[float]]:
    """Build base→quote FX levels keyed by currency for ``pd.DataFrame``.

    Returns a ``dict`` (not a TypedDict): keys are the caller’s currency codes
    (typically ``FX_MATRIX_ORDER``) and are not a closed set at this boundary;
    values are quote-level rows in that same order. Pandas takes this mapping
    as column data before transpose in ``get_fx_prices_matrix``.
    """
    # Usage of dict: keys are FX matrix currency codes; values are quote-level
    # price rows in the same order as ``currencies``.
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
) -> list[FxMatrixRow]:
    """Get FX prices matrix showing percentage change between two dates."""
    fx_dict_current = _build_fx_price_dict(
        _load_fx_pair_prices(price_date), FX_MATRIX_ORDER
    )
    fx_dict_previous = _build_fx_price_dict(
        _load_fx_pair_prices(previous_price_date), FX_MATRIX_ORDER
    )

    # Transpose the dataframes to make the base currency the index and not the columns
    fx_df_current = pd.DataFrame(fx_dict_current, index=FX_MATRIX_ORDER).transpose()
    fx_df_previous = pd.DataFrame(fx_dict_previous, index=FX_MATRIX_ORDER).transpose()

    fx_matrix = (
        (fx_df_current - fx_df_previous)
        .divide(fx_df_previous)
        .where((fx_df_current != 0) & (fx_df_previous != 0), 0)
        .multiply(100)
    )
    fx_matrix = fx_matrix.fillna(0.0)
    fx_matrix["currency"] = FX_MATRIX_ORDER

    rows: list[FxMatrixRow] = []
    for _, row in fx_matrix.iterrows():
        rows.append(
            FxMatrixRow(
                currency=str(row["currency"]),
                EUR=float(row["EUR"]),
                USD=float(row["USD"]),
                GBP=float(row["GBP"]),
                JPY=float(row["JPY"]),
                CHF=float(row["CHF"]),
                AUD=float(row["AUD"]),
                CNY=float(row["CNY"]),
            )
        )
    return rows


class _DayEventChangeClass(str, Enum):
    """CSS modifier for day-event change direction."""

    POSITIVE = "is-positive"
    NEGATIVE = "is-negative"
    NONE = ""


class _DayEvent(TypedDict):
    """Event that occurred on the market-recap target date."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
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
        change=formatted_magnitude,
        change_class=_DayEventChangeClass.NONE,
    )


def _get_day_holiday_events(event_date: date) -> list[_DayEvent]:
    """Return holiday events that fall on ``event_date``."""
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
    """True when current or previous publication falls on ``event_date`` (display TZ).

    After ingest, a just-released print often moves from ``current`` to
    ``previous`` while ``current`` advances to the next slot — both must count.
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


def _get_day_publication_events(event_date: date) -> list[_DayEvent]:
    """Return economic releases scheduled for ``event_date`` (display TZ)."""
    day_start = datetime.combine(
        event_date - timedelta(days=1), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(
        event_date + timedelta(days=1), datetime.max.time()
    ).replace(tzinfo=timezone.utc)
    schedules = (
        PublicationScheduleModel.objects.filter(
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
        .order_by("indicator__location", "indicator__type")
    )

    day_events: list[_DayEvent] = []
    for publication_schedule in schedules:
        if not _does_publication_schedule_match_event_date(
            publication_schedule, event_date
        ):
            continue

        indicator = publication_schedule.indicator
        indicator_default_display_mode = IndicatorDisplayModeChoices(
            indicator.default_mode
        )
        indicator_frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
        time_series_max_period = (
            get_lag_for_mode_change_calculation(
                indicator_frequency, indicator_default_display_mode
            )
            + 2
        )
        economic_data_time_series = [
            float(time_series_point.data_value)
            for time_series_point in EconomicDataModel.objects.filter(
                indicator=indicator,
                data_value__isnull=False,
                period__isnull=False,
            ).order_by("-period", "-last_modified")[:time_series_max_period]
            if time_series_point.data_value is not None
        ]
        indicator_value_triplet = change_indicator_values_mode(
            economic_data_time_series,
            frequency=indicator_frequency,
            mode=indicator_default_display_mode,
        )
        formatted_value_change = _format_day_event_change(
            indicator_value_triplet.change,
            base_unit=indicator.base_unit,
            base_currency=indicator.base_currency,
            mode=indicator_default_display_mode,
        )
        day_events.append(
            _DayEvent(
                name=indicator.type,
                location=str(EconomicDataLocationChoices(indicator.location).label),
                value=format_indicator_value(
                    indicator_value_triplet.current,
                    base_unit=indicator.base_unit,
                    base_currency=indicator.base_currency,
                    mode=indicator_default_display_mode,
                    include_unit_label=True,
                    digits=2,
                ),
                previous=format_indicator_value(
                    indicator_value_triplet.previous,
                    base_unit=indicator.base_unit,
                    base_currency=indicator.base_currency,
                    mode=indicator_default_display_mode,
                    include_unit_label=True,
                    digits=2,
                ),
                change=formatted_value_change.change,
                change_class=formatted_value_change.change_class,
                is_holiday=False,
            )
        )
    return day_events


def _get_day_central_bank_events(event_date: date) -> list[_DayEvent]:
    """Return key interest rates for monetary-policy decisions on ``event_date``.

    On a meeting day, emit one card per key rate (current / previous / change)
    instead of a generic ``Rates Decision`` label.
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
