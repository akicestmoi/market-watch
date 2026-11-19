"""Tests for the METI retail sales value index scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.meti import (
    _parse_meti_operating_ratio_workbook,
    _parse_meti_retail_sales_index_workbook,
    get_data_from_meti,
)


class TestMetiDataIngestion(TestCase):
    """Tests for METI Current Survey of Commerce retail sales index scraping."""

    MOCK_RETAIL_INDEX_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/meti/data/retail_sales_index_sa.xlsx"
    )
    MOCK_OPERATING_RATIO_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/meti/data/operating_ratio_mfg_sa.xlsx"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_meti.cache_clear()

    def test_parse_meti_retail_sales_index_workbook(self):
        """
        GIVEN a METI SA monthly retail sales index workbook fixture
        WHEN parsing values
        THEN monthly index levels are returned newest-first
        """
        result = _parse_meti_retail_sales_index_workbook(self.MOCK_RETAIL_INDEX_XLSX)
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=116.6, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=117.4, comment=""),
            ScrapingResult(period=date(2026, 5, 1), data_value=120.8, comment=""),
        ]

    @patch("economic_overview.services.scrapers.meti.requests.get")
    def test_get_data_from_meti_success(self, mock_get):
        """
        GIVEN the METI retail sales index Excel download
        WHEN getting retail sales index levels
        THEN parsed index levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_RETAIL_INDEX_XLSX, text=""
        )

        result = get_data_from_meti(
            "retail_sales_index_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1), data_value=116.6, comment=""
        )

    def test_parse_meti_operating_ratio_workbook(self):
        """
        GIVEN a METI monthly SA manufacturing operating-ratio workbook fixture
        WHEN parsing the Manufacturing total row
        THEN monthly index levels are returned newest-first
        """
        result = _parse_meti_operating_ratio_workbook(self.MOCK_OPERATING_RATIO_XLSX)
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=100.0, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=99.7, comment=""),
            ScrapingResult(period=date(2026, 7, 1), data_value=102.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.meti.requests.get")
    def test_get_data_from_meti_operating_ratio_success(self, mock_get):
        """
        GIVEN the METI operating-ratio Excel download
        WHEN getting operating_ratio_mfg_sa
        THEN parsed index levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_OPERATING_RATIO_XLSX, text=""
        )

        result = get_data_from_meti(
            "operating_ratio_mfg_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1), data_value=100.0, comment=""
        )
