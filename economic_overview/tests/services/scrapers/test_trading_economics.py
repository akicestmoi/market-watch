"""Tests for the Trading Economics S&P Global PMI scraper."""

import base64
import json
import zlib
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import TRADING_ECONOMICS_CHART_OBFUSCATION_KEY
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.trading_economics import (
    _decrypt_trading_economics_chart_payload,
    _parse_trading_economics_chart_points,
    _parse_trading_economics_page_meta,
    get_data_from_trading_economics,
)


def _build_encrypted_chart_payload(points: list[list[float | int | str | None]]) -> str:
    """Build a TE charts-api encrypted response body for the given points."""
    plaintext = json.dumps(
        [
            {
                "series": [{"serie": {"data": points}}],
                "span": "max",
                "agr": "1month",
                "frequency": {"min": "Monthly", "max": "Monthly"},
            }
        ]
    ).encode()
    gzipped = zlib.compress(plaintext, wbits=31)
    obfuscation_key = TRADING_ECONOMICS_CHART_OBFUSCATION_KEY.encode()
    obfuscated = bytearray(gzipped)
    for byte_index in range(len(obfuscated)):
        obfuscated[byte_index] ^= obfuscation_key[byte_index % len(obfuscation_key)]
    return json.dumps(base64.b64encode(bytes(obfuscated)).decode())


class TestTradingEconomicsDataIngestion(TestCase):
    """Tests for Trading Economics PMI scraping."""

    MOCK_PAGE_HTML = """
    <script>var TESymbol = 'FRANCECOMPMI';</script>
    <script>TEChartsKey = '20260324:testkey'; TEChartsToken = 'tok123';</script>
    <script>TEChartsPath = '/france/composite-pmi';</script>
    """

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_trading_economics.cache_clear()

    def test_parse_trading_economics_page_meta(self):
        """
        GIVEN a Trading Economics indicator page fixture
        WHEN parsing chart symbol and auth headers
        THEN symbol, key, token, and path are extracted
        """
        page_meta = _parse_trading_economics_page_meta(self.MOCK_PAGE_HTML)
        assert page_meta is not None
        assert page_meta.symbol == "FRANCECOMPMI"
        assert page_meta.api_key == "20260324:testkey"
        assert page_meta.api_token == "tok123"
        assert page_meta.api_path == "/france/composite-pmi"

    def test_decrypt_and_parse_trading_economics_chart_points(self):
        """
        GIVEN an encrypted TE charts-api payload with two monthly points
        WHEN decrypting and parsing
        THEN newest-first ScrapingResult levels are returned
        """
        encrypted_payload = _build_encrypted_chart_payload(
            [
                [51.1, 1788220800, None, "2026-09-01"],
                [46.6, 1790812800, None, "2026-10-01"],
            ]
        )
        chart_payload = _decrypt_trading_economics_chart_payload(encrypted_payload)
        result = _parse_trading_economics_chart_points(chart_payload)
        assert result == [
            ScrapingResult(period=date(2026, 10, 1), data_value=46.6, comment=""),
            ScrapingResult(period=date(2026, 9, 1), data_value=51.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.trading_economics.requests.get")
    def test_get_data_from_trading_economics_success(self, mock_get):
        """
        GIVEN a TE page and encrypted chart payload
        WHEN getting fr_sp_composite_pmi
        THEN monthly PMI levels are returned newest-first
        """
        encrypted_payload = _build_encrypted_chart_payload(
            [
                [51.1, 1788220800, None, "2026-09-01"],
                [46.6, 1790812800, None, "2026-10-01"],
            ]
        )
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                content=self.MOCK_PAGE_HTML.encode(),
                text=self.MOCK_PAGE_HTML,
            ),
            MockResponse(
                status_code=200,
                content=encrypted_payload.encode(),
                text=encrypted_payload,
            ),
        ]

        result = get_data_from_trading_economics(
            "fr_sp_composite_pmi",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 10, 1), data_value=46.6, comment=""),
            ScrapingResult(period=date(2026, 9, 1), data_value=51.1, comment=""),
        ]

    def test_get_data_from_trading_economics_unsupported_ticker(self):
        """
        GIVEN an unknown Trading Economics ticker
        WHEN getting data
        THEN a miss comment is returned
        """
        result = get_data_from_trading_economics(
            "not_a_ticker",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported Trading Economics ticker: not_a_ticker",
            )
        ]
