"""Management console page view."""

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import data_visualization.services.database_management as database_management
from central_banks_overview.models import CentralBankChoices
from economic_overview.models.economic_indicators import (
    EconomicIndicatorInformationModel,
)
from market_overview.models import AssetModel


def management_view(request: HttpRequest) -> HttpResponse:
    """Management View."""
    database_info = database_management.get_database_information()
    # Usage of dict: catalog lists for the management console front-end.
    management_catalog = {
        "assetShortNames": list(
            AssetModel.objects.order_by("short_name").values_list(
                "short_name", flat=True
            )
        ),
        "indicatorNames": list(
            EconomicIndicatorInformationModel.objects.order_by("full_name").values_list(
                "full_name", flat=True
            )
        ),
        "centralBanks": [choice.value for choice in CentralBankChoices.ordered()],
    }
    # Usage of dict: Django template context for the management page.
    context = {
        "database_info": json.dumps(database_info, default=str),
        "management_catalog": json.dumps(management_catalog),
    }
    return render(request, "data_visualization/management.html", context)
