"""Tests for economic recap views."""

import json
from datetime import date, datetime, timezone

from django.test import Client, TestCase
from freezegun import freeze_time

from economic_overview.models.common import (
    EconomicDataLocationChoices,
    EconomicDataSourceChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorMeasureTypeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel

_EXPECTED_REGIONS = ["US", "FR", "JP"]
_EXPECTED_LOCATIONS = ["US"]
_EXPECTED_AS_OF_YEARS = list(range(2025, 2009, -1))
_EXPECTED_AS_OF_MONTH_CHOICES = [
    {"value": month, "label": label}
    for month, label in enumerate(
        [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ],
        start=1,
    )
]
_EXPECTED_AS_OF_LATEST = {
    "as_of_years": _EXPECTED_AS_OF_YEARS,
    "as_of_year": None,
    "as_of_quarter": None,
    "as_of_month": None,
    "as_of_month_display": None,
    "as_of_month_choices": _EXPECTED_AS_OF_MONTH_CHOICES,
    "as_of_end_date": None,
    "as_of_query": "",
    "as_of_available_years": [2025],
    "as_of_available_quarters": [],
    "as_of_available_months": [],
    "comparison": "Latest",
    "as_of_json": json.dumps(
        {
            "year": None,
            "quarter": None,
            "month": None,
            "month_display": None,
            "end_date": None,
            "comparison": "Latest",
            "available_years": [2025],
            "available_quarters": [],
            "available_months": [],
            # json.dumps stringifies object keys.
            "quarter_end_month_by_quarter": {
                "1": 3,
                "2": 6,
                "3": 9,
                "4": 12,
            },
        }
    ),
}
_EXPECTED_ECONOMIC_DATA = [
    {
        "category": EconomicDataCategoryChoices.MACROECONOMICS,
        "indicator_row_count": 2,
        "subcategories": [
            {
                "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                "indicator_row_count": 2,
                "entries": [
                    {
                        "category": EconomicDataCategoryChoices.MACROECONOMICS,
                        "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                        "location": EconomicDataLocationChoices.US,
                        "name": "US Indicator",
                        "display_name": "US Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "source": EconomicDataSourceChoices.INSEE,
                        "technical_name": "us_indicator",
                        "description": "",
                        "source_url": "",
                        "measure_type": IndicatorMeasureTypeChoices.FLOW,
                        "is_annualized": False,
                        "is_seasonally_adjusted": True,
                        "price_basis": None,
                        "parent_series_label": "",
                        "expansion_relation": "",
                        "base_year": None,
                        "base_unit": None,
                        "base_currency": None,
                        "default_mode": "Raw",
                        "supports_vs_gdp": False,
                        "current": 115.0,
                        "previous": 100.0,
                        "change": 15.0,
                        "period": "Jul.25",
                        "time_series": [
                            {
                                "period": "Jun.25",
                                "period_date": "2025-06-15",
                                "value": 100.0,
                            },
                            {
                                "period": "Jul.25",
                                "period_date": "2025-07-15",
                                "value": 115.0,
                            },
                        ],
                    },
                    {
                        "category": EconomicDataCategoryChoices.MACROECONOMICS,
                        "subcategory": EconomicDataSubcategoryChoices.GROWTH,
                        "location": EconomicDataLocationChoices.US,
                        "name": "Second US Indicator",
                        "display_name": "Second US Indicator",
                        "frequency": EconomicPublicationFrequencyChoices.MONTHLY,
                        "source": EconomicDataSourceChoices.INSEE,
                        "technical_name": "second_us_indicator",
                        "description": "",
                        "source_url": "",
                        "measure_type": IndicatorMeasureTypeChoices.FLOW,
                        "is_annualized": False,
                        "is_seasonally_adjusted": True,
                        "price_basis": None,
                        "parent_series_label": "",
                        "expansion_relation": "",
                        "base_year": None,
                        "base_unit": None,
                        "base_currency": None,
                        "default_mode": "Raw",
                        "supports_vs_gdp": False,
                        "current": None,
                        "previous": None,
                        "change": None,
                        "period": None,
                        "time_series": [],
                    },
                ],
            }
        ],
    },
]


class TestEconomicRecapView(TestCase):
    """Test cases for economic_recap_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-recap/"
        self.indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="US Indicator",
            full_name="US Indicator Name",
            technical_name="us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="Second US Indicator",
            full_name="Second US Indicator Name",
            technical_name="second_us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.BUSINESS,
            subcategory=EconomicDataSubcategoryChoices.CONFIDENCE,
            series_label="FR Indicator",
            full_name="FR Indicator Name",
            technical_name="fr_indicator",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_jp = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.MACROECONOMICS,
            subcategory=EconomicDataSubcategoryChoices.GROWTH,
            series_label="JP Indicator",
            full_name="JP Indicator Name",
            technical_name="jp_indicator",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565532",
        )
        past_period = date(2024, 6, 15)
        first_period = date(2025, 6, 15)
        second_period = date(2025, 7, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=first_period,
            data_value=100.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=second_period,
            data_value=115.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=past_period,
            data_value=180.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=first_period,
            data_value=200.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=second_period,
            data_value=210.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_jp,
            period=first_period,
            data_value=55.0,
        )
        PublicationScheduleModel.objects.create(
            indicator=self.indicator_fr,
            current_publication_date=datetime(
                2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc
            ),
            next_publication_date=None,
        )
        PublicationScheduleModel.objects.create(
            indicator=self.indicator_us,
            current_publication_date=datetime(
                2025, 7, 15, 0, 0, 0, tzinfo=timezone.utc
            ),
            next_publication_date=datetime(2025, 8, 14, 0, 0, 0, tzinfo=timezone.utc),
        )

    @freeze_time("2025-07-01")
    def test_economic_recap_view_success(self):
        """
        GIVEN economic data services
        WHEN accessing economic recap view
        THEN the view renders successfully with the default US region
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert {
            "regions": response.context["regions"],
            "selected_region": response.context["selected_region"],
            "locations": response.context["locations"],
            "economic_data": response.context["economic_data"],
            "economic_data_json": response.context["economic_data_json"],
            "nominal_gdp_json": response.context["nominal_gdp_json"],
            "locations_json": response.context["locations_json"],
            "as_of_years": response.context["as_of_years"],
            "as_of_year": response.context["as_of_year"],
            "as_of_quarter": response.context["as_of_quarter"],
            "as_of_month": response.context["as_of_month"],
            "as_of_month_display": response.context["as_of_month_display"],
            "as_of_month_choices": response.context["as_of_month_choices"],
            "as_of_end_date": response.context["as_of_end_date"],
            "as_of_query": response.context["as_of_query"],
            "as_of_available_years": response.context["as_of_available_years"],
            "as_of_available_quarters": response.context["as_of_available_quarters"],
            "as_of_available_months": response.context["as_of_available_months"],
            "comparison": response.context["comparison"],
            "as_of_json": response.context["as_of_json"],
        } == {
            "regions": _EXPECTED_REGIONS,
            "selected_region": "US",
            "locations": _EXPECTED_LOCATIONS,
            "economic_data": _EXPECTED_ECONOMIC_DATA,
            "economic_data_json": json.dumps(_EXPECTED_ECONOMIC_DATA, default=str),
            "nominal_gdp_json": json.dumps([], default=str),
            "locations_json": json.dumps(_EXPECTED_LOCATIONS),
            **_EXPECTED_AS_OF_LATEST,
        }
        assert "upcoming_events" not in response.context

    @freeze_time("2025-07-01")
    def test_economic_recap_view_region_query(self):
        """
        GIVEN economic data for FR
        WHEN accessing economic recap with region=FR
        THEN only the France region payload is returned
        """
        response = self.client.get(self.base_url, {"region": "FR"})

        assert response.status_code == 200
        expected_economic_data = [
            {
                "category": EconomicDataCategoryChoices.BUSINESS,
                "indicator_row_count": 1,
                "subcategories": [
                    {
                        "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                        "indicator_row_count": 1,
                        "entries": [
                            {
                                "category": EconomicDataCategoryChoices.BUSINESS,
                                "subcategory": EconomicDataSubcategoryChoices.CONFIDENCE,
                                "location": EconomicDataLocationChoices.FR,
                                "name": "FR Indicator",
                                "display_name": "FR Indicator",
                                "frequency": EconomicPublicationFrequencyChoices.QUARTERLY,
                                "source": EconomicDataSourceChoices.INSEE,
                                "technical_name": "fr_indicator",
                                "description": "",
                                "source_url": "",
                                "measure_type": IndicatorMeasureTypeChoices.FLOW,
                                "is_annualized": False,
                                "is_seasonally_adjusted": True,
                                "price_basis": None,
                                "parent_series_label": "",
                                "expansion_relation": "",
                                "base_year": None,
                                "base_unit": None,
                                "base_currency": None,
                                "default_mode": "Raw",
                                "supports_vs_gdp": False,
                                "current": 210.0,
                                "previous": 200.0,
                                "change": 10.0,
                                "period": "25Q3",
                                "time_series": [
                                    {
                                        "period": "24Q2",
                                        "period_date": "2024-06-15",
                                        "value": 180.0,
                                    },
                                    {
                                        "period": "25Q2",
                                        "period_date": "2025-06-15",
                                        "value": 200.0,
                                    },
                                    {
                                        "period": "25Q3",
                                        "period_date": "2025-07-15",
                                        "value": 210.0,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        assert {
            "selected_region": response.context["selected_region"],
            "locations": response.context["locations"],
            "economic_data": response.context["economic_data"],
        } == {
            "selected_region": "FR",
            "locations": ["FR"],
            "economic_data": expected_economic_data,
        }

    @freeze_time("2025-07-01")
    def test_economic_recap_view_unknown_region_falls_back_to_default(self):
        """
        GIVEN an unknown region query value
        WHEN accessing economic recap
        THEN the default US region is used
        """
        response = self.client.get(self.base_url, {"region": "ZZ"})

        assert response.status_code == 200
        assert response.context["selected_region"] == "US"
        assert response.context["locations"] == _EXPECTED_LOCATIONS
        assert response.context["economic_data"] == _EXPECTED_ECONOMIC_DATA

    @freeze_time("2025-08-01")
    def test_economic_recap_view_no_upcoming_events_in_context(self):
        """
        GIVEN publication schedules (including past ones)
        WHEN accessing economic recap view
        THEN upcoming releases are not part of the economic recap context
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert {
            "regions": response.context["regions"],
            "selected_region": response.context["selected_region"],
            "locations": response.context["locations"],
            "economic_data": response.context["economic_data"],
            "economic_data_json": response.context["economic_data_json"],
            "nominal_gdp_json": response.context["nominal_gdp_json"],
            "locations_json": response.context["locations_json"],
            "as_of_years": response.context["as_of_years"],
            "as_of_year": response.context["as_of_year"],
            "as_of_quarter": response.context["as_of_quarter"],
            "as_of_month": response.context["as_of_month"],
            "as_of_month_display": response.context["as_of_month_display"],
            "as_of_month_choices": response.context["as_of_month_choices"],
            "as_of_end_date": response.context["as_of_end_date"],
            "as_of_query": response.context["as_of_query"],
            "as_of_available_years": response.context["as_of_available_years"],
            "as_of_available_quarters": response.context["as_of_available_quarters"],
            "as_of_available_months": response.context["as_of_available_months"],
            "comparison": response.context["comparison"],
            "as_of_json": response.context["as_of_json"],
        } == {
            "regions": _EXPECTED_REGIONS,
            "selected_region": "US",
            "locations": _EXPECTED_LOCATIONS,
            "economic_data": _EXPECTED_ECONOMIC_DATA,
            "economic_data_json": json.dumps(_EXPECTED_ECONOMIC_DATA, default=str),
            "nominal_gdp_json": json.dumps([], default=str),
            "locations_json": json.dumps(_EXPECTED_LOCATIONS),
            **{
                **_EXPECTED_AS_OF_LATEST,
                "as_of_years": list(range(2025, 2009, -1)),
            },
        }
        assert "upcoming_events" not in response.context

    @freeze_time("2025-07-01")
    def test_economic_recap_view_as_of_quarter_query(self):
        """
        GIVEN as_of_year and as_of_quarter query params
        WHEN accessing economic recap
        THEN the as-of context uses that quarter end and omits as_of_month
        """
        response = self.client.get(
            self.base_url,
            {"region": "US", "as_of_year": "2025", "as_of_quarter": "2"},
        )

        assert response.status_code == 200
        assert {
            "as_of_year": response.context["as_of_year"],
            "as_of_quarter": response.context["as_of_quarter"],
            "as_of_month": response.context["as_of_month"],
            "as_of_month_display": response.context["as_of_month_display"],
            "as_of_end_date": response.context["as_of_end_date"],
            "as_of_query": response.context["as_of_query"],
            "as_of_available_years": response.context["as_of_available_years"],
            "as_of_available_quarters": response.context["as_of_available_quarters"],
            "as_of_available_months": response.context["as_of_available_months"],
        } == {
            "as_of_year": 2025,
            "as_of_quarter": 2,
            "as_of_month": None,
            "as_of_month_display": None,
            "as_of_end_date": "2025-06-30",
            "as_of_query": "as_of_year=2025&as_of_quarter=2",
            "as_of_available_years": [2025],
            "as_of_available_quarters": [2, 3],
            "as_of_available_months": [6, 7],
        }

    @freeze_time("2025-07-01")
    def test_economic_recap_view_as_of_month_wins_over_quarter(self):
        """
        GIVEN both as_of_quarter and as_of_month in the query
        WHEN accessing economic recap
        THEN month wins and quarter is cleared from the as-of context
        """
        response = self.client.get(
            self.base_url,
            {
                "region": "US",
                "as_of_year": "2025",
                "as_of_quarter": "2",
                "as_of_month": "5",
            },
        )

        assert response.status_code == 200
        assert {
            "as_of_year": response.context["as_of_year"],
            "as_of_quarter": response.context["as_of_quarter"],
            "as_of_month": response.context["as_of_month"],
            "as_of_month_display": response.context["as_of_month_display"],
            "as_of_end_date": response.context["as_of_end_date"],
            "as_of_query": response.context["as_of_query"],
        } == {
            "as_of_year": 2025,
            "as_of_quarter": None,
            "as_of_month": 5,
            "as_of_month_display": 5,
            "as_of_end_date": "2025-05-31",
            "as_of_query": "as_of_year=2025&as_of_month=5",
        }
