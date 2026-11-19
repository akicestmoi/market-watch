"""Tests for the University of Michigan Surveys of Consumers scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.univ_michigan import (
    _parse_univ_michigan_sca_table_csv,
    get_data_from_univ_michigan,
)


class TestUnivMichiganDataIngestion(TestCase):
    """Tests for Michigan SCA table scraping."""

    MOCK_TABLE_30_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/michigan/data/sca_table_30.csv"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_univ_michigan.cache_clear()

    def test_parse_univ_michigan_sca_table_csv(self):
        """
        GIVEN a Michigan SCA Table 30 CSV fixture
        WHEN parsing Relative index scores
        THEN monthly levels are returned newest-first
        """
        result = _parse_univ_michigan_sca_table_csv(self.MOCK_TABLE_30_CSV)
        assert result == [
            ScrapingResult(period=date(2025, 12, 1), data_value=48.0, comment=""),
            ScrapingResult(period=date(2025, 11, 1), data_value=40.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.univ_michigan.requests.post")
    def test_get_data_from_univ_michigan_table_30_success(self, mock_post):
        """
        GIVEN a successful Michigan data-archive CSV response
        WHEN getting Table 30 unemployment expectations
        THEN Relative index scores are returned
        """
        mock_post.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_TABLE_30_CSV.encode(),
            text=self.MOCK_TABLE_30_CSV,
        )

        result = get_data_from_univ_michigan(
            "sca_table_30",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 12, 1), data_value=48.0, comment=""
        )
