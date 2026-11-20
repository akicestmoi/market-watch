"""Market recap page view."""

import json
from datetime import date

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import data_visualization.services.market_recap as market_recap
import market_overview.services.market_data as market_data
from data_visualization.services.config import FX_MATRIX_ORDER
from data_visualization.views.common import (
    RecapReferenceDates,
    get_recap_dates_base_context,
    parse_recap_reference_and_previous_dates,
)
from market_overview.models.market_prices import AssetClassChoices, MarketPriceModel


def _collect_market_recap_validation_errors(
    dates: RecapReferenceDates,
    reference_market_prices: list[MarketPriceModel],
    previous_market_prices: list[MarketPriceModel],
) -> dict[str, str]:
    """Collect validation errors for the market recap date and price inputs."""
    # Usage of dict: template error_messages keys by field name.
    errors: dict[str, str] = {}
    if dates.reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date {dates.reference_date} must be before today {date.today()}."
        )

    if dates.reference_date <= dates.previous_date:
        errors["previous_date"] = (
            f"Reference date {dates.reference_date} must be greater than the previous date {dates.previous_date}."
        )

    if not reference_market_prices:
        errors["reference_market_prices"] = (
            f"No data found for reference date {dates.reference_date}."
        )

    if not previous_market_prices:
        errors["previous_market_prices"] = (
            f"No data found for reference date {dates.previous_date}."
        )
    return errors


def market_recap_view(request: HttpRequest) -> HttpResponse:
    """Market recap view to render price changes."""
    recap_dates = parse_recap_reference_and_previous_dates(request)
    base_context = get_recap_dates_base_context(recap_dates)

    reference_market_prices = market_data.get_all_asset_prices_for_date(
        recap_dates.reference_date
    )
    previous_market_prices = market_data.get_all_asset_prices_for_date_without_holidays(
        recap_dates.previous_date
    )
    errors = _collect_market_recap_validation_errors(
        recap_dates,
        reference_market_prices,
        previous_market_prices,
    )

    data_to_display = market_recap.format_market_prices_for_recap_display(
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

    fx_matrix = market_recap.get_fx_prices_matrix(
        recap_dates.reference_date, recap_dates.previous_date
    )
    day_events_by_location = market_recap.get_day_events_grouped_by_location(
        recap_dates.reference_date
    )

    # Usage of dict: Django template context for the market recap page.
    context = {
        **base_context,
        "data_to_display": data_to_display,
        "left_asset_classes": left_asset_classes,
        "right_asset_classes": right_asset_classes,
        "fx_matrix": fx_matrix,
        "fx_matrix_order": FX_MATRIX_ORDER,
        "day_events_by_location": day_events_by_location,
    }
    if errors:
        context["error_messages"] = json.dumps(errors)
    return render(request, "data_visualization/market_recap.html", context)
