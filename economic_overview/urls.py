from django.urls import path

from .views import (
    GenerateBaseEconomicIndicatorInformationView,
    IngestEconomicDataView,
    UpdatePublicationScheduleView,
)

urlpatterns = [
    path(
        "generate-base-economic-indicator-information",
        GenerateBaseEconomicIndicatorInformationView.as_view(),
    ),
    path("ingest-economic-data", IngestEconomicDataView.as_view()),
    path("update-publication-schedules", UpdatePublicationScheduleView.as_view()),
]
