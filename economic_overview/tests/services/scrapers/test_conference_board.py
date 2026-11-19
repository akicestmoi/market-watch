"""Tests for The Conference Board CEO Confidence scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.conference_board import (
    _parse_ceo_confidence_article_html,
    get_data_from_conference_board,
)


class TestConferenceBoardDataIngestion(TestCase):
    """Tests for Conference Board CEO Confidence scraping."""

    MOCK_LIST_HTML = read_file_content(
        "economic_overview/tests/mock_web_data/conference_board/data/prnewswire_list.html"
    ).decode()
    MOCK_ARTICLE_HTML = read_file_content(
        "economic_overview/tests/mock_web_data/conference_board/data/ceo_q4_2026.html"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_conference_board.cache_clear()

    def test_parse_ceo_confidence_article_html(self):
        """
        GIVEN a Conference Board CEO Confidence PR Newswire article
        WHEN parsing the headline value
        THEN the quarter-start period and index are returned
        """
        result = _parse_ceo_confidence_article_html(self.MOCK_ARTICLE_HTML)
        assert result == ScrapingResult(
            period=date(2026, 10, 1), data_value=46.0, comment=""
        )

    @patch("economic_overview.services.scrapers.conference_board.requests.get")
    def test_get_data_from_conference_board_success(self, mock_get):
        """
        GIVEN Conference Board listing and article fixtures
        WHEN getting ceo_confidence
        THEN quarterly levels are returned
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                content=self.MOCK_LIST_HTML.encode(),
                text=self.MOCK_LIST_HTML,
            ),
            MockResponse(
                status_code=200,
                content=self.MOCK_ARTICLE_HTML.encode(),
                text=self.MOCK_ARTICLE_HTML,
            ),
            MockResponse(
                status_code=200,
                content=b"<html></html>",
                text="<html></html>",
            ),
        ]

        result = get_data_from_conference_board(
            "ceo_confidence",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 10, 1), data_value=46.0, comment="")
        ]
