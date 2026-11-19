"""Tests for the MLIT residential property price index scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
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

    def test_parse_mlit_rppi_workbook_detached_house(self):
        """
        GIVEN an MLIT nationwide SA RPPI workbook fixture
        WHEN parsing the Detached House index column
        THEN monthly index levels are returned newest-first
        """
        result = _parse_mlit_rppi_workbook(self.MOCK_RPPI_XLSX, index_column=8)
        assert result == [
            ScrapingResult(
                period=date(2025, 12, 1), data_value=121.8841005707, comment=""
            ),
            ScrapingResult(
                period=date(2025, 11, 1), data_value=120.4281143314, comment=""
            ),
        ]

    def test_parse_mlit_rppi_workbook_condominiums(self):
        """
        GIVEN an MLIT nationwide SA RPPI workbook fixture
        WHEN parsing the Condominiums index column
        THEN monthly index levels are returned newest-first
        """
        result = _parse_mlit_rppi_workbook(self.MOCK_RPPI_XLSX, index_column=11)
        assert result == [
            ScrapingResult(
                period=date(2025, 12, 1), data_value=225.1495454622, comment=""
            ),
            ScrapingResult(
                period=date(2025, 11, 1), data_value=222.9250185054, comment=""
            ),
        ]

    @patch("economic_overview.services.scrapers.mlit.requests.get")
    def test_get_data_from_mlit_detached_house_success(self, mock_get):
        """
        GIVEN the MLIT RPPI page and Excel download
        WHEN getting Detached House nationwide SA prices
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
            "detached_house_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 12, 1), data_value=121.8841005707, comment=""
        )

    @patch("economic_overview.services.scrapers.mlit.requests.get")
    def test_get_data_from_mlit_condominiums_success(self, mock_get):
        """
        GIVEN the MLIT RPPI page and Excel download
        WHEN getting Condominiums nationwide SA prices
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
            "condominiums_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 12, 1), data_value=225.1495454622, comment=""
        )
