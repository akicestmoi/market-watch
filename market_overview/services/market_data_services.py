from datetime import date, datetime
from io import BytesIO
from typing import Dict, List, Optional, TypedDict, cast

import pandas as pd

import core.services as core_services
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
)
from market_overview.services.price_ingestion_services import MarketData


class PriceChange(TypedDict):
    """Price change dictionnary."""

    asset_id: int
    asset_class: AssetClassChoices
    short_name: str
    full_name: str
    maturity: Optional[float]
    asset_type: AssetTypeChoices
    source: PriceSourceChoices
    location: Optional[LocationChoices]
    price: Optional[float]
    comment: Optional[str]
    price_previous: Optional[float]
    comment_previous: Optional[str]
    price_change: Optional[float]
    price_change_pct: Optional[float]


class YieldCurvePoint(TypedDict):
    """Information on Yield Curve specific tenor."""

    maturity: Optional[float]
    price: Optional[float]
    short_name: str


class HistoricalPrice(TypedDict):
    """Information of a specific historical price."""

    price_date: date
    price: Optional[float]


class AssetNames(TypedDict):
    """Asset names dictionnary."""

    short_name: str
    full_name: str


class AssetWithoutPrice(TypedDict):
    """Asset without price dictionnary."""

    id: int
    date: date
    short_name: str
    full_name: str
    maturity: Optional[float]
    comment: Optional[str]


class BulkUpdateAssetsPricesItem(TypedDict):
    """Bulk update assets prices dictionnary."""

    date: date
    short_name: str
    price: float
    logs: Optional[str]


def get_all_asset_prices_for_date(price_date: date) -> List[MarketPriceModel]:
    """Get market prices for a specific date."""
    return list(
        MarketPriceModel.objects.filter(date=price_date).select_related("asset")
    )


def calculate_price_change(
    reference_market_prices: List[MarketPriceModel],
    comparison_market_prices: List[MarketPriceModel],
) -> List[PriceChange]:
    """Calculate price change between two dates."""
    reference_data = []
    for market_price in reference_market_prices:
        asset = market_price.asset.convert_to_dict()
        data = market_price.convert_to_dict(remove_foreign_key=True)
        data.update(asset)
        reference_data.append(data)

    comparison_data = []
    for market_price in comparison_market_prices:
        asset = market_price.asset.convert_to_dict()
        data = market_price.convert_to_dict(remove_foreign_key=True)
        data.update(asset)
        comparison_data.append(data)

    reference_df = pd.DataFrame(reference_data)
    comparison_df = pd.DataFrame(comparison_data)

    price_diff = pd.merge(
        reference_df,
        comparison_df,
        on="short_name",
        how="left",
        suffixes=("", "_previous"),
    )

    # Calculate price changes
    price_diff["price_change"] = price_diff["price"] - price_diff["price_previous"]
    price_diff["price_change_pct"] = (
        price_diff["price"] / price_diff["price_previous"] - 1
    ) * 100

    # Adjusting price changes for Interest Rate classes
    rates_row = price_diff["asset_class"].isin([AssetClassChoices.RATES])
    price_diff.loc[rates_row, "price_change"] *= 100
    price_diff.loc[rates_row, "price_change_pct"] = None

    records = cast(
        List[PriceChange],
        price_diff[list(PriceChange.__annotations__.keys())]
        .replace({float("nan"): None})
        .to_dict(orient="records"),
    )
    return [PriceChange(**record) for record in records]


def get_asset_names(filters: Dict[str, str]) -> List[AssetNames]:
    """Get all assets based on unique short_name and full_name pair."""
    asset_names = []
    for asset in AssetModel.objects.filter(**filters).order_by("asset_id"):
        asset_names.append(
            AssetNames(short_name=asset.short_name, full_name=asset.full_name)
        )
    return asset_names


def check_asset_existence(asset_name: str) -> bool:
    """Check asset existence in database."""
    return AssetModel.objects.filter(short_name=asset_name).exists()


def get_historical_prices(
    short_name: str, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> List[HistoricalPrice]:
    """Get historical prices of an asset."""
    market_data_queryset = MarketPriceModel.objects.filter(asset__short_name=short_name)
    if start_date:
        market_data_queryset = market_data_queryset.filter(date__gte=start_date)
    if end_date:
        market_data_queryset = market_data_queryset.filter(date__lte=end_date)

    historical_prices = [
        HistoricalPrice(
            price_date=data.date,
            price=data.price,
        )
        for data in market_data_queryset
    ]

    return sorted(historical_prices, key=lambda x: x["price_date"])


def get_yield_curve(
    target_date: date,
    location: LocationChoices,
    asset_type: AssetTypeChoices = AssetTypeChoices.GOVERNMENT_BOND_RATE,
) -> List[YieldCurvePoint]:
    """Get yield curve for a specific date and location."""
    market_data_queryset = MarketPriceModel.objects.filter(
        date=target_date, asset__location=location, asset__asset_type=asset_type
    )
    yield_curve = [
        YieldCurvePoint(
            short_name=data.asset.short_name,
            maturity=data.asset.maturity,
            price=data.price,
        )
        for data in market_data_queryset
        if data.asset.asset_class == AssetClassChoices.RATES
    ]
    return sorted(yield_curve, key=lambda x: (x["maturity"] is None, x["maturity"]))


def get_price_update_logs(
    price_date: Optional[date] = None, short_name: Optional[str] = None
) -> List[MarketData]:
    """Get price update logs with optional filtering."""
    logs_queryset = PriceUpdateLogModel.objects.select_related(
        "market_price__asset"
    ).all()
    if price_date:
        logs_queryset = logs_queryset.filter(date_added__date=price_date)
    if short_name:
        logs_queryset = logs_queryset.filter(market_price__asset__short_name=short_name)

    return [
        MarketData(**log)
        for log in core_services.convert_query_to_dictionary_list(
            queryset=logs_queryset
        )
    ]


def get_assets_without_prices(
    price_date: Optional[date] = None,
) -> List[AssetWithoutPrice]:
    """Get assets without prices."""
    assets_queryset = MarketPriceModel.objects.filter(
        price__isnull=True
    ).select_related("asset")
    if price_date:
        assets_queryset = assets_queryset.filter(date=price_date)
    assets_data = assets_queryset.values(
        "id",
        "comment",
        "date",
        "asset__short_name",
        "asset__full_name",
        "asset__maturity",
    )
    return sorted(
        [
            AssetWithoutPrice(
                id=asset["id"],
                date=asset["date"],
                short_name=asset["asset__short_name"],
                full_name=asset["asset__full_name"],
                maturity=asset["asset__maturity"],
                comment=asset["comment"],
            )
            for asset in assets_data
        ],
        key=lambda x: x["id"],
        reverse=True,
    )


def bulk_update_assets_prices(
    updates: List[BulkUpdateAssetsPricesItem],
) -> List[MarketPriceModel]:
    """Bulk update assets prices."""
    updated_assets = []
    for update in updates:
        market_price = core_services.get(
            MarketPriceModel,
            date=update["date"],
            asset__short_name=update["short_name"],
        )
        updated_assets.append(
            core_services.update_with_logs(
                market_price,
                PriceUpdateLogModel,
                {
                    "logs": update.get(
                        "logs",
                        f"Bulk update of {update['short_name']} to price: {update['price']}.",
                    ),
                    "price": update["price"],
                },
            )
        )
    return updated_assets


EXPECTED_CSV_FORMAT = {
    "date": str,
    "short_name": str,
    "price": float,
    "logs": str,
}


def bulk_update_assets_prices_from_csv(
    csv_file: bytes,
) -> List[MarketPriceModel]:
    """Bulk update assets prices from a CSV file."""
    df = pd.read_csv(BytesIO(csv_file), dtype=EXPECTED_CSV_FORMAT)  # type: ignore[reportArgumentType]
    df.fillna("", inplace=True)

    missing_columns = set(EXPECTED_CSV_FORMAT.keys()) - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"CSV file must have the following columns: {', '.join(missing_columns)}."
        )

    updates = [
        BulkUpdateAssetsPricesItem(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
            short_name=row["short_name"],
            price=row["price"],
            logs=(
                row["logs"]
                if row["logs"]
                else f"Bulk update from CSV file of {row['short_name']} to price: {row['price']}."
            ),
        )
        for row in df.to_dict(orient="records")
    ]
    return bulk_update_assets_prices(updates)
