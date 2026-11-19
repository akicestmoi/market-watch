"""Tests for the ISM Manufacturing and Services PMI scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.ism import (
    _parse_forecasts_napm_html,
    _parse_ism_prnewswire_listing_html,
    get_data_from_ism,
)


class TestIsmDataIngestion(TestCase):
    """Tests for ISM PMI scraping."""

    MOCK_PRNEWSWIRE_HTML = read_file_content(
        "economic_overview/tests/mock_web_data/ism/data/prnewswire_ism_page1.html"
    ).decode()
    MOCK_FORECASTS_HTML = read_file_content(
        "economic_overview/tests/mock_web_data/ism/data/forecasts_napm.html"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_ism.cache_clear()

    def test_parse_ism_prnewswire_listing_html(self):
        """
        GIVEN an ISM PR Newswire listing fixture
        WHEN parsing Manufacturing and Services PMI titles
        THEN period and composite values are extracted
        """
        result = _parse_ism_prnewswire_listing_html(self.MOCK_PRNEWSWIRE_HTML)
        assert result == [
            ("manufacturing", date(2026, 10, 1), 55.5),
            ("services", date(2026, 10, 1), 54.5),
            ("manufacturing", date(2026, 9, 1), 54.5),
            ("services", date(2026, 9, 1), 54.9),
        ]

    def test_parse_forecasts_napm_html(self):
        """
        GIVEN a forecasts.org NAPM HTML fixture
        WHEN parsing embedded Manufacturing PMI points
        THEN monthly levels are returned newest-first
        """
        result = _parse_forecasts_napm_html(self.MOCK_FORECASTS_HTML)
        assert result == [
            ScrapingResult(period=date(2014, 8, 1), data_value=59.0, comment=""),
            ScrapingResult(period=date(2014, 7, 1), data_value=57.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.ism.requests.get")
    def test_get_data_from_ism_manufacturing_success(self, mock_get):
        """
        GIVEN PR Newswire and forecasts.org fixtures
        WHEN getting ism_manufacturing_pmi
        THEN recent PR Newswire releases merge over legacy history
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                content=self.MOCK_PRNEWSWIRE_HTML.encode(),
                text=self.MOCK_PRNEWSWIRE_HTML,
            ),
            MockResponse(
                status_code=200,
                content=b"",
                text="",
            ),
            MockResponse(
                status_code=200,
                content=self.MOCK_FORECASTS_HTML.encode(),
                text=self.MOCK_FORECASTS_HTML,
            ),
        ]

        result = get_data_from_ism(
            "ism_manufacturing_pmi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 10, 1), data_value=55.5, comment=""),
            ScrapingResult(period=date(2026, 9, 1), data_value=54.5, comment=""),
            ScrapingResult(period=date(2014, 8, 1), data_value=59.0, comment=""),
            ScrapingResult(period=date(2014, 7, 1), data_value=57.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.ism.requests.get")
    def test_get_data_from_ism_services_success(self, mock_get):
        """
        GIVEN an ISM PR Newswire listing fixture
        WHEN getting ism_services_pmi
        THEN Services PMI levels are returned newest-first
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                content=self.MOCK_PRNEWSWIRE_HTML.encode(),
                text=self.MOCK_PRNEWSWIRE_HTML,
            ),
            MockResponse(
                status_code=200,
                content=b"",
                text="",
            ),
        ]

        result = get_data_from_ism(
            "ism_services_pmi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 10, 1), data_value=54.5, comment=""),
            ScrapingResult(period=date(2026, 9, 1), data_value=54.9, comment=""),
        ]
