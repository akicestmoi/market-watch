from django.urls import path

from .views import (
    EconomicDataDetailedView,
    GenerateBaseEconomicIndicatorInformationView,
    IngestEconomicDataView,
    IngestSpecificEconomicDataView,
    UpdatePublicationScheduleView,
)

urlpatterns = [
    path(
        "indicator/generate-base-information",
        GenerateBaseEconomicIndicatorInformationView.as_view(),
    ),
    path("indicator/ingest", IngestEconomicDataView.as_view()),
    path("indicator/ingest-specific", IngestSpecificEconomicDataView.as_view()),
    path("indicator", EconomicDataDetailedView.as_view()),
    path("schedule/update", UpdatePublicationScheduleView.as_view()),
]
