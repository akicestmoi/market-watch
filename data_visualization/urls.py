from django.urls import path

from data_visualization.views import (
    central_banks_recap_view,
    economic_charts_view,
    economic_recap_view,
    management_view,
    market_charts_view,
    market_recap_view,
)

urlpatterns = [
    path("market-recap/", market_recap_view, name="market-recap"),
    path("market-charts/", market_charts_view, name="market-charts"),
    path("economic-recap/", economic_recap_view, name="economic-recap-view"),
    path("economic-charts/", economic_charts_view, name="economic-charts-view"),
    path("central-banks-recap/", central_banks_recap_view, name="central-banks-recap"),
    path("management/", management_view, name="management"),
]
