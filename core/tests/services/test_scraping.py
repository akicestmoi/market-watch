"""Tests for shared scraping helpers in 'core.services.scraping'."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup
from django.test import TestCase

from core.services.scraping import fetch_html, parse_datetime


class TestFetchHtml(TestCase):
    """Test cases for fetch_html function."""

    @patch("core.services.scraping.requests.get")
    def test_fetch_html_success(self, mock_get):
        """
        GIVEN a valid URL
        WHEN fetch_html is called
        THEN a BeautifulSoup object should be returned
        """
        url = "https://example.com"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_get.return_value = mock_response

        result = fetch_html(url)

        assert isinstance(result, BeautifulSoup)
        body = result.find("body")
        assert body is not None
        assert body.text == "Test"
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.scraping.requests.get")
    def test_fetch_html_http_error(self, mock_get):
        """
        GIVEN a URL that returns an HTTP error
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.scraping.requests.get")
    def test_fetch_html_request_exception(self, mock_get):
        """
        GIVEN a URL that raises a RequestException
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_get.side_effect = requests.RequestException("Connection error")

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)

    @patch("core.services.scraping.requests.get")
    def test_fetch_html_timeout(self, mock_get):
        """
        GIVEN a URL that times out
        WHEN fetch_html is called
        THEN None should be returned
        """
        url = "https://example.com"
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = fetch_html(url)

        assert result is None
        mock_get.assert_called_once_with(url, timeout=10)


class TestParseDatetime(TestCase):
    """Test cases for parse_datetime."""

    def test_parse_datetime_iso(self):
        """
        GIVEN an ISO datetime string with offset
        WHEN parse_datetime is called
        THEN an aware datetime normalized to UTC is returned
        """
        parsed = parse_datetime("2026-10-23T22:05:55+02:00")
        assert parsed is not None
        assert parsed == datetime(2026, 10, 23, 20, 5, 55, tzinfo=timezone.utc)

    def test_parse_datetime_naive_assumes_utc(self):
        """
        GIVEN a naive ISO datetime string
        WHEN parse_datetime is called
        THEN timezone is set to UTC
        """
        parsed = parse_datetime("2026-10-23T22:05:55")
        assert parsed is not None
        assert parsed.tzinfo == timezone.utc

    def test_parse_datetime_naive_with_source_timezone(self):
        """
        GIVEN a naive datetime and America/New_York as the source zone
        WHEN parse_datetime is called
        THEN the local announcement time is localized then stored as UTC
        """
        parsed = parse_datetime(
            "2025-01-29T14:00:00",
            naive_timezone="America/New_York",
        )
        assert parsed == datetime(2025, 1, 29, 19, 0, 0, tzinfo=timezone.utc)

    def test_parse_datetime_empty_returns_none(self):
        """
        GIVEN an empty value
        WHEN parse_datetime is called
        THEN None is returned
        """
        assert parse_datetime(None) is None
        assert parse_datetime("") is None
