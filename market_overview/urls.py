from django.urls import path

from market_overview.views.asset_views import (
    AssetDetailsView,
    GenerateBaseAssetsDataView,
    GetAssetNamesView,
)
from market_overview.views.holiday_views import HolidaysDetailsView, IngestHolidaysView
from market_overview.views.logs_views import GetPriceUpdateLogsView
from market_overview.views.price_views import (
    BulkUpdateAssetsPricesView,
    CsvBulkUpdateAssetsPricesView,
    GetAssetsWithoutPricesView,
    GetMarketPriceView,
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
    path("prices/get-assets-without-prices", GetAssetsWithoutPricesView.as_view()),
    path("prices/bulk-update", BulkUpdateAssetsPricesView.as_view()),
    path("prices/bulk-update-from-csv", CsvBulkUpdateAssetsPricesView.as_view()),
    path("prices/get-price-update-logs", GetPriceUpdateLogsView.as_view()),
    path("holidays/ingest", IngestHolidaysView.as_view()),
    path("holidays", HolidaysDetailsView.as_view()),
]
