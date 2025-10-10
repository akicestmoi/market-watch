from django.urls import path

from data_visualization.views import (
    data_visualization_view,
    economic_overview_view,
    market_recap_view,
)

urlpatterns = [
    path("market-overview/", market_recap_view, name="market-recap"),
    path("market-charts/", data_visualization_view, name="data-visualization"),
    path("economic-overview/", economic_overview_view, name="economic-overview-view"),
]
