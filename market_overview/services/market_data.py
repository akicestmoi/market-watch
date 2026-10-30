"""Query helpers for assets and prices (including missing-price reports)."""

from collections.abc import Hashable
from datetime import date, datetime
from io import BytesIO
from typing import Literal, TypedDict

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
    SpecialComment,
)

EXPECTED_CSV_COLUMNS: tuple[
    Literal["date"],
    Literal["short_name"],
    Literal["price"],
    Literal["logs"],
] = ("date", "short_name", "price", "logs")
# Pandas DtypeArg needs dict[Hashable, ...]; invariance blocks TypedDict/Literal keys.
ASSETS_PRICES_CSV_DTYPES: dict[Hashable, type[str]] = {
    column: str for column in EXPECTED_CSV_COLUMNS
}


def get_all_asset_prices_for_date(price_date: date) -> list[MarketPriceModel]:
    """Get market prices for a specific date."""
    return list(
        MarketPriceModel.objects.filter(date=price_date).select_related("asset")
    )


def delete_market_prices(ids: list[int]) -> int:
    """Delete market prices by IDs."""
    market_prices_queryset = MarketPriceModel.objects.filter(pk__in=ids)
    deleted_count = market_prices_queryset.count()
    market_prices_queryset.delete()
    return deleted_count


def delete_price_update_logs_before_date(logs_date: date):
    """Delete price update logs before a given date."""
    PriceUpdateLogModel.objects.filter(date_added__lt=logs_date).delete()


def get_price_update_logs(
    price_date: date | None = None, short_name: str | None = None
) -> list[PriceUpdateLogModel]:
    """Get price update logs with optional filtering."""
    logs_queryset = PriceUpdateLogModel.objects.select_related(
        "market_price__asset"
    ).all()
    if price_date:
        logs_queryset = logs_queryset.filter(market_price__date=price_date)
    if short_name:
        logs_queryset = logs_queryset.filter(market_price__asset__short_name=short_name)

    return list(logs_queryset.order_by("-date_added"))


class AssetNames(TypedDict):
    """Asset names dictionnary."""

    short_name: str
    full_name: str


class _GetAssetNamesFilters(TypedDict, total=False):
    """Optional filters for ``get_asset_names``."""

    asset_class: AssetClassChoices | None
    asset_type: AssetTypeChoices | None
    location: LocationChoices | None
    source: PriceSourceChoices | None


def get_asset_names(filters: _GetAssetNamesFilters) -> list[AssetNames]:
    """Get all assets based on unique short_name and full_name pair."""
    asset_names = []
    query_filters = {key: value for key, value in filters.items() if value}
    for asset in AssetModel.objects.filter(**query_filters).order_by("asset_id"):
        asset_names.append(
            AssetNames(short_name=asset.short_name, full_name=asset.full_name)
        )
    return asset_names


class HistoricalPrice(TypedDict):
    """Information of a specific historical price."""

    price_date: date
    price: float | None


def get_historical_prices(
    short_name: str, start_date: date | None = None, end_date: date | None = None
) -> list[HistoricalPrice]:
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


class YieldCurvePoint(TypedDict):
    """Information on Yield Curve specific tenor."""

    maturity: float | None
    price: float | None
    short_name: str


def get_yield_curve(
    target_date: date,
    location: LocationChoices,
    include_interbank_rates: bool = True,
) -> list[YieldCurvePoint]:
    """Get yield curve for a specific date and location.

    Includes both GOVERNMENT_BOND_RATE and INTERBANK_RATE assets.
    None maturity values are treated as 0 for interbank rates.

    Special rules:
    - Excludes EFFR, only includes SOFR among interbank rates
    - For FR location: also includes EU location data
    - None maturity values are treated as 0.0 for interbank rates
    """
    locations_to_query = [location]
    asset_types_to_query = [AssetTypeChoices.GOVERNMENT_BOND_RATE]
    if location == LocationChoices.FR:
        locations_to_query.append(LocationChoices.EU)
    if include_interbank_rates:
        asset_types_to_query.append(AssetTypeChoices.INTERBANK_RATE)
    market_data_queryset = MarketPriceModel.objects.filter(
        date=target_date,
        asset__location__in=locations_to_query,
        asset__asset_type__in=asset_types_to_query,
    )
    yield_curve = [
        YieldCurvePoint(
            short_name=data.asset.short_name,
            maturity=0.0 if data.asset.maturity is None else data.asset.maturity,
            price=data.price,
        )
        for data in market_data_queryset
        if data.asset.asset_class == AssetClassChoices.RATES
        and not data.asset.short_name == "EFFR"
    ]
    return sorted(yield_curve, key=lambda x: x["maturity"] or 0)


class _AssetWithoutPrice(TypedDict):
    """Asset without price dictionnary."""

    id: int
    date: date
    short_name: str
    full_name: str
    maturity: float | None
    comment: str | None


def get_assets_without_prices(
    start_date: date | None = None,
    end_date: date | None = None,
    include_holidays: bool = False,
) -> list[_AssetWithoutPrice]:
    """Get assets without prices."""
    assets_queryset = MarketPriceModel.objects.filter(
        price__isnull=True
    ).select_related("asset")
    if not include_holidays:
        assets_queryset = assets_queryset.exclude(comment=SpecialComment.BANK_HOLIDAY)
    if start_date:
        assets_queryset = assets_queryset.filter(date__gte=start_date)
    if end_date:
        assets_queryset = assets_queryset.filter(date__lte=end_date)
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
            _AssetWithoutPrice(
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


def _get_last_market_price_without_holidays_before_date(
    asset: AssetModel, date: date
) -> MarketPriceModel:
    """Get last market price without holidays before a given date."""
    market_prices_without_holidays = (
        MarketPriceModel.objects.filter(asset=asset, date__lte=date)
        .exclude(comment=SpecialComment.BANK_HOLIDAY)
        .order_by("-date")
        .first()
    )
    if not market_prices_without_holidays:
        raise ValueError(
            f"No market price found for {asset.short_name} without holidays."
        )
    return market_prices_without_holidays


def get_all_asset_prices_for_date_without_holidays(
    price_date: date,
) -> list[MarketPriceModel]:
    """Return all asset prices for a date, substituting prior non-holiday prices."""
    queryset = MarketPriceModel.objects.filter(date=price_date).select_related("asset")
    market_prices_without_holidays = []
    for market_price in queryset:
        if market_price.comment == SpecialComment.BANK_HOLIDAY:
            market_prices_without_holidays.append(
                _get_last_market_price_without_holidays_before_date(
                    market_price.asset, price_date
                )
            )
        else:
            market_prices_without_holidays.append(market_price)
    return market_prices_without_holidays


class BulkUpdateAssetsPricesItem(TypedDict):
    """Bulk update assets prices dictionnary."""

    date: date
    short_name: str
    price: float
    logs: str | None


def bulk_update_assets_prices(
    updates: list[BulkUpdateAssetsPricesItem],
) -> list[MarketPriceModel]:
    """Bulk update assets prices."""
    updated_assets = []
    for update in updates:
        market_price = MarketPriceModel.objects.get(
            date=update["date"],
            asset__short_name=update["short_name"],
        )
        logs_value = update.get("logs") or "Bulk update of assets prices."
        updated_assets.append(
            core_services.update_with_logs(
                model_to_update=market_price,
                log_model=PriceUpdateLogModel,
                updates={
                    "logs": logs_value,
                    "price": update["price"],
                    "comment": logs_value,
                },
                logging_on_fields=["price"],
                none_skip_fields=["price"],
            )
        )
    return updated_assets


def bulk_update_assets_prices_from_csv(
    csv_file: bytes,
) -> list[MarketPriceModel]:
    """Bulk update assets prices from a CSV file."""
    df = pd.read_csv(BytesIO(csv_file), dtype=ASSETS_PRICES_CSV_DTYPES)
    df.fillna("", inplace=True)

    missing_columns = [
        column for column in EXPECTED_CSV_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(
            f"CSV file must have the following columns: "
            f"{', '.join(sorted(missing_columns))}."
        )

    updates = [
        BulkUpdateAssetsPricesItem(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
            short_name=row["short_name"],
            price=float(row["price"]),
            logs=(
                row["logs"]
                if row["logs"]
                else (
                    f"Bulk update from CSV file of {row['short_name']} "
                    f"to price: {row['price']}."
                )
            ),
        )
        for row in df.to_dict(orient="records")
    ]
    return bulk_update_assets_prices(updates)


class MarkAsHolidayItem(TypedDict):
    """Mark as holiday item dictionnary."""

    short_name: str
    date: date


class _MarkAsHolidayResult(TypedDict):
    """Mark as holiday result dictionnary."""

    updated_count: int
    not_found: list[str]


def mark_prices_as_holiday(items: list[MarkAsHolidayItem]) -> _MarkAsHolidayResult:
    """Mark market prices as holiday for the given assets and dates."""
    updated_count = 0
    not_found: list[str] = []

    for item in items:
        market_price = MarketPriceModel.objects.filter(
            asset__short_name=item["short_name"],
            date=item["date"],
        ).first()

        if market_price:
            market_price.comment = SpecialComment.BANK_HOLIDAY
            market_price.price = None
            market_price.save()
            updated_count += 1
        else:
            not_found.append(f"{item['short_name']} on {item['date']}")

    return _MarkAsHolidayResult(updated_count=updated_count, not_found=not_found)


class _MarketPriceRow(TypedDict):
    """Merged asset + market-price row used by price-change calculations."""

    asset_id: int
    asset_class: AssetClassChoices
    location: LocationChoices | None
    short_name: str
    full_name: str
    maturity: float | None
    asset_type: AssetTypeChoices | None
    ticker: str
    source: PriceSourceChoices | Literal[""]
    date: date
    price: float | None
    comment: str | None


class _PriceChange(TypedDict):
    """Price change dictionnary."""

    asset_id: int
    asset_class: AssetClassChoices
    short_name: str
    full_name: str
    maturity: float | None
    asset_type: AssetTypeChoices
    source: PriceSourceChoices | Literal[""]
    location: LocationChoices | None
    price: float | None
    comment: str | None
    price_previous: float | None
    comment_previous: str | None
    price_change: float | None
    price_change_pct: float | None


def _convert_market_prices_to_data(
    market_prices: list[MarketPriceModel],
) -> list[_MarketPriceRow]:
    """Convert market prices to dictionary format."""
    data_list: list[_MarketPriceRow] = []
    for market_price in market_prices:
        asset = market_price.asset
        data_list.append(
            _MarketPriceRow(
                asset_id=asset.asset_id,
                asset_class=AssetClassChoices(asset.asset_class),
                location=(LocationChoices(asset.location) if asset.location else None),
                short_name=asset.short_name,
                full_name=asset.full_name,
                maturity=asset.maturity,
                asset_type=(
                    AssetTypeChoices(asset.asset_type) if asset.asset_type else None
                ),
                ticker=asset.ticker,
                source=(PriceSourceChoices(asset.source) if asset.source else ""),
                date=market_price.date,
                price=market_price.price,
                comment=market_price.comment,
            )
        )
    return data_list


def calculate_price_change(
    reference_market_prices: list[MarketPriceModel],
    comparison_market_prices: list[MarketPriceModel],
) -> list[_PriceChange]:
    """Calculate price change between two dates."""
    reference_data = _convert_market_prices_to_data(reference_market_prices)
    comparison_data = _convert_market_prices_to_data(comparison_market_prices)

    if not reference_data and not comparison_data:
        return []

    reference_df = pd.DataFrame(reference_data) if reference_data else pd.DataFrame()
    comparison_df = pd.DataFrame(comparison_data) if comparison_data else pd.DataFrame()
    if not reference_df.empty and not comparison_df.empty:
        # Outer merge to handle all cases uniformly
        price_diff = pd.merge(
            reference_df,
            comparison_df,
            on="short_name",
            how="outer",
            suffixes=("", "_previous"),
        )
    elif not reference_df.empty:
        price_diff = reference_df.copy()
        price_diff["price_previous"] = None
        price_diff["comment_previous"] = None
    else:
        price_diff = comparison_df.rename(
            columns={"price": "price_previous", "comment": "comment_previous"}
        )
        price_diff["price"] = None
        price_diff["comment"] = None

    # For assets that only exist in comparison_data, copy _previous metadata fields
    # to base fields (except price/comment which should remain None)
    if not reference_df.empty and not comparison_df.empty:
        previous_cols = [col for col in price_diff.columns if col.endswith("_previous")]
        price_cols = {"price", "comment"}

        for prev_col in previous_cols:
            base_col = prev_col.replace("_previous", "")
            if base_col in price_cols or base_col not in price_diff.columns:
                continue

            # Vectorized copy: only where base is NaN and _previous has value
            mask = price_diff[base_col].isna() & price_diff[prev_col].notna()
            if mask.any():
                price_diff.loc[mask, base_col] = price_diff.loc[mask, prev_col]

        # Ensure price/comment are None for assets without reference data
        mask_no_ref = price_diff["price"].isna() & price_diff["price_previous"].notna()
        if mask_no_ref.any():
            price_diff.loc[mask_no_ref, ["price", "comment"]] = None

    # Calculate price changes
    price_diff["price_change"] = price_diff["price"] - price_diff["price_previous"]
    price_diff["price_change_pct"] = (
        price_diff["price"] / price_diff["price_previous"] - 1
    ) * 100

    # Adjust price changes for Interest Rate classes
    if "asset_class" in price_diff.columns:
        rates_mask = price_diff["asset_class"].isin([AssetClassChoices.RATES])
        if rates_mask.any():
            price_diff.loc[rates_mask, "price_change"] *= 100
            price_diff.loc[rates_mask, "price_change_pct"] = None

    # Convert to _PriceChange records
    price_change_cols = list(_PriceChange.__annotations__.keys())
    available_cols = [col for col in price_change_cols if col in price_diff.columns]
    price_changes: list[_PriceChange] = []
    for record in (
        price_diff[available_cols]
        .replace({float("nan"): None})
        .to_dict(orient="records")
    ):
        price_changes.append(
            _PriceChange(
                asset_id=record["asset_id"],
                asset_class=record["asset_class"],
                short_name=record["short_name"],
                full_name=record["full_name"],
                maturity=record.get("maturity"),
                asset_type=record["asset_type"],
                source=record["source"],
                location=record.get("location"),
                price=record.get("price"),
                comment=record.get("comment"),
                price_previous=record.get("price_previous"),
                comment_previous=record.get("comment_previous"),
                price_change=record.get("price_change"),
                price_change_pct=record.get("price_change_pct"),
            )
        )
    return price_changes
