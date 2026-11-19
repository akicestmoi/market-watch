"""Tests for the IMF DataMapper and IL SDMX scrapers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.imf import get_data_from_imf


class TestImfDataIngestion(TestCase):
    """Tests for IMF DataMapper and International Liquidity scraping."""

    MOCK_IMF_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/imf/data/success.json"
    )
    MOCK_IMF_IL_RESERVES = load_json_mock(
        "economic_overview/tests/mock_web_data/imf/data/il_reserves_success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_imf.cache_clear()

    @patch("economic_overview.services.scrapers.imf.requests.get")
    def test_get_data_from_imf_success(self, mock_get):
        """
        GIVEN a successful IMF DataMapper payload
        WHEN getting primary balance for the United States
        THEN annual ratios are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_IMF_SUCCESS
        )

        result = get_data_from_imf(
            "GGXONLB_G01_GDP_PT",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="US",
        )
        assert result == [
            ScrapingResult(period=date(2024, 1, 1), data_value=-4.63, comment=""),
            ScrapingResult(period=date(2023, 1, 1), data_value=-4.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.imf.requests.get")
    def test_get_data_from_imf_fx_reserves_success(self, mock_get):
        """
        GIVEN a successful IMF IL SDMX reserves payload
        WHEN getting RXF11_REVS for the United States
        THEN monthly millions-of-USD stocks are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_IMF_IL_RESERVES
        )

        result = get_data_from_imf(
            "RXF11_REVS",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            location="US",
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 9, 1),
                data_value=float("242836430601.1308") / 1_000_000.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 8, 1),
                data_value=float("243800829074.6694") / 1_000_000.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 7, 1),
                data_value=float("241641649527.8553") / 1_000_000.0,
                comment="",
            ),
        ]

    @patch("economic_overview.services.scrapers.imf.requests.get")
    def test_get_data_from_imf_unsupported_location(self, mock_get):
        """
        GIVEN a location without an IMF area mapping
        WHEN getting data
        THEN an unsupported-location error result is returned
        """
        result = get_data_from_imf(
            "GGXONLB_G01_GDP_PT",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="XX",
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported IMF location: XX",
            )
        ]
        mock_get.assert_not_called()

    @patch("economic_overview.services.scrapers.imf.requests.get")
    def test_get_data_from_imf_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown IMF ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_imf("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported IMF ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()
