from datetime import date, timedelta
from enum import Enum
from typing import List, Optional, TypedDict, cast

import pandas as pd
from dateutil.relativedelta import relativedelta

import market_overview.services.market_data_services as market_data_services
from market_overview.models import AssetClassChoices, AssetTypeChoices, LocationChoices
from market_overview.services.market_data_services import (
    AssetNames,
    HistoricalPrice,
    YieldCurvePoint,
)


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
    stock_chart_duration: ChartDuration
    fx_chart_duration: ChartDuration
    crypto_chart_duration: ChartDuration
    commodity_chart_duration: ChartDuration
    spread_rates_chart_duration: ChartDuration
    stock_name_compare: str
    fx_name_compare: str
    crypto_name_compare: str
    commodity_name_compare: str
    spread_rate: Optional[str]


class MarketChartsLabels(TypedDict):
    """Labels."""

    stocks: Optional[str]
    fx: Optional[str]
    crypto: Optional[str]
    commodity: Optional[str]
    yield_curve_location: Optional[str]
    main_rate: Optional[str]
    main_rate_full_name: Optional[str]
    spread_rate: Optional[str]
    stock_name_compare: Optional[str]
    fx_name_compare: Optional[str]
    crypto_name_compare: Optional[str]
    commodity_name_compare: Optional[str]


def _get_asset_full_name(
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


def get_market_charts_labels(
    dropdown_values: MarketChartsDropdownValues, front_data: MarketChartsFrontData
) -> MarketChartsLabels:
    """Get labels."""

    def _generic_asset_label_getter(
        asset_class: str, asset_name: Optional[str]
    ) -> Optional[str]:
        return (
            _get_asset_full_name(dropdown_values[asset_class], asset_name)
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
        "main_rate_full_name": _generic_asset_label_getter(
            "rates", front_data["main_rate"]
        ),
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
        "spread_rate": front_data["spread_rate"],
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

    spread_rate = front_data.get("spread_rate")
    if spread_rate:
        spread_rate_historical_yield = market_data_services.get_historical_prices(
            str(spread_rate),
            start_date=_get_start_date(
                reference_date, front_data["spread_rates_chart_duration"]
            ),
            end_date=reference_date,
        )
        if main_rate_historical_yield and spread_rate_historical_yield:
            main_df = pd.DataFrame(main_rate_historical_yield)
            spread_df = pd.DataFrame(spread_rate_historical_yield)
            spread_rate_df = pd.merge(
                main_df,
                spread_df,
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
        else:
            spread_rate_df = pd.DataFrame(main_rate_historical_yield)
            spread_rate_df["price"] = spread_rate_df["price"] * 100
            spread_rates = cast(
                List[HistoricalPrice],
                spread_rate_df[["price_date", "price"]].to_dict(orient="records"),
            )
    else:
        spread_rate_df = pd.DataFrame(main_rate_historical_yield)
        spread_rate_df["price"] = spread_rate_df["price"] * 100
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
