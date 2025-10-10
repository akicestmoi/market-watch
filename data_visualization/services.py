from enum import Enum
from typing import List, Optional, TypedDict

import pandas as pd
from pandas.api.types import CategoricalDtype

from market_overview.models import AssetClassChoices, LocationChoices, MarketPriceModel
from market_overview.services import calculate_price_change


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


def format_data_for_display(
    reference_market_prices: List[MarketPriceModel],
    previous_market_prices: List[MarketPriceModel],
) -> List[DisplayData]:
    """Format data to be used for display."""
    df = calculate_price_change(reference_market_prices, previous_market_prices)

    country_to_location = {
        country: loc.value
        for loc, countries in LOCATION_MAPPING.items()
        for country in countries
    }
    location_group_categories = CategoricalDtype(
        categories=[loc.value for loc in LocationEnum], ordered=True
    )
    location_categories = CategoricalDtype(
        categories=[loc for loc in LocationChoices], ordered=True
    )
    asset_class_categories = CategoricalDtype(
        categories=[loc for loc in AssetClassChoices], ordered=True
    )
    df["location_group"] = (
        df["location"].map(country_to_location).fillna(LocationEnum.NO_LOCATION)
    )
    df = df.astype(
        {
            "location": location_categories,
            "asset_class": asset_class_categories,
            "location_group": location_group_categories,
        }
    )

    data_to_display = []
    for asset_class, group_location in df.groupby("asset_class", sort=False):
        locations = []
        for location, group_class in group_location.groupby(
            "location_group", sort=False
        ):
            assets = [
                DisplayAsset(
                    country=(
                        row["location"].label if not pd.isna(row["location"]) else "-"
                    ),
                    asset=row["short_name"],
                    name=row["full_name"],
                    maturity=row["maturity"],
                    price=row["price"],
                    previous_price=row["price_previous"],
                    price_change=row["price_change"],
                    price_change_pct=row["price_change_pct"],
                )
                for _, row in group_class.sort_values(
                    ["location", "maturity"], na_position="last"
                ).iterrows()
            ]
            if assets:
                locations.append(
                    DisplayAssetbyLocation(
                        location=location,
                        assets=assets,
                    )
                )
        if locations:
            data_to_display.append(
                DisplayData(
                    asset_class=asset_class.label,
                    locations=locations,
                )
            )
    return data_to_display
