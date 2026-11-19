"""Tests for the MOF balance-of-payments and corporate-survey scrapers."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
)
from economic_overview.services.scrapers.mof import (
    get_data_from_mof,
    get_industry_profitability_from_mof,
)
from economic_overview.services.scrapers.stat_of_jp import (
    _fetch_estat_stats_data_cached,
)


class TestMofDataIngestion(TestCase):
    """Tests for MOF 6s-a-1 seasonally adjusted BoP scraping."""

    MOCK_MOF_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/mof/data/success.csv"
    ).decode()

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_mof.cache_clear()

    @patch("economic_overview.services.scrapers.mof.requests.get")
    def test_get_data_from_mof_current_account_success(self, mock_get):
        """
        GIVEN a successful MOF 6s-a-1 CSV response
        WHEN getting the current-account series
        THEN quarterly billion-yen values are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_MOF_CSV.encode(),
            text=self.MOCK_MOF_CSV,
        )

        result = get_data_from_mof(
            "mof_bop_ca",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=8964.6, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=9878.0, comment=""),
            ScrapingResult(period=date(1996, 4, 1), data_value=1627.6, comment=""),
            ScrapingResult(period=date(1996, 1, 1), data_value=2064.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.mof.requests.get")
    def test_get_data_from_mof_goods_services_success(self, mock_get):
        """
        GIVEN a successful MOF 6s-a-1 CSV response
        WHEN getting the goods-and-services balance
        THEN quarterly billion-yen values are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_MOF_CSV.encode(),
            text=self.MOCK_MOF_CSV,
        )

        result = get_data_from_mof(
            "mof_bop_gs",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=62.9, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=-237.3, comment=""),
            ScrapingResult(period=date(1996, 4, 1), data_value=232.8, comment=""),
            ScrapingResult(period=date(1996, 1, 1), data_value=976.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.mof.requests.get")
    def test_get_data_from_mof_unsupported_ticker(self, mock_get):
        """
        GIVEN an unknown MOF ticker
        WHEN getting data
        THEN an unsupported-ticker error result is returned
        """
        result = get_data_from_mof("not_a_series")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported MOF ticker: not_a_series",
            )
        ]
        mock_get.assert_not_called()


class TestGetIndustryProfitabilityFromMof(TestCase):
    """Tests for get_industry_profitability_from_mof."""

    def tearDown(self):
        """Clear scrape caches after each test."""
        get_industry_profitability_from_mof.cache_clear()
        _fetch_estat_stats_data_cached.cache_clear()

    @override_settings(ESTAT_APP_ID="test-estat-app-id")
    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_industry_profitability_from_mof(self, mock_get):
        """
        GIVEN e-Stat payloads for MOF sales and operating profit
        WHEN scraping MOF corporate industry profitability
        THEN aggregate and discontinued industries are skipped and amounts are kept
        """

        def _build_payload(item_code: str, food_amount: str) -> dict:
            return {
                "GET_STATS_DATA": {
                    "RESULT": {"STATUS": 0, "ERROR_MSG": "正常に終了しました。"},
                    "STATISTICAL_DATA": {
                        "CLASS_INF": {
                            "CLASS_OBJ": [
                                {
                                    "@id": "cat02",
                                    "@name": "業種",
                                    "CLASS": [
                                        {
                                            "@code": "104",
                                            "@name": "全産業（除く金融保険業）",
                                        },
                                        {"@code": "109", "@name": "食料品製造業"},
                                        {
                                            "@code": "163",
                                            "@name": "繊維工業(H20年度まで)",
                                        },
                                    ],
                                }
                            ]
                        },
                        "DATA_INF": {
                            "VALUE": [
                                {
                                    "@cat01": item_code,
                                    "@cat02": "104",
                                    "@cat03": "26",
                                    "@time": "20240",
                                    "$": "99999999",
                                },
                                {
                                    "@cat01": item_code,
                                    "@cat02": "109",
                                    "@cat03": "26",
                                    "@time": "20240",
                                    "$": food_amount,
                                },
                                {
                                    "@cat01": item_code,
                                    "@cat02": "163",
                                    "@cat03": "26",
                                    "@time": "20240",
                                    "$": "100",
                                },
                            ]
                        },
                    },
                }
            }

        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.side_effect = [
            _build_payload("045", "19167000"),
            _build_payload("048", "1916700"),
        ]
        scraped_industry_profitabilities = get_industry_profitability_from_mof()
        assert scraped_industry_profitabilities == [
            ScrapedIndustryProfitability(
                industry_code="109",
                industry_label="食料品製造業",
                period=date(2024, 1, 1),
                turnover=19167000.0,
                operating_profit=1916700.0,
                gva=None,
            )
        ]
