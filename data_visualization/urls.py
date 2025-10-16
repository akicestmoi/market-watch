from django.urls import path

from data_visualization.views import (
    data_visualization_view,
    economic_recap_view,
    market_recap_view,
)

urlpatterns = [
    path("market-recap/", market_recap_view, name="market-recap"),
    path("market-charts/", data_visualization_view, name="data-visualization"),
    path("economic-recap/", economic_recap_view, name="economic-recap-view"),
]
