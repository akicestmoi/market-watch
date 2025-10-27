from django.urls import path

from .views import (
    GenerateBaseEconomicIndicatorInformationView,
    IngestEconomicDataView,
    IngestSpecificEconomicDataView,
    UpdatePublicationScheduleView,
)

urlpatterns = [
    path(
        "generate-base-economic-indicator-information",
        GenerateBaseEconomicIndicatorInformationView.as_view(),
    ),
    path("ingest-economic-data", IngestEconomicDataView.as_view()),
    path("ingest-specific-economic-data", IngestSpecificEconomicDataView.as_view()),
    path("update-publication-schedules", UpdatePublicationScheduleView.as_view()),
]
