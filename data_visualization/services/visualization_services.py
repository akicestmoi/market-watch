from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, List, Literal, Optional, TypedDict, Union, cast

import pandas as pd
from dateutil.relativedelta import relativedelta

import market_overview.services.market_data_services as market_data_services
from central_banks_overview.models import CENTRAL_BANK_LOCATION_MAP, CentralBankChoices
from central_banks_overview.services.cb_data_services import get_central_bank_data
from central_banks_overview.services.cb_inference_services import (
    CentralBankProbabilityMatrix,
    calculate_probability_changes,
    get_central_bank_effective_rate,
    get_central_bank_probability_matrices,
)
from central_banks_overview.services.cb_meetings_services import (
    get_central_bank_meeting_dates,
    get_central_bank_next_meeting_date,
)
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
from market_overview.services.market_data_services import (
    AssetNames,
    HistoricalPrice,
    YieldCurvePoint,
    calculate_price_change,
)


class LocationEnum(str, Enum):
    """Location Enum."""

    NA = "North America"
    EU = "Europe"
    ASIA = "Asia"
    NO_LOCATION = "No Location"


class DisplayAsset(TypedDict):
    """Display asset dictionnary."""

    country: Union[LocationChoices, Literal["-"]]
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


def get_asset_full_name(
    asset_names: List[AssetNames], asset_short_name
) -> Optional[str]:
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
        location_order=group["location"].map(lambda x: location_order.get(x, 999))
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
    df["location_group"] = df["location"].map(
        lambda x: country_to_location.get(x, LocationEnum.NO_LOCATION.value)
    )
    df = df.sort_values(by="asset_id")

    data_to_display: List[DisplayData] = []
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
                        location=cast(LocationEnum, LocationEnum(location_group).value),
                        assets=assets,
                    )
                )
        if locations:
            data_to_display.append(
                DisplayData(
                    asset_class=cast(
                        AssetClassChoices, AssetClassChoices(asset_class).label
                    ),
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

    stocks: List[AssetNames]
    fx: List[AssetNames]
    crypto: List[AssetNames]
    commodity: List[AssetNames]
    rates: List[AssetNames]
    locations: List[str]


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
        name: market_data_services.get_asset_names(filters)
        for name, filters in asset_classes.items()
    }
    locations = LocationChoices.get_labels()
    return MarketChartsDropdownValues(
        stocks=dropdown_values["stocks"],
        fx=dropdown_values["fx"],
        crypto=dropdown_values["crypto"],
        commodity=dropdown_values["commodity"],
        rates=dropdown_values["rates"],
        locations=locations,
    )


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

    stocks: Optional[str]
    fx: Optional[str]
    crypto: Optional[str]
    commodity: Optional[str]
    yield_curve_location: Optional[str]
    main_rate: Optional[str]
    spread_rate: Optional[str]
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

    stock_prices: List[HistoricalPrice]
    stock_prices_compare: List[HistoricalPrice]
    fx_prices: List[HistoricalPrice]
    fx_prices_compare: List[HistoricalPrice]
    crypto_prices: List[HistoricalPrice]
    crypto_prices_compare: List[HistoricalPrice]
    commodity_prices: List[HistoricalPrice]
    commodity_prices_compare: List[HistoricalPrice]
    reference_yield_curve: List[YieldCurvePoint]
    previous_yield_curve: List[YieldCurvePoint]
    spread_rates: List[HistoricalPrice]


def get_market_charts_market_data(
    reference_date: date, previous_curve_date: date, front_data: MarketChartsFrontData
) -> MarketChartsMarketData:
    """Get market data."""
    main_rate_historical_yield = market_data_services.get_historical_prices(
        front_data["main_rate"],
        start_date=_get_start_date(
            reference_date, front_data["spread_rates_chart_duration"]
        ),
        end_date=reference_date,
    )
    spread_rate_historical_yield = market_data_services.get_historical_prices(
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
    ) * 100
    spread_rates = cast(
        List[HistoricalPrice],
        spread_rate_df[["price_date", "price"]].to_dict(orient="records"),
    )
    return {
        "stock_prices": market_data_services.get_historical_prices(
            front_data["stock_name"],
            start_date=_get_start_date(
                reference_date, front_data["stock_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "stock_prices_compare": (
            market_data_services.get_historical_prices(
                front_data["stock_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["stock_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["stock_name_compare"]
            else []
        ),
        "fx_prices": market_data_services.get_historical_prices(
            front_data["fx_name"],
            start_date=_get_start_date(reference_date, front_data["fx_chart_duration"]),
            end_date=reference_date,
        ),
        "fx_prices_compare": (
            market_data_services.get_historical_prices(
                front_data["fx_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["fx_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["fx_name_compare"]
            else []
        ),
        "crypto_prices": market_data_services.get_historical_prices(
            front_data["crypto_name"],
            start_date=_get_start_date(
                reference_date, front_data["crypto_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "crypto_prices_compare": (
            market_data_services.get_historical_prices(
                front_data["crypto_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["crypto_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["crypto_name_compare"]
            else []
        ),
        "commodity_prices": market_data_services.get_historical_prices(
            front_data["commodity_name"],
            start_date=_get_start_date(
                reference_date, front_data["commodity_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "commodity_prices_compare": (
            market_data_services.get_historical_prices(
                front_data["commodity_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["commodity_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["commodity_name_compare"]
            else []
        ),
        "reference_yield_curve": market_data_services.get_yield_curve(
            reference_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "previous_yield_curve": market_data_services.get_yield_curve(
            previous_curve_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "spread_rates": spread_rates,
    }


class EconomicRecapItem(TypedDict):
    """Economic recap item."""

    category: str
    location: str
    name: str
    current: Optional[float]
    previous: Optional[float]
    change: Optional[float]
    period: Optional[str]


def get_economic_recap_data(locations: List[str]) -> Dict[str, List[EconomicRecapItem]]:
    """Get economic recap data."""
    indicators = EconomicIndicatorInformationModel.objects.all().order_by("id")
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

            curr, prev = (records + [None, None])[:2]
            curr_value = getattr(curr, "data_value", None)
            prev_value = getattr(prev, "data_value", None)
            period = curr.get_period_display() if curr else None
            change = (
                curr_value - prev_value
                if curr_value is not None and prev_value is not None
                else None
            )

            economic_data[category].append(
                EconomicRecapItem(
                    category=category,
                    location=location,
                    name=indicator.type,
                    current=curr_value,
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
    publication_date: datetime
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

        event = EconomicEvent(
            name=schedule.indicator.type,
            location=str(
                EconomicDataLocationChoices(schedule.indicator.location).label
            ),
            publication_date=publication_date,
            time_str=publication_date.strftime("%H:%M"),
        )

        date_key = publication_date.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    for central_bank_meeting_date in get_central_bank_meeting_dates():
        central_bank = CentralBankChoices(central_bank_meeting_date["central_bank"])
        central_bank_location = CENTRAL_BANK_LOCATION_MAP[central_bank]
        meeting_date = central_bank_meeting_date["meeting_dates"][0]

        event = EconomicEvent(
            name=f"{central_bank.label} Rates Decision",
            location=str(EconomicDataLocationChoices(central_bank_location).label),
            publication_date=meeting_date,
            time_str=meeting_date.strftime("%H:%M"),
        )

        date_key = meeting_date.strftime("%Y-%m-%d")
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    upcoming_events: List[UpcomingEventGroup] = []
    for date_key in sorted(events_by_date.keys()):
        events_for_date = sorted(
            events_by_date[date_key], key=lambda event: event["publication_date"]
        )

        date_group: UpcomingEventGroup = {
            "date": date_key,
            "date_display": events_for_date[0]["publication_date"].strftime("%Y-%m-%d"),
            "events": events_for_date,
        }
        upcoming_events.append(date_group)

    return upcoming_events


class CentralBankDataItem(TypedDict):
    """Central bank data item."""

    label: str
    value: str


def get_central_bank_data_item(
    central_bank: CentralBankChoices, reference_date: date
) -> List[CentralBankDataItem]:
    """Get central bank data item."""
    effective_rate = get_central_bank_effective_rate(central_bank, reference_date)
    next_meeting_date = get_central_bank_next_meeting_date(central_bank)
    next_meeting_date = (
        next_meeting_date.strftime("%Y-%m-%d") if next_meeting_date else "N/A"
    )
    data_items = [
        CentralBankDataItem(
            label=item.full_name, value=f"{item.value} %" if item.value else "N/A"
        )
        for item in get_central_bank_data(central_banks=[central_bank], last_value=True)
    ]

    base_data = [
        CentralBankDataItem(
            label="Effective Rate",
            value=f"{effective_rate} %" if effective_rate else "N/A",
        ),
        CentralBankDataItem(label="Next Meeting", value=next_meeting_date),
        *data_items,
    ]
    match central_bank:
        case CentralBankChoices.FRB:
            additional_data = [
                CentralBankDataItem(label="US Inflation Rate", value="3.0 %"),
            ]
        case CentralBankChoices.BOJ:
            additional_data = [
                CentralBankDataItem(label="Japan Inflation Rate", value="2.9 %"),
            ]
        case CentralBankChoices.ECB:
            additional_data = [
                CentralBankDataItem(label="France Inflation Rate", value="0.9 %"),
                CentralBankDataItem(label="Eurozone Inflation Rate", value="2.1 %"),
            ]
    return base_data + additional_data


def get_central_bank_formatted_probability_matrix(
    central_bank: CentralBankChoices,
    reference_date: date,
) -> Optional[CentralBankProbabilityMatrix]:
    """Get formatted probability matrix for a central bank."""
    if central_bank == CentralBankChoices.ECB:
        return None
    cb_probability_matrices = get_central_bank_probability_matrices(
        reference_date, [central_bank]
    )
    for prob_matrix in cb_probability_matrices:
        if prob_matrix["central_bank"] == central_bank:
            sorted_probability_matrix = sorted(
                prob_matrix["probability_matrix"],
                key=lambda x: x["expected_rate_step"],
            )
            return {
                "central_bank": prob_matrix["central_bank"],
                "meeting_dates": prob_matrix["meeting_dates"],
                "probability_matrix": sorted_probability_matrix,
            }


def get_formatted_probability_matrix_changes(
    probability_matrix: Optional[CentralBankProbabilityMatrix],
    previous_probability_matrix: Optional[CentralBankProbabilityMatrix],
) -> Optional[CentralBankProbabilityMatrix]:
    """Get formatted probability change matrix."""
    if not probability_matrix or not previous_probability_matrix:
        return None

    probability_change_matrix = calculate_probability_changes(
        probability_matrix, previous_probability_matrix
    )
    # Sort by expected_rate_step in ascending order
    sorted_probability_change_matrix = sorted(
        probability_change_matrix["probability_matrix"],
        key=lambda x: x["expected_rate_step"],
    )
    return {
        "central_bank": probability_change_matrix["central_bank"],
        "meeting_dates": probability_change_matrix["meeting_dates"],
        "probability_matrix": sorted_probability_change_matrix,
    }
