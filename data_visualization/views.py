import json
from datetime import date, datetime

from django.shortcuts import render
from pandas.tseries.offsets import BDay

import data_visualization.services.central_bank_recap_services as central_bank_recap_services
import data_visualization.services.database_management_services as database_management_services
import data_visualization.services.economic_chart_services as economic_chart_services
import data_visualization.services.economic_recap_services as economic_recap_services
import data_visualization.services.market_chart_services as market_chart_services
import data_visualization.services.market_recap_services as market_recap_services
import market_overview.services.market_data_services as market_data_services
from central_banks_overview.models import CentralBankChoices
from data_visualization.services.economic_chart_services import EconomicChartsFrontData
from data_visualization.services.market_chart_services import (
    ChartDuration,
    MarketChartsFrontData,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
)
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

    errors = {}

    base_context = {
        "reference_date": reference_date.isoformat(),
        "previous_date": previous_date.isoformat(),
        "default_reference_date": default_reference_date.isoformat(),
        "default_previous_date": default_previous_date.isoformat(),
    }
    if reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date {reference_date} must be before today {date.today()}."
        )

    if reference_date <= previous_date:
        errors["previous_date"] = (
            f"Reference date {reference_date} must be greater than the previous date {previous_date}."
        )

    reference_market_prices = market_data_services.get_all_asset_prices_for_date(
        reference_date
    )
    if not reference_market_prices:
        errors["reference_market_prices"] = (
            f"No data found for reference date {reference_date}."
        )

    previous_market_prices = (
        market_data_services.get_all_asset_prices_for_date_without_holidays(
            previous_date
        )
    )
    if not previous_market_prices:
        errors["previous_market_prices"] = (
            f"No data found for reference date {previous_date}."
        )

    data_to_display = market_recap_services.format_data_for_market_recap_display(
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

    fx_matrix = market_recap_services.get_fx_prices_matrix(
        reference_date, previous_date
    )

    context = {
        **base_context,
        "data_to_display": data_to_display,
        "left_asset_classes": left_asset_classes,
        "right_asset_classes": right_asset_classes,
        "fx_matrix": fx_matrix,
        "fx_matrix_order": market_recap_services.FX_MATRIX_ORDER,
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/market_recap.html", context)


def market_charts_view(request):
    """Market Charts View."""
    # Default Values
    default_values = {
        "reference_date": (date.today() - BDay(1)).date().isoformat(),
        "previous_curve_date": (date.today() - BDay(2)).date().isoformat(),
        "yield_curve_location": str(LocationChoices.US.label),
        "stock_name": "DJIA",
        "fx_name": "EURUSD",
        "crypto_name": "BTC",
        "commodity_name": "Gold",
        "main_rate": "UST10Y",
        "spread_rate": None,
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

    errors = {}

    reference_date = datetime.fromisoformat(front_data["reference_date"]).date()
    if reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date {reference_date} must be before today {date.today()}."
        )

    previous_curve_date = datetime.fromisoformat(
        front_data["previous_curve_date"]
    ).date()
    if reference_date <= previous_curve_date:
        errors["previous_curve_date"] = (
            f"Reference date {reference_date} must be greater than the previous curve date {previous_curve_date}."
        )

    # Return Selected Values for Front/Back Interaction
    selected_values = {
        **front_data,
        "previous_curve_date": previous_curve_date.isoformat(),
    }

    # Dropdown values
    dropdown_values = market_chart_services.get_market_charts_dropdown_values()

    # Get Label
    labels = market_chart_services.get_market_charts_labels(
        dropdown_values, MarketChartsFrontData(**front_data)
    )

    # Get Market Data
    market_data = market_chart_services.get_market_charts_market_data(
        reference_date, previous_curve_date, MarketChartsFrontData(**front_data)
    )

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
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/market_charts.html", context)


def economic_recap_view(request):
    """Economic Overview View."""
    locations = [
        loc.value for loc in EconomicDataLocationChoices.ordered() if loc.value != "EU"
    ]
    economic_data = economic_recap_services.get_economic_recap_data(locations)
    upcoming_events = economic_recap_services.get_economic_recap_upcoming_events()
    context = {
        "locations": locations,
        "economic_data": economic_data,
        "upcoming_events": upcoming_events,
    }
    return render(request, "data_visualization/economic_recap.html", context)


def economic_charts_view(request):
    """Economic Charts View."""
    # Default Values
    default_values = {
        "zone": str(EconomicDataLocationChoices.US.label),
        "us_growth_indicator": "",
        "us_inflation_indicator": "",
        "us_government_indicator": "",
        "us_labour_indicator": "",
        "us_housing_indicator": "",
        "us_production_indicator": "",
        "us_confidence_indicator": "",
        "us_sales_indicator": "",
        "fr_growth_indicator": "",
        "fr_inflation_indicator": "",
        "fr_government_indicator": "",
        "fr_labour_indicator": "",
        "fr_housing_indicator": "",
        "fr_production_indicator": "",
        "fr_confidence_indicator": "Aggregate Business Confidence",
        "fr_sales_indicator": "",
        "jp_growth_indicator": "",
        "jp_inflation_indicator": "",
        "jp_government_indicator": "",
        "jp_labour_indicator": "",
        "jp_housing_indicator": "",
        "jp_production_indicator": "",
        "jp_confidence_indicator": "",
        "jp_sales_indicator": "",
    }

    # Get Data from Front
    front_data = {
        key: request.GET.get(key, default_values[key]) for key in default_values.keys()
    }
    errors = {}

    # Return Selected Values for Front/Back Interaction
    selected_values = {**front_data}
    selected_zone = selected_values.get("zone", default_values["zone"])

    # Dropdown values
    dropdown_values = economic_chart_services.get_economic_charts_dropdown_values(
        selected_zone
    )

    # Economic data
    selected_indicators_by_category = (
        economic_chart_services.get_selected_indicators_by_category(
            selected_zone,
            EconomicChartsFrontData(**front_data),
        )
    )
    economic_data = economic_chart_services.get_economic_charts_data(
        selected_zone, selected_indicators_by_category
    )

    context = {
        "zone": selected_zone,
        "dropdown_values": json.dumps(dropdown_values, default=str),
        "economic_data": json.dumps(economic_data, default=str),
        "categories": json.dumps(
            [str(category.label) for category in EconomicDataCategoryChoices.ordered()]
        ),
        "selected_values": json.dumps(selected_values),
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/economic_charts.html", context)


def central_banks_recap_view(request):
    """Central Banks Overview View."""
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

    errors = {}

    base_context = {
        "reference_date": reference_date.isoformat(),
        "previous_date": previous_date.isoformat(),
        "default_reference_date": default_reference_date.isoformat(),
        "default_previous_date": default_previous_date.isoformat(),
    }
    if reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date: {reference_date} must be before today: {date.today()}."
        )

    central_banks_data = {}
    for central_bank in CentralBankChoices.ordered():
        cb_data_items = []
        probability_matrix = None
        probability_change_matrix = None

        try:
            cb_data_items = central_bank_recap_services.get_central_bank_data_item(
                central_bank, reference_date
            )
        except Exception as e:
            errors[f"{central_bank.value}_data_item"] = (
                f"Error getting central bank data item for {central_bank.label}: {e}"
            )

        try:
            probability_matrix = central_bank_recap_services.get_central_bank_formatted_probability_matrix(
                central_bank, reference_date
            )
        except Exception as e:
            errors[f"{central_bank.value}_probability_matrix"] = (
                f"Error getting probability matrix for {central_bank.label}: {e}"
            )

        try:
            previous_probability_matrix = central_bank_recap_services.get_central_bank_formatted_probability_matrix(
                central_bank, previous_date
            )
            probability_change_matrix = (
                central_bank_recap_services.get_formatted_probability_matrix_changes(
                    probability_matrix,
                    previous_probability_matrix,
                    previous_date=previous_date,
                )
            )
        except Exception as e:
            errors[f"{central_bank.value}_probability_change_matrix"] = (
                f"Error getting probability change matrix for {central_bank.label}: {e}"
            )

        central_banks_data[central_bank] = {
            "display_name": central_bank.label,
            "data": cb_data_items,
            "probability_matrix": probability_matrix,
            "probability_change_matrix": probability_change_matrix,
        }

    context = {
        **base_context,
        "central_banks_data": central_banks_data,
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/central_banks_recap.html", context)


def management_view(request):
    """Management View."""
    database_info = database_management_services.get_database_information()
    context = {
        "database_info": json.dumps(database_info, default=str),
    }
    return render(request, "data_visualization/management.html", context)
