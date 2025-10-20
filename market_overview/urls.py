from django.urls import path

from .views import (
    BulkUpdateAssetsPricesView,
    CalculatePriceChangeView,
    DatabaseInteractionView,
    GetAssetNamesView,
    GetAssetsWithoutPricesView,
    GetHistoricalPricesView,
    GetPriceUpdateLogsView,
    GetYieldCurveView,
    IngestAssetDataView,
    IngestDataView,
)

urlpatterns = [
    path("", DatabaseInteractionView.as_view()),
    path("ingest-market-prices", IngestDataView.as_view()),
    path("ingest-asset-market-prices", IngestAssetDataView.as_view()),
    path("calculate-price-change", CalculatePriceChangeView.as_view()),
    path("get-yield-curve", GetYieldCurveView.as_view()),
    path("get-historical-prices", GetHistoricalPricesView.as_view()),
    path("get-asset-names", GetAssetNamesView.as_view()),
    path("get-price-update-logs", GetPriceUpdateLogsView.as_view()),
    path("get-assets-without-prices", GetAssetsWithoutPricesView.as_view()),
    path("bulk-update-prices", BulkUpdateAssetsPricesView.as_view()),
]
