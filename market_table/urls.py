from django.urls import path

from market_table.views import (
    data_visualization_view,
    market_recap_view,
    economic_overview_view,
)

urlpatterns = [
    path("market-recap/", market_recap_view, name="market-recap"),
    path("data-visualization/", data_visualization_view, name="data-visualization"),
    path("economic-overview/", economic_overview_view, name="economic-overview-view"),
]
