import json
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, TypedDict

import pandas as pd
from dateutil.relativedelta import relativedelta
from django.shortcuts import render
from pandas.tseries.offsets import BDay

import data_visualization.services as data_visualization_services
import market_overview.services as market_overview_services
from market_overview.models import AssetClassChoices, AssetTypeChoices, LocationChoices


def market_recap_view(request):
    """Market recap view to render price changes."""
    default_reference_date = (date.today() - BDay(1)).date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    default_previous_date = (default_reference_date - BDay(1)).date()
    previous_date = request.GET.get(
        "previous_date",
        default_previous_date.isoformat(),
    )
    previous_date = datetime.fromisoformat(previous_date).date()

    base_context = {
        "reference_date": reference_date.isoformat(),
        "previous_date": previous_date.isoformat(),
        "default_reference_date": default_reference_date.isoformat(),
        "default_previous_date": default_previous_date.isoformat(),
    }
    if reference_date >= date.today():
        base_context["error_message"] = (
            f"Reference date: {reference_date} must be before today: {date.today()}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    if reference_date <= previous_date:
        base_context["error_message"] = (
            f"Reference date: {reference_date} must be greater than the previous date: {previous_date}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    reference_market_prices = market_overview_services.get_all_asset_prices_for_date(
        reference_date
    )
    if not reference_market_prices:
        base_context["error_message"] = (
            f"No data found for reference date: {reference_date}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    previous_market_prices = market_overview_services.get_all_asset_prices_for_date(
        previous_date
    )
    if not previous_market_prices:
        base_context["error_message"] = (
            f"No data found for reference date: {previous_date}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    data_to_display = data_visualization_services.format_data_for_display(
        reference_market_prices, previous_market_prices
    )

    left_asset_classes = [
        AssetClassChoices.STOCKS.label,
        AssetClassChoices.COMMODITIES.label,
        AssetClassChoices.FX.label,
        AssetClassChoices.CRYPTO.label,
        AssetClassChoices.OTHERS.label,
    ]
    right_asset_classes = [
        AssetClassChoices.RATES.label,
    ]
    context = {
        "data_to_display": data_to_display,
        "left_asset_classes": left_asset_classes,
        "right_asset_classes": right_asset_classes,
        **base_context,
    }
    print(context)
    return render(request, "data_visualization/market_recap.html", context)


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


def _get_dropdown_values() -> MarketChartsDropdownValues:
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
    stock_compare: Optional[str]
    fx_compare: Optional[str]
    crypto_compare: Optional[str]
    commodity_compare: Optional[str]


def _get_labels(
    dropdown_values: MarketChartsDropdownValues, front_data: MarketChartsFrontData
) -> MarketChartsLabels:
    """Get labels."""

    def _generic_asset_label_getter(
        asset_class: str, asset_name: Optional[str]
    ) -> Optional[str]:
        return (
            data_visualization_services.get_asset_full_name(
                dropdown_values[asset_class], asset_name
            )
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
        "stock_compare": _generic_asset_label_getter(
            "stocks", front_data["stock_name_compare"]
        ),
        "fx_compare": _generic_asset_label_getter("fx", front_data["fx_name_compare"]),
        "crypto_compare": _generic_asset_label_getter(
            "crypto", front_data["crypto_name_compare"]
        ),
        "commodity_compare": _generic_asset_label_getter(
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


def _get_market_data(
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


def data_visualization_view(request):
    """Data visualization view."""
    # Default Values
    default_values = {
        "reference_date": (date.today() - BDay(1)).date().isoformat(),
        "previous_curve_date": (date.today() - BDay(2)).date().isoformat(),
        "yield_curve_location": str(LocationChoices.US.label),  # Used for Yield Curve
        "stock_name": "DJIA",
        "fx_name": "EURUSD",
        "crypto_name": "BTC",
        "commodity_name": "Gold",
        "main_rate": "UST10Y",
        "spread_rate": "UST2Y",
        "stock_chart_duration": ChartDuration.ONE_MONTH.value,
        "fx_chart_duration": ChartDuration.ONE_MONTH.value,
        "crypto_chart_duration": ChartDuration.ONE_MONTH.value,
        "commodity_chart_duration": ChartDuration.ONE_MONTH.value,
        "spread_rates_chart_duration": ChartDuration.ONE_MONTH.value,
        "stock_name_compare": None,
        "fx_name_compare": None,
        "crypto_name_compare": None,
        "commodity_name_compare": None,
    }

    # Get Data from Front
    front_data = {
        key: request.GET.get(key, default_values[key]) for key in default_values.keys()
    }

    # Data Validation
    error_message = {}

    reference_date = datetime.fromisoformat(front_data["reference_date"]).date()
    if reference_date >= date.today():
        error_message = {
            "error_message": f"Reference date: {reference_date} must be before today: {date.today()}."
        }

    previous_curve_date = datetime.fromisoformat(
        front_data["previous_curve_date"]
    ).date()
    if reference_date <= previous_curve_date:
        error_message = {
            "error_message": f"Reference date: {reference_date} must be greater than the previous curve date: {previous_curve_date}."
        }

    # Return Selected Values for Front/Back Interaction
    selected_values = {
        **front_data,
        "previous_curve_date": previous_curve_date.isoformat(),
    }

    # Dropdown values
    dropdown_values = _get_dropdown_values()

    # Get Label
    labels = _get_labels(dropdown_values, front_data)

    # Get Market Data
    market_data = _get_market_data(reference_date, previous_curve_date, front_data)

    # Return all to Front
    context = {
        "reference_date": reference_date.isoformat(),
        "previous_curve_date": previous_curve_date.isoformat(),
        "default_reference_date": default_values["reference_date"],
        "default_previous_curve_date": default_values["previous_curve_date"],
        "dropdown_values": json.dumps(dropdown_values),
        "selected_values": json.dumps(selected_values),
        "labels": json.dumps(labels),
        "market_data": json.dumps(market_data, default=str),
    }
    if error_message:
        context.update(error_message)
    return render(request, "data_visualization/market_charts.html", context)


def economic_recap_view(request):
    """Economic Overview View."""
    default_reference_date = (date.today() - BDay(1)).date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    locations = ["US", "EU", "FR", "JP"]

    # Raw economic data with entries for all locations (including empty ones)
    economic_data = {
        "GROWTH": [
            {
                "category": "GROWTH",
                "location": "US",
                "name": "Gross Domestic Product",
                "last": 2.1,
                "previous": 2.0,
                "change": 0.1,
            },
            {
                "category": "GROWTH",
                "location": "EU",
                "name": "Gross Domestic Product",
                "last": None,
                "previous": None,
                "change": None,
            },
            {
                "category": "GROWTH",
                "location": "JP",
                "name": "Gross Domestic Product",
                "last": None,
                "previous": None,
                "change": None,
            },
            {
                "category": "GROWTH",
                "location": "US",
                "name": "Eurozone GDP",
                "last": None,
                "previous": None,
                "change": None,
            },
            {
                "category": "GROWTH",
                "location": "EU",
                "name": "Eurozone GDP",
                "last": 1.5,
                "previous": 1.8,
                "change": -0.3,
            },
            {
                "category": "GROWTH",
                "location": "JP",
                "name": "Eurozone GDP",
                "last": None,
                "previous": None,
                "change": None,
            },
        ],
        "INFLATION": [
            {
                "category": "INFLATION",
                "location": "US",
                "name": "CPI Inflation",
                "last": 3.7,
                "previous": 3.5,
                "change": 0.2,
            },
            {
                "category": "INFLATION",
                "location": "EU",
                "name": "CPI Inflation",
                "last": None,
                "previous": None,
                "change": None,
            },
            {
                "category": "INFLATION",
                "location": "JP",
                "name": "CPI Inflation",
                "last": 2.6,
                "previous": 2.4,
                "change": 0.2,
            },
        ],
    }

    context = {
        "reference_date": reference_date,
        "default_reference_date": default_reference_date,
        "locations": locations,
        "economic_data": economic_data,
        "upcoming_events": [
            {
                "name": "US CPI Inflation",
                "publish_date": datetime(2025, 10, 10, 14, 30),
            },
            {
                "name": "ECB Rate Decision",
                "publish_date": datetime(2025, 10, 12, 13, 0),
            },
        ],
    }
    return render(request, "data_visualization/economic_overview.html", context)
