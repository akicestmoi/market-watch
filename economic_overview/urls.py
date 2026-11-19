"""HTTP routes for economic overview features."""

from django.urls import path

from economic_overview.views.economic_data import (
    EconomicDataDetailedView,
    GenerateBaseEconomicIndicatorInformationView,
    IngestHistoricalEconomicDataView,
    IngestLatestEconomicDataView,
    IngestSpecificEconomicDataView,
)
from economic_overview.views.industry_profitability import (
    IngestIndustryProfitabilityView,
)
from economic_overview.views.publication_update import (
    RunMonthlyPublicationUpdateView,
    UpdatePublicationScheduleView,
)
from economic_overview.views.trade_rankings import IngestTradeRankingsView

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
    path(
        "indicator/monthly-publication-update",
        RunMonthlyPublicationUpdateView.as_view(),
    ),
    path(
        "industry-profitability/ingest",
        IngestIndustryProfitabilityView.as_view(),
    ),
    path(
        "trade-rankings/ingest",
        IngestTradeRankingsView.as_view(),
    ),
]
