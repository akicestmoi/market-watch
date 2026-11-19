"""Build market chart series payloads for the visualization UI."""

from datetime import date, timedelta
from enum import Enum
from typing import TypedDict

import pandas as pd
from dateutil.relativedelta import relativedelta

import market_overview.services.market_data as market_data
from market_overview.models import AssetClassChoices, LocationChoices
from market_overview.services.market_data import (
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


class _MarketChartsDropdownValues(TypedDict):
    """Dropdown values."""

    stocks: list[AssetNames]
    fx: list[AssetNames]
    crypto: list[AssetNames]
    commodity: list[AssetNames]
    rates: list[AssetNames]
    locations: list[str]


def get_market_charts_dropdown_values() -> _MarketChartsDropdownValues:
    """Get dropdown values."""
    locations = LocationChoices.get_labels()
    return _MarketChartsDropdownValues(
        stocks=market_data.get_asset_names({"asset_class": AssetClassChoices.STOCKS}),
        fx=market_data.get_asset_names({"asset_class": AssetClassChoices.FX}),
        crypto=market_data.get_asset_names({"asset_class": AssetClassChoices.CRYPTO}),
        commodity=market_data.get_asset_names(
            {"asset_class": AssetClassChoices.COMMODITIES}
        ),
        rates=market_data.get_asset_names({"asset_class": AssetClassChoices.RATES}),
        locations=locations,
    )


class MarketChartsFrontData(TypedDict):
    """Front data."""

    reference_date: date
    previous_curve_date: date
    yield_curve_location: str  # Display label (LocationChoices.label) from the UI
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
    spread_rate: str | None


class _MarketChartsLabels(TypedDict):
    """Labels."""

    stocks: str | None
    fx: str | None
    crypto: str | None
    commodity: str | None
    yield_curve_location: str | None
    main_rate: str | None
    main_rate_full_name: str | None
    spread_rate: str | None
    stock_name_compare: str | None
    fx_name_compare: str | None
    crypto_name_compare: str | None
    commodity_name_compare: str | None


def _get_asset_full_name(
    asset_names: list[AssetNames], asset_short_name: str
) -> str | None:
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
    dropdown_values: _MarketChartsDropdownValues, front_data: MarketChartsFrontData
) -> _MarketChartsLabels:
    """Get labels."""

    def _get_generic_asset_label(
        asset_class: str, asset_name: str | None
    ) -> str | None:
        """Get full name for an asset short name in a dropdown class."""
        return (
            _get_asset_full_name(dropdown_values[asset_class], asset_name)
            if asset_name
            else None
        )

    return _MarketChartsLabels(
        stocks=_get_generic_asset_label("stocks", front_data["stock_name"]),
        fx=_get_generic_asset_label("fx", front_data["fx_name"]),
        crypto=_get_generic_asset_label("crypto", front_data["crypto_name"]),
        commodity=_get_generic_asset_label("commodity", front_data["commodity_name"]),
        yield_curve_location=front_data["yield_curve_location"],
        main_rate=front_data["main_rate"],
        main_rate_full_name=_get_generic_asset_label("rates", front_data["main_rate"]),
        stock_name_compare=_get_generic_asset_label(
            "stocks", front_data["stock_name_compare"]
        ),
        fx_name_compare=_get_generic_asset_label("fx", front_data["fx_name_compare"]),
        crypto_name_compare=_get_generic_asset_label(
            "crypto", front_data["crypto_name_compare"]
        ),
        commodity_name_compare=_get_generic_asset_label(
            "commodity", front_data["commodity_name_compare"]
        ),
        spread_rate=front_data["spread_rate"],
    )


class _MarketChartsData(TypedDict):
    """Price series and curves for the market charts page."""

    stock_prices: list[HistoricalPrice]
    stock_prices_compare: list[HistoricalPrice]
    fx_prices: list[HistoricalPrice]
    fx_prices_compare: list[HistoricalPrice]
    crypto_prices: list[HistoricalPrice]
    crypto_prices_compare: list[HistoricalPrice]
    commodity_prices: list[HistoricalPrice]
    commodity_prices_compare: list[HistoricalPrice]
    reference_yield_curve: list[YieldCurvePoint]
    previous_yield_curve: list[YieldCurvePoint]
    spread_rates: list[HistoricalPrice]


def _get_start_date(reference_date: date, chart_duration: ChartDuration) -> date:
    """Get start date for data."""
    if chart_duration == ChartDuration.ONE_WEEK:
        return reference_date - timedelta(weeks=1)
    if chart_duration == ChartDuration.ONE_MONTH:
        return reference_date - relativedelta(months=1)
    if chart_duration == ChartDuration.YEAR_TO_DATE:
        return reference_date - relativedelta(days=365)
    if chart_duration == ChartDuration.ONE_YEAR:
        return reference_date - relativedelta(years=1)
    return reference_date


def _convert_dataframe_to_historical_prices(
    frame: pd.DataFrame,
) -> list[HistoricalPrice]:
    """Convert a DataFrame with price_date/price into 'HistoricalPrice' values."""
    prices: list[HistoricalPrice] = []
    for price_record in frame[["price_date", "price"]].to_dict(orient="records"):
        prices.append(
            HistoricalPrice(
                price_date=price_record["price_date"],
                price=price_record["price"],
            )
        )
    return prices


def _get_historical_prices_for_asset_chart(
    asset_short_name: str,
    reference_date: date,
    chart_duration: ChartDuration,
) -> list[HistoricalPrice]:
    """Load one asset's price series for a chart window ending on 'reference_date'."""
    return market_data.get_historical_prices(
        asset_short_name,
        start_date=_get_start_date(reference_date, chart_duration),
        end_date=reference_date,
    )


def _get_optional_compare_historical_prices(
    compare_short_name: str,
    reference_date: date,
    chart_duration: ChartDuration,
) -> list[HistoricalPrice]:
    """Load a comparison asset's prices when 'compare_short_name' is set."""
    if not compare_short_name:
        return []
    return _get_historical_prices_for_asset_chart(
        compare_short_name, reference_date, chart_duration
    )


def _get_spread_rates_historical_prices(
    reference_date: date,
    front_data: MarketChartsFrontData,
) -> list[HistoricalPrice]:
    """Return spread or scaled main-rate yields for the spread-rates chart."""
    chart_duration = front_data["spread_rates_chart_duration"]
    main_rate_historical_yield = _get_historical_prices_for_asset_chart(
        front_data["main_rate"], reference_date, chart_duration
    )
    spread_rate = front_data.get("spread_rate")
    if spread_rate:
        spread_rate_historical_yield = _get_historical_prices_for_asset_chart(
            str(spread_rate), reference_date, chart_duration
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
            return _convert_dataframe_to_historical_prices(spread_rate_df)
        if main_rate_historical_yield:
            spread_rate_df = pd.DataFrame(main_rate_historical_yield)
            spread_rate_df["price"] = spread_rate_df["price"] * 100
            return _convert_dataframe_to_historical_prices(spread_rate_df)
        return []
    if main_rate_historical_yield:
        spread_rate_df = pd.DataFrame(main_rate_historical_yield)
        spread_rate_df["price"] = spread_rate_df["price"] * 100
        return _convert_dataframe_to_historical_prices(spread_rate_df)
    return []


def get_market_charts_data(
    reference_date: date, previous_curve_date: date, front_data: MarketChartsFrontData
) -> _MarketChartsData:
    """Load price series and yield curves for the market charts page."""
    spread_rates = _get_spread_rates_historical_prices(reference_date, front_data)
    return _MarketChartsData(
        stock_prices=_get_historical_prices_for_asset_chart(
            front_data["stock_name"],
            reference_date,
            front_data["stock_chart_duration"],
        ),
        stock_prices_compare=_get_optional_compare_historical_prices(
            front_data["stock_name_compare"],
            reference_date,
            front_data["stock_chart_duration"],
        ),
        fx_prices=_get_historical_prices_for_asset_chart(
            front_data["fx_name"],
            reference_date,
            front_data["fx_chart_duration"],
        ),
        fx_prices_compare=_get_optional_compare_historical_prices(
            front_data["fx_name_compare"],
            reference_date,
            front_data["fx_chart_duration"],
        ),
        crypto_prices=_get_historical_prices_for_asset_chart(
            front_data["crypto_name"],
            reference_date,
            front_data["crypto_chart_duration"],
        ),
        crypto_prices_compare=_get_optional_compare_historical_prices(
            front_data["crypto_name_compare"],
            reference_date,
            front_data["crypto_chart_duration"],
        ),
        commodity_prices=_get_historical_prices_for_asset_chart(
            front_data["commodity_name"],
            reference_date,
            front_data["commodity_chart_duration"],
        ),
        commodity_prices_compare=_get_optional_compare_historical_prices(
            front_data["commodity_name_compare"],
            reference_date,
            front_data["commodity_chart_duration"],
        ),
        reference_yield_curve=market_data.get_yield_curve(
            reference_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        previous_yield_curve=market_data.get_yield_curve(
            previous_curve_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        spread_rates=spread_rates,
    )
