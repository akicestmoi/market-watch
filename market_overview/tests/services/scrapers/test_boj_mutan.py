"""Tests for BoJ Mutan rate scraper."""

from datetime import date
from io import BytesIO
from unittest.mock import patch

import pandas as pd
from django.test import TestCase

from core.testing import MockResponse, read_file_content
from market_overview.services.scrapers.boj_mutan import get_mutan_rate_from_boj
from market_overview.services.scrapers.common import ScrapingResult


class TestBOJScraping(TestCase):
    """Test cases for get_mutan_rate_from_boj."""

    MOCK_BOJ_CERTIFIED_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/boj/certified_success.xlsx"
    )
    MOCK_BOJ_PREVISION_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/boj/previsional_success.xlsx"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_mutan_rate_from_boj.cache_clear()

    @patch("market_overview.services.scrapers.boj_mutan.requests.get")
    def test_boj_certified_success(self, mock_get):
        """
        GIVEN a successful BOJ Excel file response (certified) with Mutan rate data
        WHEN scraping the Mutan rate for a specific date
        THEN the Mutan rate should be returned successfully
        """
        target_date = date(2024, 1, 15)

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BOJ_CERTIFIED_SUCCESS, text="Success"
        )

        result = get_mutan_rate_from_boj(target_date)

        assert result == ScrapingResult(price=0.478, comment="")

    @patch("market_overview.services.scrapers.boj_mutan.requests.get")
    def test_boj_prevision_fallback(self, mock_get):
        """
        GIVEN a BOJ certified file request that fails and a successful prevision file
        WHEN scraping the Mutan rate for a specific date
        THEN the Mutan rate should be returned from the prevision file
        """
        target_date = date(2024, 1, 15)

        mock_get.side_effect = [
            MockResponse(status_code=404, content=b"", text="Not Found"),
            MockResponse(
                status_code=200, content=self.MOCK_BOJ_PREVISION_SUCCESS, text="Success"
            ),
        ]

        result = get_mutan_rate_from_boj(target_date)

        assert result == ScrapingResult(price=0.477, comment="")

    @patch("market_overview.services.scrapers.boj_mutan.requests.get")
    def test_boj_both_fail(self, mock_get):
        """
        GIVEN BOJ certified and prevision file requests that both fail
        WHEN scraping the Mutan rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)

        mock_get.side_effect = [
            MockResponse(status_code=404, content=b"", text="Not Found"),
            MockResponse(status_code=404, content=b"", text="Not Found"),
        ]

        result = get_mutan_rate_from_boj(target_date)

        assert result == ScrapingResult(price=None, comment="Not Found")

    @patch("market_overview.services.scrapers.boj_mutan.requests.get")
    def test_boj_multiple_averages(self, mock_get):
        """
        GIVEN a BOJ Excel file with multiple 'Average' cells
        WHEN scraping the Mutan rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)

        df = pd.DataFrame(
            {
                "A": ["", "Average", "Average", ""],
                "B": ["", "0.25", "0.30", ""],
            }
        )
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        excel_buffer.seek(0)

        mock_get.return_value = MockResponse(
            status_code=200, content=excel_buffer.read(), text="Success"
        )

        result = get_mutan_rate_from_boj(target_date)

        assert result == ScrapingResult(
            price=None, comment="BoJ file has likely changed. Review of code is needed."
        )
