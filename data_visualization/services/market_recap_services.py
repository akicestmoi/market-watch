from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union, cast

import pandas as pd

from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
)
from market_overview.services.market_data_services import calculate_price_change


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
    reference_market_prices: List[MarketPriceModel],
    previous_market_prices: List[MarketPriceModel],
) -> List[DisplayData]:
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


def _build_fx_price_dict(
    fx_prices: Dict[str, float], currencies: List[str]
) -> Dict[str, List[float]]:
    """Build a dictionary of FX prices for a matrix."""
    fx_dict: Dict[str, List[float]] = {}
    for base_currency in currencies:
        prices = []
        for quote_currency in currencies:
            if base_currency == quote_currency:
                prices.append(0.0)
                continue

            direct_pair = f"{base_currency}{quote_currency}"
            if direct_pair in fx_prices:
                prices.append(
                    fx_prices[direct_pair]
                    if fx_prices[direct_pair] is not None
                    else 0.0
                )
                continue

            inverted_pair = f"{quote_currency}{base_currency}"
            if inverted_pair in fx_prices:
                prices.append(
                    1.0 / fx_prices[inverted_pair]
                    if fx_prices[inverted_pair] is not None
                    else 0.0
                )
                continue

            prices.append(0.0)
        fx_dict[base_currency] = prices
    return fx_dict


def get_fx_prices_matrix(
    price_date: date,
    previous_price_date: date,
) -> List[Dict[str, Any]]:
    """Get FX prices matrix showing percentage change between two dates."""
    fx_prices_current = dict(
        MarketPriceModel.objects.filter(
            asset__asset_type=AssetTypeChoices.FX_SPOT_RATE,
            date=price_date,
        )
        .select_related("asset")
        .values_list("asset__short_name", "price")
    )
    fx_prices_previous = dict(
        MarketPriceModel.objects.filter(
            asset__asset_type=AssetTypeChoices.FX_SPOT_RATE,
            date=previous_price_date,
        )
        .select_related("asset")
        .values_list("asset__short_name", "price")
    )

    fx_dict_current = _build_fx_price_dict(fx_prices_current, FX_MATRIX_ORDER)
    fx_dict_previous = _build_fx_price_dict(fx_prices_previous, FX_MATRIX_ORDER)

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

    return fx_matrix.to_dict(orient="records")  # type: ignore[reportReturnType]
