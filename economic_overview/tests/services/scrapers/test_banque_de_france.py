"""Tests for the Banque de France Webstat scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.banque_de_france import (
    get_data_from_banque_de_france,
)
from economic_overview.services.scrapers.common import ScrapingResult


class TestBanqueDeFranceDataIngestion(TestCase):
    """Tests for Banque de France manufacturing capacity utilisation scraping."""

    MOCK_CAPACITY_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/banque_de_france/data/"
        "mfg_capacity_utilisation_success.csv"
    ).decode()
    MOCK_NEW_ORDERS_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/banque_de_france/data/"
        "mfg_new_orders_success.csv"
    ).decode()
    MOCK_GG_DEBT_GROSS_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/banque_de_france/data/"
        "gg_debt_securities_gross_success.csv"
    ).decode()
    MOCK_GG_DEBT_NET_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/banque_de_france/data/"
        "gg_debt_securities_net_success.csv"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_banque_de_france.cache_clear()

    @patch("economic_overview.services.scrapers.banque_de_france.requests.get")
    def test_get_data_from_banque_de_france_success(self, mock_get):
        """
        GIVEN a successful Webstat CSV for manufacturing capacity utilisation
        WHEN getting CONJ.M.N01.S.IN.000CZ.TUTSM000.10
        THEN monthly percent levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_CAPACITY_CSV.encode(),
            text=self.MOCK_CAPACITY_CSV,
        )

        result = get_data_from_banque_de_france(
            "CONJ.M.N01.S.IN.000CZ.TUTSM000.10",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=76.77, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=76.41, comment=""),
            ScrapingResult(period=date(2026, 7, 1), data_value=76.61, comment=""),
        ]

    @patch("economic_overview.services.scrapers.banque_de_france.requests.get")
    def test_get_data_from_banque_de_france_new_orders_success(self, mock_get):
        """
        GIVEN a successful Webstat CSV for manufacturing new-orders opinion balance
        WHEN getting CONJ.M.N01.S.IN.000CZ.CRTEM100.10
        THEN monthly SA balances are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_NEW_ORDERS_CSV.encode(),
            text=self.MOCK_NEW_ORDERS_CSV,
        )

        result = get_data_from_banque_de_france(
            "CONJ.M.N01.S.IN.000CZ.CRTEM100.10",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=6.84, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=5.92, comment=""),
            ScrapingResult(period=date(2026, 7, 1), data_value=7.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.banque_de_france.requests.get")
    def test_get_data_from_banque_de_france_gg_debt_securities_net_success(
        self, mock_get
    ):
        """
        GIVEN a successful Webstat SC1 CSV for general-government net issuance
        WHEN getting SC1.Q.FR.1300.F33000.N.4.Z01.E.Z quarterly
        THEN quarterly million-euro levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GG_DEBT_NET_CSV.encode(),
            text=self.MOCK_GG_DEBT_NET_CSV,
        )

        result = get_data_from_banque_de_france(
            "SC1.Q.FR.1300.F33000.N.4.Z01.E.Z",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=49808.757, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=97901.585, comment=""),
            ScrapingResult(period=date(2025, 10, 1), data_value=-48822.888, comment=""),
        ]

    @patch("economic_overview.services.scrapers.banque_de_france.requests.get")
    def test_get_data_from_banque_de_france_gg_debt_securities_redemptions(
        self, mock_get
    ):
        """
        GIVEN successful Webstat SC1 CSVs for gross and net issuance
        WHEN getting gg_debt_securities_redemptions
        THEN principal repayments equal gross minus net by quarter
        """

        def _mock_webstat_response(url, **_kwargs):
            if "SC1.Q.FR.1300.F33000.N.8.Z01.E.Z" in url:
                return MockResponse(
                    status_code=200,
                    content=self.MOCK_GG_DEBT_GROSS_CSV.encode(),
                    text=self.MOCK_GG_DEBT_GROSS_CSV,
                )
            return MockResponse(
                status_code=200,
                content=self.MOCK_GG_DEBT_NET_CSV.encode(),
                text=self.MOCK_GG_DEBT_NET_CSV,
            )

        mock_get.side_effect = _mock_webstat_response

        result = get_data_from_banque_de_france(
            "gg_debt_securities_redemptions",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=301650.335 - 49808.757,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=326261.481 - 97901.585,
                comment="",
            ),
            ScrapingResult(
                period=date(2025, 10, 1),
                data_value=229648.459 - (-48822.888),
                comment="",
            ),
        ]

    @patch("economic_overview.services.scrapers.banque_de_france.requests.get")
    def test_get_data_from_banque_de_france_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown Banque de France ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_banque_de_france("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported Banque de France ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()
