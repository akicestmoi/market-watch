"""HTTP routes for market/economic/CB recaps, charts, and management UI."""

from django.urls import path

from data_visualization.views.central_banks_recap import central_banks_recap_view
from data_visualization.views.economic_charts import economic_charts_view
from data_visualization.views.economic_events import economic_events_view
from data_visualization.views.economic_recap import economic_recap_view
from data_visualization.views.management import management_view
from data_visualization.views.market_charts import market_charts_view
from data_visualization.views.market_recap import market_recap_view
from data_visualization.views.sector_analysis import sector_analysis_view

urlpatterns = [
    path("market-recap/", market_recap_view, name="market-recap"),
    path("sector-analysis/", sector_analysis_view, name="sector-analysis"),
    path("economic-events/", economic_events_view, name="economic-events"),
    path("market-charts/", market_charts_view, name="market-charts"),
    path("economic-recap/", economic_recap_view, name="economic-recap-view"),
    path("economic-charts/", economic_charts_view, name="economic-charts-view"),
    path("central-banks-recap/", central_banks_recap_view, name="central-banks-recap"),
    path("management/", management_view, name="management"),
]
