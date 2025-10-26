from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, TypedDict

import pandas as pd
from dateutil.relativedelta import relativedelta

import market_overview.services as market_overview_services
from economic_overview.models import (
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicIndicatorInformationModel,
    PublicationScheduleModel,
)
from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)
from market_overview.services import AssetNames, calculate_price_change


class LocationEnum(str, Enum):
    """Location Enum."""

    NA = "North America"
    EU = "Europe"
    ASIA = "Asia"
    NO_LOCATION = "No Location"


class DisplayAsset(TypedDict):
    """Display asset dictionnary."""

    country: LocationChoices
    asset: str
    name: str
    maturity: Optional[float]
    price: Optional[float]
    previous_price: Optional[float]
    price_change: Optional[float]
    price_change_pct: Optional[float]


class DisplayAssetbyLocation(TypedDict):
    """Display asset classes dictionnary."""

    location: LocationEnum
    assets: List[DisplayAsset]


class DisplayData(TypedDict):
    """Display data dictionnary."""

    asset_class: AssetClassChoices
    locations: List[DisplayAssetbyLocation]


LOCATION_MAPPING = {
    LocationEnum.NA: [LocationChoices.US],
    LocationEnum.EU: [
        LocationChoices.EU,
        LocationChoices.DE,
        LocationChoices.FR,
    ],
    LocationEnum.ASIA: [LocationChoices.JP],
}


def get_asset_full_name(asset_names: List[AssetNames], asset_short_name) -> str:
    """Get asset full_name."""
    return next(
        (
            asset["full_name"]
            for asset in asset_names
            if asset["short_name"] == asset_short_name
        ),
        None,
    )


def _build_assets(group: pd.DataFrame) -> List[DisplayAsset]:
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
        location_order=group["location"].map(location_order).fillna(999)
    ).sort_values(["location_order", "maturity"], na_position="last")


def format_data_for_market_recap_display(
    reference_market_prices: List[MarketPriceModel],
    previous_market_prices: List[MarketPriceModel],
) -> List[DisplayData]:
    """Format market price data for structured display."""
    price_diff = calculate_price_change(reference_market_prices, previous_market_prices)
    df = pd.DataFrame(price_diff).replace({float("nan"): None})

    # Map countries to location groups
    country_to_location = {
        country: loc.value
        for loc, countries in LOCATION_MAPPING.items()
        for country in countries
    }
    df["location_group"] = (
        df["location"].map(country_to_location).fillna(LocationEnum.NO_LOCATION.value)
    )
    df = df.sort_values(by="asset_id")

    data_to_display: List[DisplayData] = []
    for asset_class, asset_group in df.groupby("asset_class", sort=False):
        locations = []
        for location_group, loc_group in asset_group.groupby(
            "location_group", sort=False
        ):
            sorted_group = _sort_by_location_and_maturity(loc_group, location_group)
            assets = _build_assets(sorted_group)
            if assets:
                locations.append(
                    DisplayAssetbyLocation(location=location_group, assets=assets)
                )
        if locations:
            data_to_display.append(
                DisplayData(
                    asset_class=AssetClassChoices(asset_class).label,
                    locations=locations,
                )
            )

    return data_to_display


class ChartDuration(str, Enum):
    """Chart duration."""

    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    YEAR_TO_DATE = "YTD"
    ONE_YEAR = "1Y"


def _get_start_date(reference_date: date, chart_duration: ChartDuration) -> date:
    """Get start date for data."""
    if chart_duration == ChartDuration.ONE_WEEK:
        return reference_date - timedelta(weeks=1)
    elif chart_duration == ChartDuration.ONE_MONTH:
        return reference_date - relativedelta(months=1)
    elif chart_duration == ChartDuration.YEAR_TO_DATE:
        return reference_date - relativedelta(days=365)
    elif chart_duration == ChartDuration.ONE_YEAR:
        return reference_date - relativedelta(years=1)
    else:
        return reference_date


class MarketChartsDropdownValues(TypedDict):
    """Dropdown values."""

    stocks: list[str]
    fx: list[str]
    crypto: list[str]
    commodity: list[str]
    rates: list[str]
    locations: list[str]


def get_market_charts_dropdown_values() -> MarketChartsDropdownValues:
    """Get dropdown values."""
    asset_classes = {
        "stocks": {"asset_class": AssetClassChoices.STOCKS},
        "fx": {"asset_class": AssetClassChoices.FX},
        "crypto": {"asset_class": AssetClassChoices.CRYPTO},
        "commodity": {"asset_class": AssetClassChoices.COMMODITIES},
        "rates": {"asset_type": AssetTypeChoices.GOVERNMENT_BOND_RATE},
    }
    dropdown_values = {
        name: market_overview_services.get_asset_names(filters)
        for name, filters in asset_classes.items()
    }
    dropdown_values["locations"] = [str(choice.label) for choice in LocationChoices]
    return dropdown_values


class MarketChartsFrontData(TypedDict):
    """Front data."""

    reference_date: date
    previous_curve_date: date
    yield_curve_location: str
    stock_name: str
    fx_name: str
    crypto_name: str
    commodity_name: str
    main_rate: str
    spread_rate: str
    stock_chart_duration: ChartDuration
    fx_chart_duration: ChartDuration
    crypto_chart_duration: ChartDuration
    commodity_chart_duration: ChartDuration
    spread_rates_chart_duration: ChartDuration
    stock_name_compare: str
    fx_name_compare: str
    crypto_name_compare: str
    commodity_name_compare: str


class MarketChartsLabels(TypedDict):
    """Labels."""

    stocks: str
    fx: str
    crypto: str
    commodity: str
    yield_curve_location: str
    main_rate: str
    spread_rate: str
    stock_name_compare: Optional[str]
    fx_name_compare: Optional[str]
    crypto_name_compare: Optional[str]
    commodity_name_compare: Optional[str]


def get_market_charts_labels(
    dropdown_values: MarketChartsDropdownValues, front_data: MarketChartsFrontData
) -> MarketChartsLabels:
    """Get labels."""

    def _generic_asset_label_getter(
        asset_class: str, asset_name: Optional[str]
    ) -> Optional[str]:
        return (
            get_asset_full_name(dropdown_values[asset_class], asset_name)
            if asset_name
            else None
        )

    return {
        "stocks": _generic_asset_label_getter("stocks", front_data["stock_name"]),
        "fx": _generic_asset_label_getter("fx", front_data["fx_name"]),
        "crypto": _generic_asset_label_getter("crypto", front_data["crypto_name"]),
        "commodity": _generic_asset_label_getter(
            "commodity", front_data["commodity_name"]
        ),
        "yield_curve_location": front_data["yield_curve_location"],
        "main_rate": front_data["main_rate"],
        "spread_rate": front_data["spread_rate"],
        "stock_name_compare": _generic_asset_label_getter(
            "stocks", front_data["stock_name_compare"]
        ),
        "fx_name_compare": _generic_asset_label_getter(
            "fx", front_data["fx_name_compare"]
        ),
        "crypto_name_compare": _generic_asset_label_getter(
            "crypto", front_data["crypto_name_compare"]
        ),
        "commodity_name_compare": _generic_asset_label_getter(
            "commodity", front_data["commodity_name_compare"]
        ),
    }


class MarketChartsMarketData(TypedDict):
    """Market data."""

    stock_prices: list[dict]
    stock_prices_compare: list[dict]
    fx_prices: list[dict]
    fx_prices_compare: list[dict]
    crypto_prices: list[dict]
    crypto_prices_compare: list[dict]
    commodity_prices: list[dict]
    commodity_prices_compare: list[dict]
    reference_yield_curve: list[dict]
    previous_yield_curve: list[dict]
    spread_rates: list[dict]


def get_market_charts_market_data(
    reference_date: date, previous_curve_date: date, front_data: MarketChartsFrontData
) -> MarketChartsMarketData:
    """Get market data."""
    main_rate_historical_yield = market_overview_services.get_historical_prices(
        front_data["main_rate"],
        start_date=_get_start_date(
            reference_date, front_data["spread_rates_chart_duration"]
        ),
        end_date=reference_date,
    )
    spread_rate_historical_yield = market_overview_services.get_historical_prices(
        front_data["spread_rate"],
        start_date=_get_start_date(
            reference_date, front_data["spread_rates_chart_duration"]
        ),
        end_date=reference_date,
    )
    spread_rate_df = pd.merge(
        pd.DataFrame(main_rate_historical_yield),
        pd.DataFrame(spread_rate_historical_yield),
        on="price_date",
        how="left",
        suffixes=("_current", "_prev"),
    )
    spread_rate_df["price"] = (
        spread_rate_df["price_current"] - spread_rate_df["price_prev"]
    )
    return {
        "stock_prices": market_overview_services.get_historical_prices(
            front_data["stock_name"],
            start_date=_get_start_date(
                reference_date, front_data["stock_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "stock_prices_compare": (
            market_overview_services.get_historical_prices(
                front_data["stock_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["stock_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["stock_name_compare"]
            else None
        ),
        "fx_prices": market_overview_services.get_historical_prices(
            front_data["fx_name"],
            start_date=_get_start_date(reference_date, front_data["fx_chart_duration"]),
            end_date=reference_date,
        ),
        "fx_prices_compare": (
            market_overview_services.get_historical_prices(
                front_data["fx_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["fx_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["fx_name_compare"]
            else None
        ),
        "crypto_prices": market_overview_services.get_historical_prices(
            front_data["crypto_name"],
            start_date=_get_start_date(
                reference_date, front_data["crypto_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "crypto_prices_compare": (
            market_overview_services.get_historical_prices(
                front_data["crypto_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["crypto_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["crypto_name_compare"]
            else None
        ),
        "commodity_prices": market_overview_services.get_historical_prices(
            front_data["commodity_name"],
            start_date=_get_start_date(
                reference_date, front_data["commodity_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "commodity_prices_compare": (
            market_overview_services.get_historical_prices(
                front_data["commodity_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["commodity_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["commodity_name_compare"]
            else None
        ),
        "reference_yield_curve": market_overview_services.get_yield_curve(
            reference_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "previous_yield_curve": market_overview_services.get_yield_curve(
            previous_curve_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "spread_rates": spread_rate_df[["price_date", "price"]].to_dict(
            orient="records"
        ),
    }


class EconomicRecapItem(TypedDict):
    """Economic recap item."""

    category: str
    location: str
    name: str
    last: Optional[float]
    previous: Optional[float]
    change: Optional[float]
    period: Optional[str]


def get_economic_recap_data(locations: List[str]) -> Dict[str, List[EconomicRecapItem]]:
    """Get economic recap data."""
    indicators = EconomicIndicatorInformationModel.objects.all()
    economic_data: Dict[str, List[EconomicRecapItem]] = {}

    for indicator in indicators:
        category = indicator.category
        if category not in economic_data:
            economic_data[category] = []

        for location in locations:
            # Fetch the 2 most recent records
            records = list(
                EconomicDataModel.objects.filter(
                    indicator=indicator,
                    indicator__location=location,
                ).order_by("-period")[:2]
            )

            last, prev = (records + [None, None])[:2]
            last_value = getattr(last, "data_value", None)
            prev_value = getattr(prev, "data_value", None)
            period = last.get_period_display() if last else None
            change = (
                last_value - prev_value
                if last_value is not None and prev_value is not None
                else None
            )

            economic_data[category].append(
                EconomicRecapItem(
                    category=category,
                    location=location,
                    name=indicator.type,
                    last=last_value,
                    previous=prev_value,
                    change=change,
                    period=period,
                )
            )

    return economic_data


class EconomicEvent(TypedDict):
    """Economic event."""

    name: str
    location: str
    publish_datetime: datetime
    time_str: str


class UpcomingEventGroup(TypedDict):
    """Upcoming event group."""

    date: str
    date_display: str
    events: List[EconomicEvent]


def get_economic_recap_upcoming_events() -> List[UpcomingEventGroup]:
    """Get economic recap upcoming events from publication schedules."""
    upcoming_schedules = (
        PublicationScheduleModel.objects.filter(next_publication_date__gte=date.today())
        .select_related("indicator")
        .order_by("next_publication_date")[:100]
    )

    events_by_date: Dict[str, List[EconomicEvent]] = {}

    for schedule in upcoming_schedules:
        publication_date = schedule.current_publication_date
        if not publication_date:
            continue

        # Default to 9:00 AM if no time provided
        publish_datetime = datetime.combine(
            publication_date, datetime.min.time().replace(hour=9)
        )

        event = EconomicEvent(
            name=schedule.indicator.type,
            location=EconomicDataLocationChoices(schedule.indicator.location).label,
            publish_datetime=publish_datetime,
            time_str=publish_datetime.strftime("%H:%M"),
        )

        date_key = publication_date.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    upcoming_events: List[UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        events_for_date = sorted(
            events_by_date[date_key], key=lambda event: event["publish_datetime"]
        )

        date_group: UpcomingEventGroup = {
            "date": date_key,
            "date_display": events_for_date[0]["publish_datetime"].strftime("%Y-%m-%d"),
            "events": events_for_date,
        }
        upcoming_events.append(date_group)

    return upcoming_events
