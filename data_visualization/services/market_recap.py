"""Build market recap payloads for the visualization UI."""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Literal, NamedTuple, TypedDict

import pandas as pd

import central_banks_overview.services.central_banks_meetings as central_banks_meetings
import market_overview.services.holidays as holidays
from central_banks_overview.models import CENTRAL_BANK_LOCATION_MAP, CentralBankChoices
from core.services import convert_to_display_timezone, get_local_today
from economic_overview.models import (
    EconomicDataLocationChoices,
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


class UpcomingEvent(TypedDict):
    """Single upcoming calendar event for the market recap sidebar."""

    name: str
    location: str  # Display label (Choices.label), not the stored code
    publication_date: datetime
    time_str: str


class UpcomingEventGroup(TypedDict):
    """Upcoming events for a single calendar day."""

    date: str
    date_display: str
    events: list[UpcomingEvent]


def _get_upcoming_events_from_publication_schedules(
    start_date: date,
) -> dict[str, list[UpcomingEvent]]:
    """Get upcoming events from publication schedules."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    upcoming_schedules = (
        PublicationScheduleModel.objects.filter(
            current_publication_date__gte=start_date
        )
        .select_related("indicator")
        .order_by("next_publication_date")[:100]
    )

    for schedule in upcoming_schedules:
        publication_date = schedule.current_publication_date
        if not publication_date:
            continue

        display_dt = convert_to_display_timezone(publication_date)
        event = UpcomingEvent(
            name=schedule.indicator.type,
            location=str(
                EconomicDataLocationChoices(schedule.indicator.location).label
            ),
            publication_date=publication_date,
            time_str=display_dt.strftime("%H:%M"),
        )

        date_key = display_dt.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_central_bank_events() -> dict[str, list[UpcomingEvent]]:
    """Get upcoming central bank events."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    for (
        central_bank_meeting_date
    ) in central_banks_meetings.get_central_bank_meeting_dates():
        central_bank = CentralBankChoices(central_bank_meeting_date["central_bank"])
        central_bank_location = CENTRAL_BANK_LOCATION_MAP[central_bank]
        meeting_date = central_bank_meeting_date["meeting_dates"][0]
        display_dt = convert_to_display_timezone(meeting_date)

        event = UpcomingEvent(
            name=f"{central_bank.label} Rates Decision",
            location=str(EconomicDataLocationChoices(central_bank_location).label),
            publication_date=meeting_date,
            time_str=display_dt.strftime("%H:%M"),
        )

        date_key = display_dt.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    return events_by_date


def _get_upcoming_holidays_events(start_date: date) -> dict[str, list[UpcomingEvent]]:
    """Get upcoming holidays events."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    current_month = start_date.month
    current_year = start_date.year
    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year if current_month < 12 else current_year + 1

    for location in HOLIDAY_COUNTRIES:
        current_month_holidays = holidays.get_holidays(
            location=location,
            year=current_year,
            months=[current_month],
        )
        next_month_holidays = holidays.get_holidays(
            location=location,
            year=next_year,
            months=[next_month],
        )

        for holiday in list(current_month_holidays) + list(next_month_holidays):
            if holiday.date < start_date:
                continue

            holiday_datetime = datetime.combine(
                holiday.date, datetime.min.time()
            ).replace(tzinfo=timezone.utc)

            event = UpcomingEvent(
                name=holiday.name,
                location=str(LocationChoices(holiday.location).label),
                publication_date=holiday_datetime,
                time_str="HOLIDAYS",
            )

            date_key = holiday.date.strftime("%Y-%m-%d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)

    return events_by_date


def _merge_events_by_date(
    base: dict[str, list[UpcomingEvent]],
    new: dict[str, list[UpcomingEvent]],
) -> dict[str, list[UpcomingEvent]]:
    """Merge events dictionaries by extending lists when keys exist."""
    for date_key, events in new.items():
        if date_key in base:
            base[date_key].extend(events)
        else:
            base[date_key] = events
    return base


def _get_upcoming_events() -> list[UpcomingEventGroup]:
    """Build day-level upcoming events for the market recap sidebar."""
    events_by_date: dict[str, list[UpcomingEvent]] = {}
    today = get_local_today()

    _merge_events_by_date(
        events_by_date, _get_upcoming_events_from_publication_schedules(today)
    )
    _merge_events_by_date(events_by_date, _get_upcoming_central_bank_events())
    _merge_events_by_date(events_by_date, _get_upcoming_holidays_events(today))
    upcoming_events: list[UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        events_for_date = sorted(
            events_by_date[date_key], key=lambda event: event["publication_date"]
        )

        display_dt = convert_to_display_timezone(events_for_date[0]["publication_date"])
        date_group: UpcomingEventGroup = {
            "date": date_key,
            "date_display": display_dt.strftime("%a %d %b"),
            "events": events_for_date,
        }
        upcoming_events.append(date_group)

    return upcoming_events


class UpcomingWeekGroup(TypedDict):
    """Upcoming events grouped by ISO week (Mon–Fri label)."""

    week_start: str
    week_label: str
    is_current_week: bool
    days: list[UpcomingEventGroup]


def _get_week_start_date(day: date) -> date:
    """Return Monday of the ISO week containing day."""
    return day - timedelta(days=day.weekday())


def _get_focus_week_start(today: date) -> date:
    """Monday of the week to show when the events card is collapsed.

    Mon–Fri: current ISO week. Sat–Sun (after Friday): next Monday's week.
    """
    if today.weekday() >= 5:  # Saturday or Sunday
        return today + timedelta(days=(7 - today.weekday()))
    return _get_week_start_date(today)


def _format_week_label(week_start: date) -> str:
    """Mon–Fri date range label without a 'Week of' prefix."""
    week_friday = week_start + timedelta(days=4)
    return f"{week_start.strftime('%d %b %Y')}" f" – {week_friday.strftime('%d %b %Y')}"


def group_upcoming_events_by_week(
    upcoming_events: list[UpcomingEventGroup] | None = None,
    today: date | None = None,
) -> list[UpcomingWeekGroup]:
    """Group day-level upcoming events into ISO weeks.

    Always includes the focus week (even when empty) so the collapsed card
    still shows Mon–Fri of the current (or next, after Friday) week.
    """
    if upcoming_events is None:
        upcoming_events = _get_upcoming_events()
    if today is None:
        today = get_local_today()

    focus_week_start = _get_focus_week_start(today)
    weeks: dict[date, list[UpcomingEventGroup]] = {}
    for day_group in upcoming_events:
        day = date.fromisoformat(day_group["date"])
        week_start = _get_week_start_date(day)
        weeks.setdefault(week_start, []).append(day_group)

    # Ensure the focus week is always present for the collapsed view.
    weeks.setdefault(focus_week_start, [])

    result: list[UpcomingWeekGroup] = []
    for week_start in sorted(weeks.keys()):
        result.append(
            {
                "week_start": week_start.isoformat(),
                "week_label": _format_week_label(week_start),
                "is_current_week": week_start == focus_week_start,
                "days": weeks[week_start],
            }
        )
    return result
