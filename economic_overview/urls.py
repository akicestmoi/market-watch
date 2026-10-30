"""HTTP routes for economic data and publication schedules."""

from django.urls import path

from economic_overview.views.economic_data import (
    EconomicDataDetailedView,
    GenerateBaseEconomicIndicatorInformationView,
    IngestHistoricalEconomicDataView,
    IngestLatestEconomicDataView,
    IngestSpecificEconomicDataView,
)
from economic_overview.views.publication_schedules import UpdatePublicationScheduleView

urlpatterns = [
    path(
        "indicator/generate-base-information",
        GenerateBaseEconomicIndicatorInformationView.as_view(),
    ),
    path("indicator/ingest", IngestLatestEconomicDataView.as_view()),
    path("indicator/ingest-historical", IngestHistoricalEconomicDataView.as_view()),
    path("indicator/ingest-specific", IngestSpecificEconomicDataView.as_view()),
    path("indicator", EconomicDataDetailedView.as_view()),
    path("schedule/update", UpdatePublicationScheduleView.as_view()),
]
