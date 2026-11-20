"""Market charts page view."""

import json
from datetime import date, datetime
from typing import NamedTuple

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import data_visualization.services.market_charts as market_charts
from core.services.calendar import (
    get_market_watch_as_of_date,
    get_previous_business_day,
)
from data_visualization.services.market_charts import (
    ChartDuration,
    MarketChartsFrontData,
)
from market_overview.models.common import LocationChoices


def _get_market_charts_default_values() -> dict[str, str | None]:
    """Return default GET param values for the market charts page."""
    # Usage of dict: GET param names mapped to default string values.
    as_of = get_market_watch_as_of_date()
    return {
        "reference_date": as_of.isoformat(),
        "previous_curve_date": get_previous_business_day(as_of).isoformat(),
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


def _collect_market_charts_validation_errors(
    reference_date: date,
    previous_curve_date: date,
) -> dict[str, str]:
    """Collect validation errors for market charts date inputs."""
    # Usage of dict: template error_messages keys by field name.
    errors: dict[str, str] = {}
    if reference_date >= date.today():
        errors["reference_date"] = (
            f"Reference date {reference_date} must be before today {date.today()}."
        )

    if reference_date <= previous_curve_date:
        errors["previous_curve_date"] = (
            f"Reference date {reference_date} must be greater than the previous curve date {previous_curve_date}."
        )
    return errors


def _get_market_charts_query_value(
    request: HttpRequest,
    key: str,
    default_values: dict[str, str | None],
) -> str | None:
    """Return one market-charts GET value, falling back to the page default."""
    if key in request.GET:
        return request.GET.get(key)
    return default_values[key]


class _MarketChartsParsedFrontData(NamedTuple):
    """Raw GET bag for the template plus typed chart front data."""

    # Usage of dict: raw GET param bag for selected_values JSON.
    raw_front_data: dict[str, str | None]
    front_data: MarketChartsFrontData


def _get_required_market_charts_string(
    raw_front_data: dict[str, str | None],
    key: str,
) -> str:
    """Return a non-None string for a required market-charts front-data field."""
    value = raw_front_data[key]
    return value if value is not None else ""


def _get_market_charts_front_data(
    raw_front_data: dict[str, str | None],
) -> MarketChartsFrontData:
    """Build typed market-charts front data from the raw GET param bag."""
    reference_date = datetime.fromisoformat(
        _get_required_market_charts_string(raw_front_data, "reference_date")
    ).date()
    previous_curve_date = datetime.fromisoformat(
        _get_required_market_charts_string(raw_front_data, "previous_curve_date")
    ).date()
    spread_rate = raw_front_data["spread_rate"]
    return MarketChartsFrontData(
        reference_date=reference_date,
        previous_curve_date=previous_curve_date,
        yield_curve_location=_get_required_market_charts_string(
            raw_front_data, "yield_curve_location"
        ),
        stock_name=_get_required_market_charts_string(raw_front_data, "stock_name"),
        fx_name=_get_required_market_charts_string(raw_front_data, "fx_name"),
        crypto_name=_get_required_market_charts_string(raw_front_data, "crypto_name"),
        commodity_name=_get_required_market_charts_string(
            raw_front_data, "commodity_name"
        ),
        main_rate=_get_required_market_charts_string(raw_front_data, "main_rate"),
        spread_rate=spread_rate if spread_rate else None,
        stock_chart_duration=ChartDuration(
            _get_required_market_charts_string(raw_front_data, "stock_chart_duration")
        ),
        fx_chart_duration=ChartDuration(
            _get_required_market_charts_string(raw_front_data, "fx_chart_duration")
        ),
        crypto_chart_duration=ChartDuration(
            _get_required_market_charts_string(raw_front_data, "crypto_chart_duration")
        ),
        commodity_chart_duration=ChartDuration(
            _get_required_market_charts_string(
                raw_front_data, "commodity_chart_duration"
            )
        ),
        spread_rates_chart_duration=ChartDuration(
            _get_required_market_charts_string(
                raw_front_data, "spread_rates_chart_duration"
            )
        ),
        stock_name_compare=_get_required_market_charts_string(
            raw_front_data, "stock_name_compare"
        ),
        fx_name_compare=_get_required_market_charts_string(
            raw_front_data, "fx_name_compare"
        ),
        crypto_name_compare=_get_required_market_charts_string(
            raw_front_data, "crypto_name_compare"
        ),
        commodity_name_compare=_get_required_market_charts_string(
            raw_front_data, "commodity_name_compare"
        ),
    )


def _parse_market_charts_front_data(
    request: HttpRequest,
    default_values: dict[str, str | None],
) -> _MarketChartsParsedFrontData:
    """Parse GET params into the selected-values bag and typed front data."""
    # Usage of dict: raw GET param bag for selected_values JSON.
    raw_front_data: dict[str, str | None] = {
        key: _get_market_charts_query_value(request, key, default_values)
        for key in default_values
    }
    return _MarketChartsParsedFrontData(
        raw_front_data=raw_front_data,
        front_data=_get_market_charts_front_data(raw_front_data),
    )


def market_charts_view(request: HttpRequest) -> HttpResponse:
    """Market Charts View."""
    default_values = _get_market_charts_default_values()
    parsed_front_data = _parse_market_charts_front_data(request, default_values)
    front_data = parsed_front_data.front_data
    reference_date = front_data["reference_date"]
    previous_curve_date = front_data["previous_curve_date"]
    errors = _collect_market_charts_validation_errors(
        reference_date, previous_curve_date
    )

    # Usage of dict: selected control values passed to the template as JSON.
    selected_values: dict[str, str | None] = {
        **parsed_front_data.raw_front_data,
        "previous_curve_date": previous_curve_date.isoformat(),
    }

    dropdown_values = market_charts.get_market_charts_dropdown_values()
    labels = market_charts.get_market_charts_labels(dropdown_values, front_data)
    charts_data = market_charts.get_market_charts_data(
        reference_date, previous_curve_date, front_data
    )

    # Usage of dict: Django template context for the market charts page.
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
