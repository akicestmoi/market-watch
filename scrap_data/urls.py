from django.urls import path

from .views import (
    CalculatePriceChangeView,
    DatabaseInteractionView,
    GetAssetNamesView,
    GetHistoricalPricesView,
    GetYieldCurveView,
    ScrapDataView,
    ScrapAssetDataView,
)

urlpatterns = [
    path("", DatabaseInteractionView.as_view()),
    path("ingest-market-prices", ScrapDataView.as_view()),
    path("ingest-asset-market-prices", ScrapAssetDataView.as_view()),
    path("calculate-price-change", CalculatePriceChangeView.as_view()),
    path("get-yield-curve", GetYieldCurveView.as_view()),
    path("get-historical-prices", GetHistoricalPricesView.as_view()),
    path("get-asset-names", GetAssetNamesView.as_view()),
]
