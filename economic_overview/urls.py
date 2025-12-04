from django.urls import path

from economic_overview.views.economic_data_views import (
    EconomicDataDetailedView,
    GenerateBaseEconomicIndicatorInformationView,
    IngestEconomicDataView,
    IngestSpecificEconomicDataView,
)
from economic_overview.views.publication_schedules_views import (
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
