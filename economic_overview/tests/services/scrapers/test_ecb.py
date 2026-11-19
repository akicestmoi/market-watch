"""Tests for the ECB Data Portal QSA and DWA scrapers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import ECB_DWA_WEALTH_GINI_TICKER
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.ecb import get_data_from_ecb


class TestEcbDataIngestion(TestCase):
    """Tests for ECB QSA household debt-to-income and DWA wealth scraping."""

    MOCK_ECB_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/ecb/data/success.csv"
    ).decode()
    MOCK_ECB_DWA_GINI_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/ecb/data/dwa_gini_success.csv"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_ecb.cache_clear()

    @patch("economic_overview.services.scrapers.ecb.requests.get")
    def test_get_data_from_ecb_success(self, mock_get):
        """
        GIVEN a successful ECB csvdata response
        WHEN getting household debt-to-income for France
        THEN quarterly ratios are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_ECB_CSV.encode(), text=self.MOCK_ECB_CSV
        )

        result = get_data_from_ecb(
            "qsa_hh_loans_to_gdi",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=90.85, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=90.82, comment=""),
        ]

    @patch("economic_overview.services.scrapers.ecb.requests.get")
    def test_get_data_from_ecb_dwa_wealth_gini_keeps_q4_as_annual(self, mock_get):
        """
        GIVEN a successful ECB DWA wealth-gini csvdata response
        WHEN getting annual wealth Gini for France
        THEN only Q4 observations are kept as calendar-year points
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_ECB_DWA_GINI_CSV.encode(),
            text=self.MOCK_ECB_DWA_GINI_CSV,
        )

        result = get_data_from_ecb(
            ECB_DWA_WEALTH_GINI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2025, 1, 1), data_value=71.20, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=71.01, comment=""),
        ]

    @patch("economic_overview.services.scrapers.ecb.requests.get")
    def test_get_data_from_ecb_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown ECB ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_ecb("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported ECB ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()
