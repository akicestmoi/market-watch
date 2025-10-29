import json
from datetime import date, datetime

from django.shortcuts import render
from pandas.tseries.offsets import BDay

import data_visualization.services.visualization_services as data_visualization_services
import market_overview.services.market_data_services as market_data_services
from data_visualization.services.visualization_services import (
    ChartDuration,
    MarketChartsFrontData,
)
from economic_overview.models import EconomicDataLocationChoices
from market_overview.models import AssetClassChoices, LocationChoices


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

    reference_market_prices = market_data_services.get_all_asset_prices_for_date(
        reference_date
    )
    if not reference_market_prices:
        base_context["error_message"] = (
            f"No data found for reference date: {reference_date}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    previous_market_prices = market_data_services.get_all_asset_prices_for_date(
        previous_date
    )
    if not previous_market_prices:
        base_context["error_message"] = (
            f"No data found for reference date: {previous_date}."
        )
        return render(request, "data_visualization/market_recap.html", base_context)

    data_to_display = data_visualization_services.format_data_for_market_recap_display(
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
    return render(request, "data_visualization/market_recap.html", context)


def market_charts_view(request):
    """Market Charts View."""
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
    dropdown_values = data_visualization_services.get_market_charts_dropdown_values()

    # Get Label
    labels = data_visualization_services.get_market_charts_labels(
        dropdown_values, MarketChartsFrontData(**front_data)
    )

    # Get Market Data
    market_data = data_visualization_services.get_market_charts_market_data(
        reference_date, previous_curve_date, MarketChartsFrontData(**front_data)
    )

    # Return all to Front
    context = {
        "reference_date": reference_date.isoformat(),
        "previous_curve_date": previous_curve_date.isoformat(),
        "default_reference_date": default_values["reference_date"],
        "default_previous_curve_date": default_values["previous_curve_date"],
        "dropdown_values": json.dumps(dropdown_values, default=str),
        "selected_values": json.dumps(selected_values),
        "labels": json.dumps(labels),
        "market_data": json.dumps(market_data, default=str),
    }
    if error_message:
        context.update(error_message)
    return render(request, "data_visualization/market_charts.html", context)


def economic_recap_view(request):
    """Economic Overview View."""
    locations = [loc for loc in EconomicDataLocationChoices.ordered() if loc != "EU"]
    economic_data = data_visualization_services.get_economic_recap_data(locations)
    upcoming_events = data_visualization_services.get_economic_recap_upcoming_events()
    context = {
        "locations": locations,
        "economic_data": economic_data,
        "upcoming_events": upcoming_events,
    }
    return render(request, "data_visualization/economic_recap.html", context)
