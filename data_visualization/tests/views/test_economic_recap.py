"""Tests for economic recap views."""

from datetime import date, datetime, timezone

from django.test import Client, TestCase
from freezegun import freeze_time

from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicDataSourceChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
)


class TestEconomicRecapView(TestCase):
    """Test cases for economic_recap_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/economic-recap/"
        self.indicator_us = EconomicIndicatorInformationModel.objects.create(
            id=1,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="US Indicator",
            name="US Indicator Name",
            technical_name="us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        EconomicIndicatorInformationModel.objects.create(
            id=2,
            location=EconomicDataLocationChoices.US,
            category=EconomicDataCategoryChoices.GROWTH,
            type="Second US Indicator",
            name="Second US Indicator Name",
            technical_name="second_us_indicator",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565531",
        )
        self.indicator_fr = EconomicIndicatorInformationModel.objects.create(
            id=3,
            location=EconomicDataLocationChoices.FR,
            category=EconomicDataCategoryChoices.CONFIDENCE,
            type="FR Indicator",
            name="FR Indicator Name",
            technical_name="fr_indicator",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            source=EconomicDataSourceChoices.INSEE,
            ticker="001565530",
        )
        self.indicator_jp = EconomicIndicatorInformationModel.objects.create(
            id=4,
            location=EconomicDataLocationChoices.JP,
            category=EconomicDataCategoryChoices.GROWTH,
            type="JP Indicator",
            name="JP Indicator Name",
            technical_name="jp_indicator",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            source=EconomicDataSourceChoices.JP_CABINET_OFFICE,
            ticker="001565532",
        )
        self.past_period = date(2024, 6, 15)
        self.first_period = date(2025, 6, 15)
        self.second_period = date(2025, 7, 15)
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=self.first_period,
            data_value=100.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_us,
            period=self.second_period,
            data_value=115.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=self.past_period,
            data_value=180.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=self.first_period,
            data_value=200.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_fr,
            period=self.second_period,
            data_value=210.0,
        )
        EconomicDataModel.objects.create(
            indicator=self.indicator_jp,
            period=self.first_period,
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
        THEN the view renders successfully with economic data
        """
        response = self.client.get(self.base_url)

        assert response.status_code == 200
        assert response.context.get("locations") == [
            EconomicDataLocationChoices.US,
            EconomicDataLocationChoices.FR,
            EconomicDataLocationChoices.JP,
        ]

        economic_data = response.context.get("economic_data")
        assert economic_data is not None
        us_growth = next(
            item
            for item in economic_data[EconomicDataCategoryChoices.GROWTH.value]
            if item["name"] == "US Indicator"
            and item["location"] == EconomicDataLocationChoices.US
        )
        assert us_growth["current"] == 115.0
        assert us_growth["previous"] == 100.0
        assert us_growth["change"] == 15.0
        assert us_growth["period"] == "Jul.25"
        assert us_growth["frequency"] == EconomicPublicationFrequencyChoices.MONTHLY
        assert len(us_growth["history"]) == 2

        fr_confidence = next(
            item
            for item in economic_data[EconomicDataCategoryChoices.CONFIDENCE.value]
            if item["name"] == "FR Indicator"
            and item["location"] == EconomicDataLocationChoices.FR
        )
        assert fr_confidence["current"] == 210.0
        assert fr_confidence["previous"] == 200.0
        assert fr_confidence["change"] == 10.0
        assert fr_confidence["period"] == "25Q3"
        assert len(fr_confidence["history"]) == 3

        assert "upcoming_events" not in response.context
        assert response.context.get("economic_data_json") is not None
        assert response.context.get("locations_json") is not None

    @freeze_time("2025-08-01")
    def test_economic_recap_view_no_upcoming_events_in_context(self):
        """
        GIVEN publication schedules (including past ones)
        WHEN accessing economic recap view
        THEN upcoming releases are not part of the economic recap context
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert "upcoming_events" not in response.context
