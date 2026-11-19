"""Tests for the OECD Economic Outlook SDMX scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    OECD_JP_RETAIL_VOLUME_TICKER,
    OECD_OUTPUT_GAP_TICKER,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.oecd import (
    _parse_oecd_time_period,
    get_data_from_oecd,
)


class TestOecdDataIngestion(TestCase):
    """Tests for OECD Economic Outlook SDMX scraping."""

    MOCK_OECD_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/oecd/data/success.json"
    )
    MOCK_OECD_INDSERV_RETAIL_VOLUME = load_json_mock(
        "economic_overview/tests/mock_web_data/oecd/data/indserv_retail_volume.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_oecd.cache_clear()

    def test_parse_oecd_time_period_monthly(self):
        """
        GIVEN an OECD monthly TIME_PERIOD label
        WHEN parsing it
        THEN the first day of that month is returned
        """
        assert _parse_oecd_time_period("2026-06") == date(2026, 6, 1)

    @patch("economic_overview.services.scrapers.oecd.requests.get")
    def test_get_data_from_oecd_success(self, mock_get):
        """
        GIVEN a successful OECD SDMX payload for USA GAP
        WHEN getting output-gap data for the United States
        THEN annual ratios are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_OECD_SUCCESS
        )

        result = get_data_from_oecd(
            OECD_OUTPUT_GAP_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="US",
        )
        assert result == [
            ScrapingResult(period=date(2021, 1, 1), data_value=-0.73, comment=""),
            ScrapingResult(period=date(2020, 1, 1), data_value=-4.22, comment=""),
            ScrapingResult(period=date(2019, 1, 1), data_value=0.15, comment=""),
        ]

    @patch("economic_overview.services.scrapers.oecd.requests.get")
    def test_get_data_from_oecd_jp_retail_volume(self, mock_get):
        """
        GIVEN a successful OECD INDSERV payload for Japan TOVM
        WHEN getting Japan retail sales volume
        THEN monthly index levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_OECD_INDSERV_RETAIL_VOLUME
        )

        result = get_data_from_oecd(
            OECD_JP_RETAIL_VOLUME_TICKER,
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            location="JP",
        )
        assert result == [
            ScrapingResult(period=date(2026, 6, 1), data_value=100.1613, comment=""),
            ScrapingResult(period=date(2026, 5, 1), data_value=104.3079, comment=""),
            ScrapingResult(period=date(2026, 4, 1), data_value=103.0348, comment=""),
        ]

    @patch("economic_overview.services.scrapers.oecd.requests.get")
    def test_get_data_from_oecd_unsupported_location(self, mock_get):
        """
        GIVEN a location without an OECD REF_AREA mapping
        WHEN getting data
        THEN an unsupported-location error result is returned
        """
        result = get_data_from_oecd(
            OECD_OUTPUT_GAP_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="XX",
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported OECD location: XX",
            )
        ]
        mock_get.assert_not_called()
