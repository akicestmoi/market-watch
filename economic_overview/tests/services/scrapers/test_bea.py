"""Tests for the BEA NIPA government-expenditure scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import BEA_NIPA_MILLIONS_TO_BILLIONS
from economic_overview.services.scrapers.bea import (
    _download_bea_government_expenditures_by_function,
    get_data_from_bea,
)
from economic_overview.services.scrapers.common import ScrapingResult


class TestBeaGovernmentExpendituresByFunction(TestCase):
    """Tests for BEA NIPA Table 3.16 government current expenditures by function."""

    MOCK_BEA_T31600_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/bea/data/"
        "government_expenditures_by_function_success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_bea.cache_clear()
        _download_bea_government_expenditures_by_function.cache_clear()

    @override_settings(BEA_API_KEY="test-bea-key")
    @patch("economic_overview.services.scrapers.bea.requests.get")
    def test_get_data_from_bea_government_expenditures_total(self, mock_get):
        """
        GIVEN a successful BEA NIPA T31600 JSON response
        WHEN getting the total government current expenditures ticker
        THEN line 1 annual values are returned in billions, newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_BEA_T31600_SUCCESS
        )

        result = get_data_from_bea(
            "bea_t31600_total",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=10168689 * BEA_NIPA_MILLIONS_TO_BILLIONS,
                comment="",
            ),
            ScrapingResult(
                period=date(2023, 1, 1),
                data_value=9402978 * BEA_NIPA_MILLIONS_TO_BILLIONS,
                comment="",
            ),
        ]

    @override_settings(BEA_API_KEY="test-bea-key")
    @patch("economic_overview.services.scrapers.bea.requests.get")
    def test_get_data_from_bea_government_expenditures_function_lines(self, mock_get):
        """
        GIVEN one BEA NIPA T31600 response
        WHEN getting General Public Service then Income Security for 2024
        THEN each ticker reads its own line and the table is downloaded once
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_BEA_T31600_SUCCESS
        )

        general_public_service = get_data_from_bea(
            "bea_t31600_general_public_service",
            "2024",
            EconomicPublicationFrequencyChoices.ANNUAL,
        )
        income_security = get_data_from_bea(
            "bea_t31600_income_security",
            "2024",
            EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert general_public_service == [
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=1936366 * BEA_NIPA_MILLIONS_TO_BILLIONS,
                comment="",
            )
        ]
        assert income_security == [
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=2267452 * BEA_NIPA_MILLIONS_TO_BILLIONS,
                comment="",
            )
        ]
        assert mock_get.call_count == 1

    @override_settings(BEA_API_KEY="test-bea-key")
    @patch("economic_overview.services.scrapers.bea.requests.get")
    def test_get_data_from_bea_government_expenditures_quarterly_unsupported(
        self, mock_get
    ):
        """
        GIVEN an annual-only T31600 ticker
        WHEN requesting it at quarterly frequency
        THEN an unsupported-frequency error result is returned without HTTP calls
        """
        result = get_data_from_bea(
            "bea_t31600_health",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for BEA NIPA scrape: "
                    f"{EconomicPublicationFrequencyChoices.QUARTERLY}"
                ),
            )
        ]
        mock_get.assert_not_called()

    @override_settings(BEA_API_KEY="test-bea-key")
    @patch("economic_overview.services.scrapers.bea.requests.get")
    def test_get_data_from_bea_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown BEA ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_bea("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported BEA ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()
