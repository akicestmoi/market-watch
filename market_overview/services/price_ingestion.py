"""Ingest closing prices from external market data sources."""

from datetime import date, timedelta
from typing import Literal, TypedDict

import core.services as core_services
from core.services import get_market_watch_as_of_date, logger
from market_overview.models import (
    AssetModel,
    HolidayModel,
    LocationChoices,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
    SpecialComment,
)
from market_overview.services.scrapers.bb_jgb import get_jgb_yield_from_bb
from market_overview.services.scrapers.boj_mutan import get_mutan_rate_from_boj
from market_overview.services.scrapers.bundesbank import get_bund_yield_from_bundesbank
from market_overview.services.scrapers.common import ScrapingResult
from market_overview.services.scrapers.dept_treasury import (
    get_treasury_yield_from_dep_treasury,
)
from market_overview.services.scrapers.global_rates import scrap_from_global_rates
from market_overview.services.scrapers.nyfed import scrap_rate_from_nyfed_xml
from market_overview.services.scrapers.webstat import get_webstat_rates
from market_overview.services.scrapers.yahoo import get_yahoo_finance_closing_prices

SOURCE_SCRAP_MAP = {
    PriceSourceChoices.GOV_TREASURY_DEPT: lambda d, t: get_treasury_yield_from_dep_treasury(
        d, t
    ),
    PriceSourceChoices.NYFED: lambda d, t: scrap_rate_from_nyfed_xml(d, t),
    PriceSourceChoices.WEBSTAT: lambda d, t: get_webstat_rates(d, t),
    PriceSourceChoices.BUNDESBANK: lambda d, t: get_bund_yield_from_bundesbank(d, t),
    PriceSourceChoices.BOJ: lambda d, _: get_mutan_rate_from_boj(d),
    PriceSourceChoices.BB: lambda d, t: get_jgb_yield_from_bb(d, t),
    PriceSourceChoices.GLOBAL_RATES: lambda d, t: scrap_from_global_rates(d, t),
    PriceSourceChoices.YAHOO: lambda d, t: get_yahoo_finance_closing_prices(d, t),
}


def get_market_price_ingestion_lock_key(price_date: date) -> str:
    """Return Redis lock key for market price ingestion."""
    return f"lock:market_price_ingestion:{price_date.isoformat()}"


class _MarketData(TypedDict):
    """Market data dictionnary."""

    asset: AssetModel
    price: float | None
    date: date
    comment: str | None


def _is_holiday_at_location(target_date: date, location: LocationChoices) -> bool:
    """Check if target date is a holiday at a given location."""
    return HolidayModel.objects.filter(date=target_date, location=location).exists()


def _get_market_data(
    asset: AssetModel,
    target_date: date,
) -> _MarketData:
    """Get price from scraping function."""
    if _is_holiday_at_location(target_date, asset.location):
        logger.info(
            f"No price found for {asset.short_name} on {target_date} as it is a bank holiday."
        )
        return _MarketData(
            asset=asset,
            price=None,
            date=target_date,
            comment=SpecialComment.BANK_HOLIDAY,
        )
    scraping_function = SOURCE_SCRAP_MAP.get(asset.source)
    try:
        scraping_result: ScrapingResult = (
            scraping_function(target_date, asset.ticker)
            if scraping_function
            else ScrapingResult(price=None, comment="No scraping function found.")
        )
        if not scraping_result.get("price"):
            logger.warning("No price found.")
    except Exception as e:
        scraping_result = ScrapingResult(
            price=None, comment=f"Error getting market data: {str(e)}"
        )
    return _MarketData(
        asset=asset,
        price=scraping_result.get("price"),
        date=target_date,
        comment=scraping_result.get("comment"),
    )


def get_market_data(target_date: date) -> list[_MarketData]:
    """Get market data."""
    market_data = []
    for asset in AssetModel.objects.all():
        logger.info(f"Scraping asset: {asset.short_name}")
        market_data.append(_get_market_data(asset, target_date))
    return market_data


class _IngestionNotUpdatedResult(TypedDict):
    """Ingestion not updated result dictionnary."""

    asset_not_updated: list[str]
    asset_not_updated_holiday: list[str]


def ingest_market_data(
    market_data: list[_MarketData],
) -> _IngestionNotUpdatedResult:
    """Ingest market data."""
    asset_not_updated: list[_MarketData] = []
    asset_not_updated_holiday: list[_MarketData] = []
    for data in market_data:
        if not data["price"]:
            if data["comment"] == SpecialComment.BANK_HOLIDAY:
                asset_not_updated_holiday.append(data)
            else:
                asset_not_updated.append(data)
        core_services.upsert_with_logs(
            model=MarketPriceModel,
            log_model=PriceUpdateLogModel,
            lookup_kwargs={"date": data["date"], "asset": data["asset"]},
            updates={
                "logs": f"Automated price update on {data['asset'].short_name}.",
                "price": data["price"],
                "comment": data["comment"],
            },
            logging_on_fields=["price"],
            none_skip_fields=["price"],
        )
    return _IngestionNotUpdatedResult(
        asset_not_updated=[data["asset"].short_name for data in asset_not_updated],
        asset_not_updated_holiday=[
            data["asset"].short_name for data in asset_not_updated_holiday
        ],
    )


class BatchPriceIngestionItem(TypedDict):
    """Batch price ingestion item dictionnary."""

    short_name: str
    start_date: date
    end_date: date | None


class _BatchPriceIngestionResult(TypedDict):
    """Batch price ingestion result dictionnary."""

    short_name: str
    status: Literal["success", "error"]
    error: str | None
    asset_not_updated: list[str]
    asset_not_updated_holiday: list[str]


def _get_specific_asset_market_data(
    short_name: str,
    start_date: date,
    end_date: date,
) -> list[_MarketData]:
    """Get specific asset market data."""
    asset = AssetModel.objects.get(short_name=short_name)
    delta_days = (end_date - start_date).days
    date_range = [
        start_date + timedelta(days=i)
        for i in range(delta_days + 1)
        if (start_date + timedelta(days=i)).weekday() < 5
    ]
    market_data = []
    for target_date in date_range:
        logger.info(f"Scraping asset: {asset.short_name} for date: {target_date}")
        market_data.append(_get_market_data(asset, target_date))
    return market_data


def _ingest_specific_asset_market_prices(
    short_name: str,
    start_date: date,
    end_date: date | None = None,
) -> _BatchPriceIngestionResult:
    """Ingest market prices for a specific asset over a date range."""
    target_end_date = end_date if end_date else get_market_watch_as_of_date()
    if not AssetModel.objects.filter(short_name=short_name).exists():
        return _BatchPriceIngestionResult(
            short_name=short_name,
            status="error",
            error=f"Asset: {short_name} does not exist in database.",
            asset_not_updated=[],
            asset_not_updated_holiday=[],
        )

    market_data = _get_specific_asset_market_data(
        short_name, start_date, target_end_date
    )
    ingestion_result = ingest_market_data(market_data)

    return _BatchPriceIngestionResult(
        short_name=short_name,
        status="success",
        error=None,
        asset_not_updated=ingestion_result["asset_not_updated"],
        asset_not_updated_holiday=ingestion_result["asset_not_updated_holiday"],
    )


def batch_ingest_specific_asset_market_prices(
    batch_ingestion_items: list[BatchPriceIngestionItem],
) -> list[_BatchPriceIngestionResult]:
    """Batch ingest market prices for multiple assets."""
    results = []
    for item in batch_ingestion_items:
        result = _ingest_specific_asset_market_prices(
            item["short_name"], item["start_date"], item.get("end_date")
        )
        results.append(result)

    return results
