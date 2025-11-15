from django.urls import path

from .views import (
    BulkUpdateStirFuturesPricesView,
    CentralBankMeetingDatesIngestionView,
    CsvBulkUpdateStirFuturesPricesView,
    GetCentralBankMeetingDatesView,
    GetCentralBankProbabilityMatrixView,
    ListStirFuturesPricesView,
    StirFuturesPriceIngestionView,
)

urlpatterns = [
    path("meeting-dates", GetCentralBankMeetingDatesView.as_view()),
    path(
        "meeting-dates/ingest",
        CentralBankMeetingDatesIngestionView.as_view(),
    ),
    path("stir-futures/ingest", StirFuturesPriceIngestionView.as_view()),
    path("stir-futures", ListStirFuturesPricesView.as_view()),
    path("stir-futures/bulk-update", BulkUpdateStirFuturesPricesView.as_view()),
    path(
        "stir-futures/bulk-update-from-csv",
        CsvBulkUpdateStirFuturesPricesView.as_view(),
    ),
    path("probability-matrix", GetCentralBankProbabilityMatrixView.as_view()),
]
