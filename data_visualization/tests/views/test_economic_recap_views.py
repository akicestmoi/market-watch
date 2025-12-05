from datetime import date, datetime, timezone

from django.test import Client, TestCase
from freezegun import freeze_time  # type: ignore[reportMissingImports]

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
        # Current is the latest data value
        # Previous is the data value for the previous period
        # Change is the difference between the current and previous data values
        # Period is the period of the current data value
        assert economic_data == {
            EconomicDataCategoryChoices.GROWTH.value: [
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.US,
                    "name": "US Indicator",
                    "current": 115.0,
                    "previous": 100.0,
                    "change": 15.0,
                    "period": "Jul.25",
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.FR,
                    "name": "US Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.JP,
                    "name": "US Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.US,
                    "name": "Second US Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.FR,
                    "name": "Second US Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.JP,
                    "name": "Second US Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.US,
                    "name": "JP Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.FR,
                    "name": "JP Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.GROWTH.value,
                    "location": EconomicDataLocationChoices.JP,
                    "name": "JP Indicator",
                    "current": 55.0,
                    "previous": None,
                    "change": None,
                    "period": "2025",
                },
            ],
            EconomicDataCategoryChoices.CONFIDENCE.value: [
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.US,
                    "name": "FR Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.FR,
                    "name": "FR Indicator",
                    "current": 210.0,
                    "previous": 200.0,
                    "change": 10.0,
                    "period": "25Q3",
                },
                {
                    "category": EconomicDataCategoryChoices.CONFIDENCE.value,
                    "location": EconomicDataLocationChoices.JP,
                    "name": "FR Indicator",
                    "current": None,
                    "previous": None,
                    "change": None,
                    "period": None,
                },
            ],
        }

        upcoming_events = response.context.get("upcoming_events")
        assert upcoming_events is not None
        assert upcoming_events == [
            {
                "date": "2025-07-15",
                "date_display": "2025-07-15",
                "events": [
                    {
                        "name": "US Indicator",
                        "location": "United States",
                        "publication_date": datetime(
                            2025, 7, 15, 0, 0, 0, tzinfo=timezone.utc
                        ),
                        "time_str": "00:00",
                    }
                ],
            }
        ]

    @freeze_time("2025-08-01")
    def test_economic_recap_view_past_upcoming_events(self):
        """
        GIVEN a publication schedule with a current publication date in the past
        WHEN accessing economic recap view
        THEN the view renders successfully with no upcoming events
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert response.context.get("upcoming_events") == []
