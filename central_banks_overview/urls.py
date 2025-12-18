from django.urls import path

from .views.cb_data_views import CentralBankDataIngestionView, ListCentralBankDataView
from .views.cb_meetings_views import (
    CentralBankMeetingDatesIngestionView,
    GetCentralBankMeetingDatesView,
)
from .views.probability_matrix_views import GetCentralBankProbabilityMatrixView
from .views.stir_futures_prices_views import (
    BulkUpdateStirFuturesPricesView,
    CsvBulkUpdateStirFuturesPricesView,
    EstrPriceIngestionViaPdfView,
    ListStirFuturesPricesView,
    StirFuturesPriceIngestionView,
)

urlpatterns = [
    path("data", ListCentralBankDataView.as_view()),
    path("data/ingest", CentralBankDataIngestionView.as_view()),
    path("meeting-dates", GetCentralBankMeetingDatesView.as_view()),
    path(
        "meeting-dates/ingest",
        CentralBankMeetingDatesIngestionView.as_view(),
    ),
    path("stir-futures", ListStirFuturesPricesView.as_view()),
    path("stir-futures/ingest", StirFuturesPriceIngestionView.as_view()),
    path(
        "stir-futures/ingest-estr-pdf",
        EstrPriceIngestionViaPdfView.as_view(),
    ),
    path("stir-futures/bulk-update", BulkUpdateStirFuturesPricesView.as_view()),
    path(
        "stir-futures/bulk-update-from-csv",
        CsvBulkUpdateStirFuturesPricesView.as_view(),
    ),
    path("probability-matrix", GetCentralBankProbabilityMatrixView.as_view()),
]
