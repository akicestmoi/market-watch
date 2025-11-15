from django.urls import path

from .views import (
    AssetDetailsView,
    BulkUpdateAssetsPricesView,
    CalculatePriceChangeView,
    CsvBulkUpdateAssetsPricesView,
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
    path("asset/generate-base-assets-data", GenerateBaseAssetsDataView.as_view()),
    path("asset/get-asset-names", GetAssetNamesView.as_view()),
    path("asset", AssetDetailsView.as_view()),
    path("prices/ingest", IngestMarketPricesView.as_view()),
    path(
        "prices/ingest-specific",
        IngestSpecificAssetMarketPricesView.as_view(),
    ),
    path("prices", GetMarketPriceView.as_view()),
    path("prices/list-all", ListMarketPricesView.as_view()),
    path("prices/get-yield-curve", GetYieldCurveView.as_view()),
    path("prices/get-historical-prices", GetHistoricalPricesView.as_view()),
    path("prices/calculate-price-change", CalculatePriceChangeView.as_view()),
    path("prices/get-assets-without-prices", GetAssetsWithoutPricesView.as_view()),
    path("prices/bulk-update", BulkUpdateAssetsPricesView.as_view()),
    path("prices/bulk-update-from-csv", CsvBulkUpdateAssetsPricesView.as_view()),
    path("prices/get-price-update-logs", GetPriceUpdateLogsView.as_view()),
]
