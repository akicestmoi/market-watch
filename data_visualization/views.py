import json
from datetime import date, datetime
from typing import List

import pandas as pd
from django.shortcuts import render
from pandas.tseries.offsets import BDay

import market_overview.services as market_overview_services
from data_visualization.services import format_data_for_display
from market_overview.models import AssetClassChoices, AssetTypeChoices, LocationChoices
from market_overview.services import AssetNames


def _get_asset_full_name(asset_names: List[AssetNames], asset_short_name) -> str:
    """Get asset full_name."""
    return next(
        (
            asset["full_name"]
            for asset in asset_names
            if asset["short_name"] == asset_short_name
        ),
        None,
    )


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
    if reference_date <= previous_date:
        context = {
            "error_message": "reference_date must be greater than previous_date.",
            "reference_date": reference_date,
            "previous_date": previous_date,
        }
        return render(request, "data_visualization/market_recap.html", context)

    reference_market_prices = market_overview_services.get_all_asset_prices_for_date(
        reference_date
    )
    if not reference_market_prices:
        context = {
            "error_message": f"No data found for reference date: {reference_date}.",
            "reference_date": reference_date,
            "previous_date": previous_date,
        }
        return render(request, "data_visualization/market_recap.html", context)

    previous_market_prices = market_overview_services.get_all_asset_prices_for_date(
        previous_date
    )
    if not previous_market_prices:
        context = {
            "error_message": f"No data found for reference date: {previous_date}.",
            "reference_date": reference_date,
            "previous_date": previous_date,
        }
        return render(request, "data_visualization/market_recap.html", context)

    data_to_display = format_data_for_display(
        reference_market_prices, previous_market_prices
    )

    left_asset_classes = [
        AssetClassChoices.STOCKS.label,
        AssetClassChoices.COMMODITIES.label,
        AssetClassChoices.FX.label,
        AssetClassChoices.CRYPTO.label,
        AssetClassChoices.OTHERS.label,
        AssetClassChoices.CB_RATES.label,
    ]
    right_asset_classes = [
        AssetClassChoices.RATES.label,
    ]
    context = {
        "data_to_display": data_to_display,
        "reference_date": reference_date.isoformat(),
        "previous_date": previous_date.isoformat(),
        "default_reference_date": default_reference_date.isoformat(),
        "default_previous_date": default_previous_date.isoformat(),
        "left_asset_classes": left_asset_classes,
        "right_asset_classes": right_asset_classes,
    }
    return render(request, "data_visualization/market_recap.html", context)


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
    }

    # Get Data from Front
    reference_date = request.GET.get("reference_date", default_values["reference_date"])
    previous_curve_date = request.GET.get(
        "previous_curve_date", default_values["previous_curve_date"]
    )
    yield_curve_location = request.GET.get(
        "yield_curve_location", default_values["yield_curve_location"]
    )
    stock_name = request.GET.get("stock_name", default_values["stock_name"])
    fx_name = request.GET.get("fx_name", default_values["fx_name"])
    crypto_name = request.GET.get("crypto_name", default_values["crypto_name"])
    commodity_name = request.GET.get("commodity_name", default_values["commodity_name"])
    main_rate = request.GET.get("main_rate", default_values["main_rate"])
    spread_rate = request.GET.get("spread_rate", default_values["spread_rate"])
    stock_name_compare = request.GET.get("stock_name_compare", "")
    fx_name_compare = request.GET.get("fx_name_compare", "")
    crypto_name_compare = request.GET.get("crypto_name_compare", "")
    commodity_name_compare = request.GET.get("commodity_name_compare", "")

    # Return Selected Values for Front Interaction
    # Automatically takes default values at first
    selected_values = {
        "yield_curve_location": yield_curve_location,
        "stock_name": stock_name,
        "fx_name": fx_name,
        "crypto_name": crypto_name,
        "commodity_name": commodity_name,
        "main_rate": main_rate,
        "spread_rate": spread_rate,
        "previous_curve_date": previous_curve_date,
        "stock_name_compare": stock_name_compare,
        "fx_name_compare": fx_name_compare,
        "crypto_name_compare": crypto_name_compare,
        "commodity_name_compare": commodity_name_compare,
    }

    # Data Validation
    reference_date = datetime.fromisoformat(reference_date).date()
    previous_curve_date = datetime.fromisoformat(previous_curve_date).date()
    if reference_date <= previous_curve_date:
        context = {
            "error_message": "reference_date must be greater than previous_curve_date.",
            "reference_date": reference_date,
            "previous_curve_date": previous_curve_date,
        }
        return render(request, "data_visualization/market_recap.html", context)

    # Get Dropdown values
    stock_assets = market_overview_services.get_asset_names(
        {"asset_class": AssetClassChoices.STOCKS}
    )
    rates_assets = market_overview_services.get_asset_names(
        {"asset_type": AssetTypeChoices.GOVERNMENT_BOND_RATE}
    )
    fx_assets = market_overview_services.get_asset_names(
        {"asset_class": AssetClassChoices.FX}
    )
    crypto_assets = market_overview_services.get_asset_names(
        {"asset_class": AssetClassChoices.CRYPTO}
    )
    commodity_assets = market_overview_services.get_asset_names(
        {"asset_class": AssetClassChoices.COMMODITIES}
    )
    dropdown_values = {
        "stocks": stock_assets,
        "fx": fx_assets,
        "crypto": crypto_assets,
        "commodity": commodity_assets,
        "rates": rates_assets,
        "locations": [str(choice.label) for choice in LocationChoices],
    }

    # Get Label
    labels = {
        "stocks": _get_asset_full_name(stock_assets, stock_name),
        "fx": _get_asset_full_name(fx_assets, fx_name),
        "crypto": _get_asset_full_name(crypto_assets, crypto_name),
        "commodity": _get_asset_full_name(commodity_assets, commodity_name),
        "yield_curve_location": yield_curve_location,
        "main_rate": main_rate,
        "spread_rate": spread_rate,
        "stock_name_compare": (
            _get_asset_full_name(stock_assets, stock_name_compare)
            if stock_name_compare
            else None
        ),
        "fx_name_compare": (
            _get_asset_full_name(fx_assets, fx_name_compare)
            if fx_name_compare
            else None
        ),
        "crypto_name_compare": (
            _get_asset_full_name(crypto_assets, crypto_name_compare)
            if crypto_name_compare
            else None
        ),
        "commodity_name_compare": (
            _get_asset_full_name(commodity_assets, commodity_name_compare)
            if commodity_name_compare
            else None
        ),
    }

    # Get Market Data
    stock_prices = market_overview_services.get_historical_prices(
        stock_name, end_date=reference_date
    )
    reference_yield_curve = market_overview_services.get_yield_curve(
        reference_date, LocationChoices.from_label(yield_curve_location)
    )
    previous_yield_curve = market_overview_services.get_yield_curve(
        previous_curve_date, LocationChoices.from_label(yield_curve_location)
    )
    fx_prices = market_overview_services.get_historical_prices(
        fx_name, end_date=reference_date
    )
    crypto_prices = market_overview_services.get_historical_prices(
        crypto_name, end_date=reference_date
    )
    commodity_prices = market_overview_services.get_historical_prices(
        commodity_name, end_date=reference_date
    )
    main_rate_historical_yield = market_overview_services.get_historical_prices(
        main_rate, end_date=reference_date
    )
    spread_rate_historical_yield = market_overview_services.get_historical_prices(
        spread_rate, end_date=reference_date
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

    # Get comparison data if comparison assets are selected
    stock_prices_compare = None
    fx_prices_compare = None
    crypto_prices_compare = None
    commodity_prices_compare = None

    if stock_name_compare:
        stock_prices_compare = market_overview_services.get_historical_prices(
            stock_name_compare, end_date=reference_date
        )
    if fx_name_compare:
        fx_prices_compare = market_overview_services.get_historical_prices(
            fx_name_compare, end_date=reference_date
        )
    if crypto_name_compare:
        crypto_prices_compare = market_overview_services.get_historical_prices(
            crypto_name_compare, end_date=reference_date
        )
    if commodity_name_compare:
        commodity_prices_compare = market_overview_services.get_historical_prices(
            commodity_name_compare, end_date=reference_date
        )

    market_data = {
        "stock_prices": stock_prices,
        "stock_prices_compare": stock_prices_compare,
        "reference_yield_curve": reference_yield_curve,
        "previous_yield_curve": previous_yield_curve,
        "fx_prices": fx_prices,
        "fx_prices_compare": fx_prices_compare,
        "crypto_prices": crypto_prices,
        "crypto_prices_compare": crypto_prices_compare,
        "commodity_prices": commodity_prices,
        "commodity_prices_compare": commodity_prices_compare,
        "spread_rates": spread_rate_df[["price_date", "price"]].to_dict(
            orient="records"
        ),
    }

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
    return render(request, "data_visualization/data_visualization.html", context)


def economic_overview_view(request):
    """Economic Overview View."""
    default_reference_date = (date.today() - BDay(1)).date()
    reference_date = request.GET.get(
        "reference_date", default_reference_date.isoformat()
    )
    reference_date = datetime.fromisoformat(reference_date).date()

    locations = ["US", "EU", "JP"]

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
