"""Tests for the Bank of Japan Tankan, Flow of Funds, and CGPI scrapers."""

import io
import zipfile
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, load_json_mock, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import BOJ_FOF_OKU_YEN_TO_BILLION_YEN
from economic_overview.services.scrapers.boj import (
    _BOJ_TIME_SERIES_PAYLOAD_ADAPTER,
    _download_boj_fof_quarterly_csv,
    _download_boj_time_series,
    _parse_boj_fof_series_csv,
    _parse_boj_time_series_payload,
    get_data_from_boj,
)
from economic_overview.services.scrapers.common import ScrapingResult


class TestBojTankanDataIngestion(TestCase):
    """Tests for BoJ Tankan Time-Series API scraping."""

    MOCK_TANKAN_BC_JSON = load_json_mock(
        "economic_overview/tests/mock_web_data/boj/data/"
        "tankan_business_conditions_large_mfg_success.json"
    )
    MOCK_TANKAN_EMP_JSON = load_json_mock(
        "economic_overview/tests/mock_web_data/boj/data/"
        "tankan_employment_large_success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_boj.cache_clear()
        _download_boj_time_series.cache_clear()

    def test_parse_boj_time_series_payload_tankan_quarterly(self):
        """
        GIVEN a BoJ getDataCode JSON fixture for a quarterly Tankan DI
        WHEN parsing with quarterly frequency
        THEN quarter-start dates are returned newest first
        """
        result = _parse_boj_time_series_payload(
            _BOJ_TIME_SERIES_PAYLOAD_ADAPTER.validate_python(self.MOCK_TANKAN_BC_JSON),
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 7, 1), data_value=14.0, comment=""),
            ScrapingResult(period=date(2026, 4, 1), data_value=13.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=12.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_tankan_business_conditions(self, mock_get):
        """
        GIVEN a successful BoJ Time-Series API response for large manufacturing DI
        WHEN getting TK99F1000601GCQ01000 quarterly
        THEN the newest Business Conditions DI is returned first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_TANKAN_BC_JSON
        )

        result = get_data_from_boj(
            "TK99F1000601GCQ01000",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 7, 1), data_value=14.0, comment=""),
            ScrapingResult(period=date(2026, 4, 1), data_value=13.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=12.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_tankan_employment_conditions(self, mock_get):
        """
        GIVEN a successful BoJ Time-Series API response for large employment DI
        WHEN getting TK99F0000608GCQ01000 quarterly
        THEN the newest Employment Conditions DI is returned first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_TANKAN_EMP_JSON
        )

        result = get_data_from_boj(
            "TK99F0000608GCQ01000",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 7, 1), data_value=-29.0, comment=""),
            ScrapingResult(period=date(2026, 4, 1), data_value=-28.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=-27.0, comment=""),
        ]

    def test_get_data_from_boj_unknown_ticker(self):
        """
        GIVEN a ticker not in BOJ_TIME_SERIES_BY_TICKER or FOF helpers
        WHEN getting BoJ data
        THEN an unsupported-ticker ScrapingResult is returned
        """
        result = get_data_from_boj("business_conditions_all_industries")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported BOJ ticker: business_conditions_all_industries",
            )
        ]


class TestBojFlowOfFundsHouseholdLoans(TestCase):
    """Tests for BoJ Flow of Funds household loan liabilities scraping."""

    MOCK_FOF_ZIP = read_file_content(
        "economic_overview/tests/mock_web_data/boj/data/fof2_en.zip"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_boj.cache_clear()
        _download_boj_fof_quarterly_csv.cache_clear()

    def test_parse_boj_fof_series_csv(self):
        """
        GIVEN a BoJ FOF quarterly CSV with household loan liabilities
        WHEN parsing the loans series
        THEN values are converted from 億円 to billion yen, newest first
        """
        with zipfile.ZipFile(io.BytesIO(self.MOCK_FOF_ZIP)) as zip_archive:
            with zip_archive.open("ff_dl_fof_quarterly_en.csv") as csv_file:
                csv_text = csv_file.read().decode("cp932")

        result = _parse_boj_fof_series_csv(csv_text, "FOF_FFAS430L200")
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=3966868 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
            comment="",
        )
        assert result[-1] == ScrapingResult(
            period=date(2023, 7, 1),
            data_value=3660741 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
            comment="",
        )
        assert len(result) == 12

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_fof_hh_loans(self, mock_get):
        """
        GIVEN the BoJ FOF flat-file ZIP
        WHEN getting the household loans stock ticker
        THEN billion-yen loan liabilities are returned newest first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_FOF_ZIP, text=""
        )

        result = get_data_from_boj(
            "fof_hh_loans",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=3966868 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
            comment="",
        )
        assert len(result) == 12

    @patch("economic_overview.services.scrapers.boj.get_data_from_japan_cabinet_office")
    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_hh_debt_ratio(
        self, mock_get, mock_get_japan_cabinet_office
    ):
        """
        GIVEN BoJ FOF loans and ESRI nominal disposable income for matching periods
        WHEN getting the household debt-ratio ticker
        THEN the percent ratio of loans to same-period SAAR DI is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_FOF_ZIP, text=""
        )
        mock_get_japan_cabinet_office.return_value = [
            ScrapingResult(period=date(2026, 4, 1), data_value=330000.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=320000.0, comment=""),
        ]

        latest_loans = 3966868 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN
        prior_loans = 3922286 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN
        result = get_data_from_boj(
            "hh_debt_ratio",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=100.0 * latest_loans / 330000.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=100.0 * prior_loans / 320000.0,
                comment="",
            ),
        ]

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_fof_gg_debt_securities(self, mock_get):
        """
        GIVEN the BoJ FOF flat-file ZIP with general-government L300
        WHEN getting fof_gg_debt_securities
        THEN billion-yen debt-security liability flows are returned newest first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_FOF_ZIP, text=""
        )

        result = get_data_from_boj(
            "fof_gg_debt_securities",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=87802 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
            comment="",
        )
        assert len(result) == 12

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_fof_gg_loans(self, mock_get):
        """
        GIVEN the BoJ FOF flat-file ZIP with general-government L200
        WHEN getting fof_gg_loans
        THEN billion-yen loan liability flows are returned newest first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_FOF_ZIP, text=""
        )

        result = get_data_from_boj(
            "fof_gg_loans",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=-18713 * BOJ_FOF_OKU_YEN_TO_BILLION_YEN,
            comment="",
        )
        assert len(result) == 12

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_fof_gg_other_liabilities(self, mock_get):
        """
        GIVEN BoJ FOF L900 / L700 / L300 / L200 for matching quarters
        WHEN getting fof_gg_other_liabilities
        THEN the residual (L900 − L700) − L300 − L200 is returned newest first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_FOF_ZIP, text=""
        )

        # Scale each FOF input first (as the scraper does), then subtract.
        scale = BOJ_FOF_OKU_YEN_TO_BILLION_YEN
        latest_other = (
            (-36312 * scale) - (-127591 * scale) - (87802 * scale) - (-18713 * scale)
        )
        prior_other = (
            (84016 * scale) - (146239 * scale) - (29685 * scale) - (9381 * scale)
        )
        result = get_data_from_boj(
            "fof_gg_other_liabilities",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[:2] == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=latest_other,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=prior_other,
                comment="",
            ),
        ]


class TestBojTimeSeriesIndexes(TestCase):
    """Tests for BoJ CGPI / SPPI Time-Series API scraping."""

    MOCK_PPI_JSON = load_json_mock(
        "economic_overview/tests/mock_web_data/boj/data/ppi_success.json"
    )
    MOCK_SPPI_JSON = load_json_mock(
        "economic_overview/tests/mock_web_data/boj/data/sppi_success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_boj.cache_clear()
        _download_boj_time_series.cache_clear()

    def test_parse_boj_time_series_payload(self):
        """
        GIVEN a BoJ getDataCode JSON fixture for the all-commodities CGPI
        WHEN parsing the RESULTSET values
        THEN monthly index levels are returned newest first
        """
        result = _parse_boj_time_series_payload(
            _BOJ_TIME_SERIES_PAYLOAD_ADAPTER.validate_python(self.MOCK_PPI_JSON),
            EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2025, 12, 1), data_value=128.2, comment=""),
            ScrapingResult(period=date(2025, 11, 1), data_value=128.1, comment=""),
            ScrapingResult(period=date(2025, 10, 1), data_value=127.7, comment=""),
            ScrapingResult(period=date(2025, 9, 1), data_value=127.1, comment=""),
            ScrapingResult(period=date(2025, 8, 1), data_value=126.5, comment=""),
            ScrapingResult(period=date(2025, 7, 1), data_value=126.7, comment=""),
        ]

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_producer_price_index(self, mock_get):
        """
        GIVEN a successful BoJ Time-Series API response for PRCG20_2200000000
        WHEN getting the manufacturing producer-price ticker monthly
        THEN the newest CGPI all-commodities index is returned first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_PPI_JSON
        )

        result = get_data_from_boj(
            "PRCG20_2200000000",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2025, 12, 1), data_value=128.2, comment=""),
            ScrapingResult(period=date(2025, 11, 1), data_value=128.1, comment=""),
            ScrapingResult(period=date(2025, 10, 1), data_value=127.7, comment=""),
            ScrapingResult(period=date(2025, 9, 1), data_value=127.1, comment=""),
            ScrapingResult(period=date(2025, 8, 1), data_value=126.5, comment=""),
            ScrapingResult(period=date(2025, 7, 1), data_value=126.7, comment=""),
        ]

    @patch("economic_overview.services.scrapers.boj.requests.get")
    def test_get_data_from_boj_services_producer_price_index(self, mock_get):
        """
        GIVEN a successful BoJ Time-Series API response for PRCS20_5200000000
        WHEN getting the services producer-price ticker monthly
        THEN the newest SPPI all-items index is returned first
        """
        mock_get.return_value = MockResponse(
            status_code=200, json_data=self.MOCK_SPPI_JSON
        )

        result = get_data_from_boj(
            "PRCS20_5200000000",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2025, 12, 1), data_value=112.5, comment=""),
            ScrapingResult(period=date(2025, 11, 1), data_value=112.6, comment=""),
            ScrapingResult(period=date(2025, 10, 1), data_value=112.2, comment=""),
            ScrapingResult(period=date(2025, 9, 1), data_value=111.4, comment=""),
            ScrapingResult(period=date(2025, 8, 1), data_value=111.3, comment=""),
            ScrapingResult(period=date(2025, 7, 1), data_value=111.1, comment=""),
        ]
