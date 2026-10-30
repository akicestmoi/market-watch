"""Tests for the MLIT residential property price index scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.mlit import (
    _parse_mlit_rppi_workbook,
    get_data_from_mlit,
)


class TestMlitDataIngestion(TestCase):
    """Tests for MLIT Residential Property Price Index scraping."""

    MOCK_RPPI_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/mlit/data/rppi.xlsx"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_mlit.cache_clear()

    def test_parse_mlit_rppi_workbook(self):
        """
        GIVEN an MLIT nationwide SA RPPI workbook fixture
        WHEN parsing values
        THEN monthly index levels are returned newest-first
        """
        result = _parse_mlit_rppi_workbook(self.MOCK_RPPI_XLSX)
        assert result == [
            ScrapingResult(period=date(2026, 6, 1), data_value=140.5, comment=""),
            ScrapingResult(period=date(2026, 5, 1), data_value=139.8, comment=""),
        ]

    @patch("economic_overview.services.scrapers.mlit.requests.get")
    def test_get_data_from_mlit_success(self, mock_get):
        """
        GIVEN the MLIT RPPI page and Excel download
        WHEN getting residential property prices
        THEN parsed index levels are returned
        """
        page_html = (
            "<td>不動産価格指数（住宅）</td>"
            '<td class="aly_tx_center">'
            '<a href="/totikensangyo/content/001473668.xlsx">Excel</a></td>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=page_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_RPPI_XLSX, text=""),
        ]

        result = get_data_from_mlit(
            "residential_property_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 6, 1), data_value=140.5, comment=""
        )
