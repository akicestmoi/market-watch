"""Tests for the NAHB Housing Market Index scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.nahb import (
    _parse_nahb_hmi_history_workbook,
    get_data_from_nahb,
)


class TestNahbDataIngestion(TestCase):
    """Tests for NAHB HMI workbook scraping."""

    MOCK_HMI_PAGE_HTML = read_file_content(
        "economic_overview/tests/mock_web_data/nahb/data/hmi_index.html"
    ).decode()
    MOCK_HMI_XLS = read_file_content(
        "economic_overview/tests/mock_web_data/nahb/data/national_hmi_history.xls"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_nahb.cache_clear()

    def test_parse_nahb_hmi_history_workbook(self):
        """
        GIVEN a NAHB National HMI history workbook fixture
        WHEN parsing the year-by-month grid
        THEN October 2026 is the newest monthly level
        """
        result = _parse_nahb_hmi_history_workbook(self.MOCK_HMI_XLS)
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=29.0, comment=""
        )
        assert result[-1] == ScrapingResult(
            period=date(1985, 1, 1), data_value=50.0, comment=""
        )

    @patch("economic_overview.services.scrapers.nahb.requests.get")
    def test_get_data_from_nahb_success(self, mock_get):
        """
        GIVEN a successful NAHB HMI page and workbook response
        WHEN getting nahb_hmi
        THEN monthly HMI levels are returned newest-first
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                content=self.MOCK_HMI_PAGE_HTML.encode(),
                text=self.MOCK_HMI_PAGE_HTML,
            ),
            MockResponse(
                status_code=200,
                content=self.MOCK_HMI_XLS,
                text="",
            ),
        ]

        result = get_data_from_nahb(
            "nahb_hmi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=29.0, comment=""
        )
