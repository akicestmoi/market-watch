"""Tests for US Census ACS Gini and PUMS Palma scrapers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import CENSUS_GINI_TICKER
from economic_overview.services.scrapers.census import (
    _calculate_weighted_palma_from_household_incomes,
    _parse_acs_gini_estimate,
    get_data_from_census,
)
from economic_overview.services.scrapers.common import ScrapingResult


class TestCensusScraper(TestCase):
    """Unit coverage for Census inequality helpers and scrape entry points."""

    def tearDown(self) -> None:
        """Clear the TTL cache after each test."""
        get_data_from_census.cache_clear()

    def test_parse_acs_gini_estimate(self):
        """
        GIVEN an ACS B19083 estimate on a 0–1 scale
        WHEN parsing for Front storage
        THEN the value is scaled to 0–100
        """
        assert _parse_acs_gini_estimate("0.4832") == 48.32
        assert _parse_acs_gini_estimate("not-a-number") is None

    def test_calculate_weighted_palma_from_household_incomes(self):
        """
        GIVEN ten equal-weight households with incomes 1…10
        WHEN computing the weighted Palma ratio
        THEN the result equals top-decile income over the bottom four
        """
        household_incomes = [float(income) for income in range(1, 11)]
        household_weights = [1.0] * 10
        assert _calculate_weighted_palma_from_household_incomes(
            household_incomes, household_weights
        ) == 10.0 / (1.0 + 2.0 + 3.0 + 4.0)

    @patch("economic_overview.services.scrapers.census._list_acs_gini_series")
    @patch("economic_overview.services.scrapers.census._get_census_api_key")
    def test_get_data_from_census_acs_gini(
        self, mock_get_api_key, mock_list_acs_gini_series
    ):
        """
        GIVEN a configured Census API key and one ACS Gini point
        WHEN scraping acs_b19083
        THEN that scaled Gini series is returned
        """
        mock_get_api_key.return_value = "test-key"
        mock_list_acs_gini_series.return_value = [
            ScrapingResult(period=date(2024, 1, 1), data_value=50.0, comment="")
        ]
        result = get_data_from_census(
            CENSUS_GINI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(period=date(2024, 1, 1), data_value=50.0, comment="")
        ]
        mock_list_acs_gini_series.assert_called_once_with("test-key")

    @patch("economic_overview.services.scrapers.census._get_census_api_key")
    def test_get_data_from_census_missing_api_key(self, mock_get_api_key):
        """
        GIVEN no Census API key
        WHEN scraping ACS Gini
        THEN a missing-key comment is returned
        """
        mock_get_api_key.return_value = ""
        result = get_data_from_census(
            CENSUS_GINI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="CENSUS_API_KEY is not configured.",
            )
        ]

    def test_get_data_from_census_unknown_ticker(self):
        """
        GIVEN an unsupported Census ticker
        WHEN scraping
        THEN an unsupported-ticker comment is returned
        """
        result = get_data_from_census(
            "unknown_census_ticker",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported CENSUS ticker: unknown_census_ticker",
            )
        ]
