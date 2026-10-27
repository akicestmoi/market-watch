"""Build market recap payloads for the visualization UI."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Literal, NamedTuple, TypedDict

import pandas as pd

import market_overview.services.holidays as holidays
from central_banks_overview.models import (
    CENTRAL_BANK_LOCATION_MAP,
    CentralBankChoices,
    CentralBankMeetingModel,
)
from core.services import convert_to_display_timezone
from economic_overview.models import (
    EconomicDataLocationChoices,
    EconomicDataModel,
    PublicationScheduleModel,
)
from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)
from market_overview.services.holidays import HOLIDAY_COUNTRIES
from market_overview.services.market_data import calculate_price_change

FX_PAIRS_FILTER = [
    "EURGBP",
    "EURCHF",
    "EURAUD",
    "EURCNY",
    "GBPJPY",
    "GBPCHF",
    "GBPAUD",
    "GBPCNY",
    "JPYCHF",
    "JPYAUD",
    "JPYCNY",
    "CHFAUD",
    "CHFCNY",
    "AUDCNY",
]
FX_MATRIX_ORDER = ["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CNY"]


class LocationEnum(str, Enum):
    """Location Enum."""

    NA = "North America"
    EU = "Europe"
    ASIA = "Asia"
    NO_LOCATION = "No Location"


class DisplayAsset(TypedDict):
    """Display asset dictionnary."""

    country: LocationChoices | Literal["-"]
    asset: str
    name: str
    maturity: float | None
    price: float | None
    previous_price: float | None
    price_change: float | None
    price_change_pct: float | None


class DisplayAssetbyLocation(TypedDict):
    """Display asset classes dictionnary."""

    location: str  # LocationEnum value (e.g. "North America")
    assets: list[DisplayAsset]


class DisplayData(TypedDict):
    """Display data dictionnary."""

    asset_class: str  # human-readable AssetClassChoices label
    locations: list[DisplayAssetbyLocation]


LOCATION_MAPPING = {
    LocationEnum.NA: [LocationChoices.US],
    LocationEnum.EU: [
        LocationChoices.EU,
        LocationChoices.DE,
        LocationChoices.FR,
    ],
    LocationEnum.ASIA: [LocationChoices.JP],
}


def _build_assets(group: pd.DataFrame) -> list[DisplayAsset]:
    """Helper to create DisplayAsset list from a DataFrame group."""
    return [
        DisplayAsset(
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
        for i, loc in enumerate(LOCATION_MAPPING.get(LocationEnum(location_group), []))
    }
    return group.assign(
        location_order=group["location"].map(lambda x: location_order.get(x, 999))
    ).sort_values(["location_order", "maturity"], na_position="last")


def format_data_for_market_recap_display(
    reference_market_prices: list[MarketPriceModel],
    previous_market_prices: list[MarketPriceModel],
) -> list[DisplayData]:
    """Format market price data for structured display."""
    price_diff = calculate_price_change(reference_market_prices, previous_market_prices)
    if not price_diff:
        # If there is a price, there should always be a price diff (None)
        # If no price diff, then there is no data to display
        return []

    df = pd.DataFrame(price_diff).replace({float("nan"): None})

    # Map countries to location groups
    country_to_location = {
        country: loc.value
        for loc, countries in LOCATION_MAPPING.items()
        for country in countries
    }
    df["location_group"] = df["location"].map(
        lambda x: country_to_location.get(x, LocationEnum.NO_LOCATION.value)
    )
    df = df.sort_values(by="asset_id")

    data_to_display: list[DisplayData] = []
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
                    DisplayAssetbyLocation(
                        location=LocationEnum(str(location_group)).value,
                        assets=assets,
                    )
                )
        if locations:
            data_to_display.append(
                DisplayData(
                    asset_class=str(AssetClassChoices(str(asset_class)).label),
                    locations=locations,
                )
            )

    return data_to_display


class FxCurrencyPrices(TypedDict, total=False):
    """Per-base-currency FX levels against ``FX_MATRIX_ORDER`` quotes."""

    EUR: list[float]
    USD: list[float]
    GBP: list[float]
    JPY: list[float]
    CHF: list[float]
    AUD: list[float]
    CNY: list[float]


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


class FxPairPrice(NamedTuple):
    """One FX spot pair price."""

    pair: str
    price: float


def _lookup_fx_pair_price(fx_prices: list[FxPairPrice], pair: str) -> float | None:
    """Return the price for an FX pair short name, if present."""
    for item in fx_prices:
        if item.pair == pair:
            return item.price
    return None


def _load_fx_pair_prices(price_date: date) -> list[FxPairPrice]:
    """Load FX spot prices for a date as pair/price rows."""
    rows: list[FxPairPrice] = []
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
        rows.append(FxPairPrice(pair=str(short_name), price=float(price)))
    return rows


def _assign_fx_currency_prices(
    fx_dict: FxCurrencyPrices, base_currency: str, prices: list[float]
) -> None:
    """Assign one base-currency price row onto a typed FX matrix dict."""
    if base_currency == "EUR":
        fx_dict["EUR"] = prices
    elif base_currency == "USD":
        fx_dict["USD"] = prices
    elif base_currency == "GBP":
        fx_dict["GBP"] = prices
    elif base_currency == "JPY":
        fx_dict["JPY"] = prices
    elif base_currency == "CHF":
        fx_dict["CHF"] = prices
    elif base_currency == "AUD":
        fx_dict["AUD"] = prices
    elif base_currency == "CNY":
        fx_dict["CNY"] = prices


def _build_fx_price_dict(
    fx_prices: list[FxPairPrice], currencies: list[str]
) -> FxCurrencyPrices:
    """Build a dictionary of FX prices for a matrix."""
    fx_dict: FxCurrencyPrices = {}
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
        _assign_fx_currency_prices(fx_dict, base_currency, prices)
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


class DayEvent(TypedDict):
    """Event that occurred on the market-recap target date."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
    value: str  # Formatted release value; empty for holidays / unknown
    is_holiday: bool


class DayEventsLocationGroup(TypedDict):
    """Same-day events for one location card."""

    location: str
    events: list[DayEvent]


def _format_day_event_value(data_value: float | None) -> str:
    """Format an economic release value for the day-events card."""
    if data_value is None:
        return ""
    if data_value == int(data_value):
        return str(int(data_value))
    return f"{data_value:.4f}".rstrip("0").rstrip(".")


def _get_day_holiday_events(event_date: date) -> list[DayEvent]:
    """Return holiday events that fall on ``event_date``."""
    day_events: list[DayEvent] = []
    for location in HOLIDAY_COUNTRIES:
        for holiday in holidays.get_holidays(
            location=location,
            year=event_date.year,
            months=[event_date.month],
        ):
            if holiday.date != event_date:
                continue
            day_events.append(
                DayEvent(
                    name=holiday.name,
                    location=str(LocationChoices(holiday.location).label),
                    value="",
                    is_holiday=True,
                )
            )
    return day_events


def _get_day_publication_events(event_date: date) -> list[DayEvent]:
    """Return economic releases scheduled for ``event_date`` (display TZ)."""
    day_start = datetime.combine(
        event_date - timedelta(days=1), datetime.min.time()
    ).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(
        event_date + timedelta(days=1), datetime.max.time()
    ).replace(tzinfo=timezone.utc)
    schedules = (
        PublicationScheduleModel.objects.filter(
            current_publication_date__gte=day_start,
            current_publication_date__lte=day_end,
        )
        .select_related("indicator")
        .order_by("indicator__location", "indicator__type")
    )

    day_events: list[DayEvent] = []
    for schedule in schedules:
        publication_date = schedule.current_publication_date
        if not publication_date:
            continue
        display_dt = convert_to_display_timezone(publication_date)
        if display_dt.date() != event_date:
            continue

        latest = (
            EconomicDataModel.objects.filter(indicator=schedule.indicator)
            .order_by("-period", "-last_modified")
            .first()
        )
        day_events.append(
            DayEvent(
                name=schedule.indicator.type,
                location=str(
                    EconomicDataLocationChoices(schedule.indicator.location).label
                ),
                value=_format_day_event_value(latest.data_value if latest else None),
                is_holiday=False,
            )
        )
    return day_events


def _get_day_central_bank_events(event_date: date) -> list[DayEvent]:
    """Return central-bank rate decisions that fall on ``event_date``."""
    day_events: list[DayEvent] = []
    for meeting in CentralBankMeetingModel.objects.all().order_by(
        "central_bank", "date"
    ):
        display_dt = convert_to_display_timezone(meeting.date)
        if display_dt.date() != event_date:
            continue
        central_bank = CentralBankChoices(meeting.central_bank)
        central_bank_location = CENTRAL_BANK_LOCATION_MAP[central_bank]
        day_events.append(
            DayEvent(
                name=f"{central_bank.label} Rates Decision",
                location=str(LocationChoices(central_bank_location).label),
                value="",
                is_holiday=False,
            )
        )
    return day_events


def get_day_events_grouped_by_location(
    event_date: date,
) -> list[DayEventsLocationGroup]:
    """Build same-day economic releases for the market recap card by location.

    Holidays are listed first within each location. Returns an empty list when
    there are no major events that day (UI shows "No major event").
    """
    events_by_location: dict[str, list[DayEvent]] = {}
    for day_event in (
        _get_day_holiday_events(event_date)
        + _get_day_publication_events(event_date)
        + _get_day_central_bank_events(event_date)
    ):
        events_by_location.setdefault(day_event["location"], []).append(day_event)

    result: list[DayEventsLocationGroup] = []
    for location in LocationChoices.ordered():
        location_label = str(location.label)
        location_events = events_by_location.pop(location_label, None)
        if not location_events:
            continue
        location_events.sort(
            key=lambda event: (not event["is_holiday"], event["name"].lower())
        )
        result.append(
            DayEventsLocationGroup(location=location_label, events=location_events)
        )
    for location_label in sorted(events_by_location.keys()):
        location_events = events_by_location[location_label]
        location_events.sort(
            key=lambda event: (not event["is_holiday"], event["name"].lower())
        )
        result.append(
            DayEventsLocationGroup(location=location_label, events=location_events)
        )
    return result
