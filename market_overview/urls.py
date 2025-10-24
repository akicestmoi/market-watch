from django.urls import path

from .views import (
    BulkUpdateAssetsPricesView,
    CalculatePriceChangeView,
    GenerateBaseAssetsDataView,
    GetAssetNamesView,
    GetAssetsWithoutPricesView,
    GetHistoricalPricesView,
    GetMarketPriceView,
    GetPriceUpdateLogsView,
    GetYieldCurveView,
    IngestMarketPricesView,
    IngestSpecificAssetMarketPricesView,
    ListMarketPricesView,
)

urlpatterns = [
    path("generate-base-assets-data", GenerateBaseAssetsDataView.as_view()),
    path("get-asset-names", GetAssetNamesView.as_view()),
    path("ingest-market-prices", IngestMarketPricesView.as_view()),
    path("ingest-asset-market-prices", IngestSpecificAssetMarketPricesView.as_view()),
    path("get-price", GetMarketPriceView.as_view()),
    path("list-prices", ListMarketPricesView.as_view()),
    path("get-yield-curve", GetYieldCurveView.as_view()),
    path("get-historical-prices", GetHistoricalPricesView.as_view()),
    path("calculate-price-change", CalculatePriceChangeView.as_view()),
    path("get-assets-without-prices", GetAssetsWithoutPricesView.as_view()),
    path("bulk-update-prices", BulkUpdateAssetsPricesView.as_view()),
    path("get-price-update-logs", GetPriceUpdateLogsView.as_view()),
]
