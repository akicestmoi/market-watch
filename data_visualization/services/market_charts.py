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


class MarketChartsDropdownValues(TypedDict):
    """Dropdown values."""

    stocks: list[AssetNames]
    fx: list[AssetNames]
    crypto: list[AssetNames]
    commodity: list[AssetNames]
    rates: list[AssetNames]
    locations: list[str]


def get_market_charts_dropdown_values() -> MarketChartsDropdownValues:
    """Get dropdown values."""
    locations = LocationChoices.get_labels()
    return MarketChartsDropdownValues(
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


class MarketChartsLabels(TypedDict):
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
    dropdown_values: MarketChartsDropdownValues, front_data: MarketChartsFrontData
) -> MarketChartsLabels:
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

    return {
        "stocks": _get_generic_asset_label("stocks", front_data["stock_name"]),
        "fx": _get_generic_asset_label("fx", front_data["fx_name"]),
        "crypto": _get_generic_asset_label("crypto", front_data["crypto_name"]),
        "commodity": _get_generic_asset_label(
            "commodity", front_data["commodity_name"]
        ),
        "yield_curve_location": front_data["yield_curve_location"],
        "main_rate": front_data["main_rate"],
        "main_rate_full_name": _get_generic_asset_label(
            "rates", front_data["main_rate"]
        ),
        "stock_name_compare": _get_generic_asset_label(
            "stocks", front_data["stock_name_compare"]
        ),
        "fx_name_compare": _get_generic_asset_label(
            "fx", front_data["fx_name_compare"]
        ),
        "crypto_name_compare": _get_generic_asset_label(
            "crypto", front_data["crypto_name_compare"]
        ),
        "commodity_name_compare": _get_generic_asset_label(
            "commodity", front_data["commodity_name_compare"]
        ),
        "spread_rate": front_data["spread_rate"],
    }


class MarketChartsData(TypedDict):
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


def _to_historical_prices(frame: pd.DataFrame) -> list[HistoricalPrice]:
    """Build ``HistoricalPrice`` rows from a DataFrame with price_date/price."""
    prices: list[HistoricalPrice] = []
    for row in frame[["price_date", "price"]].to_dict(orient="records"):
        prices.append(
            HistoricalPrice(
                price_date=row["price_date"],
                price=row["price"],
            )
        )
    return prices


def get_market_charts_data(
    reference_date: date, previous_curve_date: date, front_data: MarketChartsFrontData
) -> MarketChartsData:
    """Load price series and yield curves for the market charts page."""
    main_rate_historical_yield = market_data.get_historical_prices(
        front_data["main_rate"],
        start_date=_get_start_date(
            reference_date, front_data["spread_rates_chart_duration"]
        ),
        end_date=reference_date,
    )

    spread_rate = front_data.get("spread_rate")
    if spread_rate:
        spread_rate_historical_yield = market_data.get_historical_prices(
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
            spread_rates = _to_historical_prices(spread_rate_df)
        else:
            if main_rate_historical_yield:
                spread_rate_df = pd.DataFrame(main_rate_historical_yield)
                spread_rate_df["price"] = spread_rate_df["price"] * 100
                spread_rates = _to_historical_prices(spread_rate_df)
            else:
                spread_rates = []
    else:
        if main_rate_historical_yield:
            spread_rate_df = pd.DataFrame(main_rate_historical_yield)
            spread_rate_df["price"] = spread_rate_df["price"] * 100
            spread_rates = _to_historical_prices(spread_rate_df)
        else:
            spread_rates = []
    return {
        "stock_prices": market_data.get_historical_prices(
            front_data["stock_name"],
            start_date=_get_start_date(
                reference_date, front_data["stock_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "stock_prices_compare": (
            market_data.get_historical_prices(
                front_data["stock_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["stock_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["stock_name_compare"]
            else []
        ),
        "fx_prices": market_data.get_historical_prices(
            front_data["fx_name"],
            start_date=_get_start_date(reference_date, front_data["fx_chart_duration"]),
            end_date=reference_date,
        ),
        "fx_prices_compare": (
            market_data.get_historical_prices(
                front_data["fx_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["fx_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["fx_name_compare"]
            else []
        ),
        "crypto_prices": market_data.get_historical_prices(
            front_data["crypto_name"],
            start_date=_get_start_date(
                reference_date, front_data["crypto_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "crypto_prices_compare": (
            market_data.get_historical_prices(
                front_data["crypto_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["crypto_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["crypto_name_compare"]
            else []
        ),
        "commodity_prices": market_data.get_historical_prices(
            front_data["commodity_name"],
            start_date=_get_start_date(
                reference_date, front_data["commodity_chart_duration"]
            ),
            end_date=reference_date,
        ),
        "commodity_prices_compare": (
            market_data.get_historical_prices(
                front_data["commodity_name_compare"],
                start_date=_get_start_date(
                    reference_date, front_data["commodity_chart_duration"]
                ),
                end_date=reference_date,
            )
            if front_data["commodity_name_compare"]
            else []
        ),
        "reference_yield_curve": market_data.get_yield_curve(
            reference_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "previous_yield_curve": market_data.get_yield_curve(
            previous_curve_date,
            LocationChoices.from_label(front_data["yield_curve_location"]),
        ),
        "spread_rates": spread_rates,
    }
