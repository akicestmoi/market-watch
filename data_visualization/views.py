"""Page and API views for recaps, charts, and the management console."""

import json
from datetime import date, datetime

from django.shortcuts import render

import data_visualization.services.central_banks_recap as central_banks_recap
import data_visualization.services.database_management as database_management
import data_visualization.services.economic_charts as economic_charts
import data_visualization.services.economic_events as economic_events
import data_visualization.services.economic_recap as economic_recap
import data_visualization.services.market_charts as market_charts
import data_visualization.services.market_recap as market_recap
import market_overview.services.market_data as market_data
from central_banks_overview.models import CentralBankChoices
from core.services import get_market_watch_as_of_date, get_previous_business_day
from data_visualization.services.config import ECONOMIC_RECAP_LOCATIONS
from data_visualization.services.economic_charts import EconomicChartsFrontData
from data_visualization.services.market_charts import (
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
    default_reference_date = get_market_watch_as_of_date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    default_previous_date = get_previous_business_day(default_reference_date)
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

    reference_market_prices = market_data.get_all_asset_prices_for_date(reference_date)
    if not reference_market_prices:
        errors["reference_market_prices"] = (
            f"No data found for reference date {reference_date}."
        )

    previous_market_prices = market_data.get_all_asset_prices_for_date_without_holidays(
        previous_date
    )
    if not previous_market_prices:
        errors["previous_market_prices"] = (
            f"No data found for reference date {previous_date}."
        )

    data_to_display = market_recap.format_data_for_market_recap_display(
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

    fx_matrix = market_recap.get_fx_prices_matrix(reference_date, previous_date)
    day_events_by_location = market_recap.get_day_events_grouped_by_location(
        reference_date
    )

    context = {
        **base_context,
        "data_to_display": data_to_display,
        "left_asset_classes": left_asset_classes,
        "right_asset_classes": right_asset_classes,
        "fx_matrix": fx_matrix,
        "fx_matrix_order": market_recap.FX_MATRIX_ORDER,
        "day_events_by_location": day_events_by_location,
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/market_recap.html", context)


def sector_analysis_view(request):
    """Sector analysis view."""
    return render(request, "data_visualization/sector_analysis.html")


def economic_events_view(request):
    """Economic events calendar view."""
    upcoming_weeks = economic_events.group_upcoming_events_by_week()
    context = {
        "upcoming_weeks": upcoming_weeks,
    }
    return render(request, "data_visualization/economic_events.html", context)


def market_charts_view(request):
    """Market Charts View."""
    # Default Values
    default_values = {
        "reference_date": get_market_watch_as_of_date().isoformat(),
        "previous_curve_date": get_previous_business_day(
            get_market_watch_as_of_date()
        ).isoformat(),
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
    dropdown_values = market_charts.get_market_charts_dropdown_values()

    # Get Label
    labels = market_charts.get_market_charts_labels(
        dropdown_values, MarketChartsFrontData(**front_data)
    )

    # Get Market Data
    charts_data = market_charts.get_market_charts_data(
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
        "market_data": json.dumps(charts_data, default=str),
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/market_charts.html", context)


def economic_recap_view(request):
    """Economic Overview View."""
    economic_data = economic_recap.get_economic_recap_data(ECONOMIC_RECAP_LOCATIONS)
    location_codes = [loc.value for loc in ECONOMIC_RECAP_LOCATIONS]
    context = {
        "locations": location_codes,
        "economic_data": economic_data,
        "economic_data_json": json.dumps(economic_data, default=str),
        "locations_json": json.dumps(location_codes),
    }
    return render(request, "data_visualization/economic_recap.html", context)


def economic_charts_view(request):
    """Economic Charts View."""
    # Same category stack across regions; confidence series differs by region
    # (see ECONOMIC_CHARTS_DEFAULT_CONFIDENCE_TYPE_BY_LOCATION). Europe defaults
    # to DE / ES / IT / FR curves.
    us_defaults = economic_charts.get_default_indicator_selections(
        EconomicDataLocationChoices.US,
    )
    eu_defaults = economic_charts.get_default_eu_indicator_selections()
    fr_defaults = economic_charts.get_default_indicator_selections(
        EconomicDataLocationChoices.FR,
    )
    jp_defaults = economic_charts.get_default_indicator_selections(
        EconomicDataLocationChoices.JP,
    )
    default_values = {
        "region": str(EconomicDataLocationChoices.US.label),
        "period_window": economic_charts.ChartPeriodWindow.FIVE_YEARS.value,
        **{f"us_{key}": value for key, value in us_defaults.items()},
        **{f"eu_{key}": value for key, value in eu_defaults.items()},
        **{f"fr_{key}": value for key, value in fr_defaults.items()},
        **{f"jp_{key}": value for key, value in jp_defaults.items()},
    }

    front_data = {
        key: request.GET.get(key, default_values[key]) for key in default_values.keys()
    }
    errors = {}

    selected_values = {**front_data}
    location = EconomicDataLocationChoices.from_label(
        selected_values.get("region", default_values["region"])
    )
    selected_region = str(location.label)
    selected_values["region"] = selected_region
    front_data["region"] = selected_region

    period_window = economic_charts.ChartPeriodWindow(
        selected_values.get("period_window", default_values["period_window"])
    )

    dropdown_values = economic_charts.get_economic_charts_dropdown_values(location)

    selected_indicators_by_category = (
        economic_charts.get_selected_indicators_by_category(
            location,
            EconomicChartsFrontData(**front_data),
        )
    )
    economic_data = economic_charts.get_economic_charts_data(
        location,
        selected_indicators_by_category,
        period_window=period_window,
    )

    context = {
        "region": selected_region,
        "period_window": period_window.value,
        "period_window_options": [
            period_window_option.value
            for period_window_option in economic_charts.ChartPeriodWindow
        ],
        "dropdown_values": json.dumps(dropdown_values, default=str),
        "economic_data": json.dumps(economic_data, default=str),
        "categories": json.dumps(EconomicDataCategoryChoices.get_labels()),
        "selected_values": json.dumps(selected_values),
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/economic_charts.html", context)


def central_banks_recap_view(request):
    """Central Banks Overview View."""
    default_reference_date = get_market_watch_as_of_date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    default_previous_date = get_previous_business_day(default_reference_date)
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
            cb_data_items = central_banks_recap.get_central_bank_data_item(
                central_bank, reference_date
            )
        except Exception as e:
            errors[f"{central_bank.value}_data_item"] = (
                f"Error getting central bank data item for {central_bank.label}: {e}"
            )

        try:
            probability_matrix = (
                central_banks_recap.get_central_bank_formatted_probability_matrix(
                    central_bank, reference_date
                )
            )
        except Exception as e:
            errors[f"{central_bank.value}_probability_matrix"] = (
                f"Error getting probability matrix for {central_bank.label}: {e}"
            )

        try:
            previous_probability_matrix = (
                central_banks_recap.get_central_bank_formatted_probability_matrix(
                    central_bank, previous_date
                )
            )
            probability_change_matrix = (
                central_banks_recap.get_formatted_probability_matrix_changes(
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
    database_info = database_management.get_database_information()
    context = {
        "database_info": json.dumps(database_info, default=str),
    }
    return render(request, "data_visualization/management.html", context)
