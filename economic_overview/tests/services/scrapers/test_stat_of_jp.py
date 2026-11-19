"""Tests for the e-Stat Statistics Dashboard scraper."""

import io
from datetime import date
from unittest.mock import patch

import openpyxl
from django.test import TestCase

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import FIES_GINI_TICKER, FIES_PALMA_TICKER
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    calculate_equal_group_gini,
    calculate_palma_from_decile_means,
)
from economic_overview.services.scrapers.stat_of_jp import (
    _extract_fies_decile_means_from_xlsx,
    get_data_from_stat_of_jp,
)


class TestStatOfJpDataIngestion(TestCase):
    """Tests for e-Stat Statistics Dashboard scraping."""

    MOCK_STAT_OF_JP_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/stat_of_jp/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_stat_of_jp.cache_clear()

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_success(self, mock_get):
        """
        GIVEN a successful e-Stat Dashboard CPI response
        WHEN getting data without target period
        THEN monthly index levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_STAT_OF_JP_SUCCESS,
        )

        result = get_data_from_stat_of_jp(
            "0703010601010090000",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1), data_value=102.2, comment=""
        )
        assert len(result) == 3

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_unknown_ticker(self, mock_get):
        """
        GIVEN a configured series ID not in STAT_OF_JP_SERIES_BY_TICKER
        WHEN getting data
        THEN an unsupported-ticker ScrapingResult is returned without calling the API
        """
        result = get_data_from_stat_of_jp("0000000000000000000")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported STAT_OF_JP ticker: 0000000000000000000",
            )
        ]
        mock_get.assert_not_called()

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_applies_value_scale(self, mock_get):
        """
        GIVEN employed-persons levels published in 10 thousand persons
        WHEN scraping the Employment Level ticker
        THEN values are scaled to thousands
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "GET_STATS": {
                    "STATISTICAL_DATA": {
                        "DATA_INF": {
                            "DATA_OBJ": [
                                {
                                    "VALUE": {
                                        "@time": "20260900",
                                        "$": "6868",
                                    }
                                }
                            ]
                        }
                    }
                }
            },
        )

        result = get_data_from_stat_of_jp(
            "0301010000010010010",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=68680.0, comment="")
        ]

    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_stat_of_jp_core_cpi_excl_food_and_energy(self, mock_get):
        """
        GIVEN e-Stat core-core CPI index levels
        WHEN scraping 0703010601010090040
        THEN monthly index levels are returned newest-first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "GET_STATS": {
                    "STATISTICAL_DATA": {
                        "DATA_INF": {
                            "DATA_OBJ": [
                                {
                                    "VALUE": {
                                        "@time": "20260900",
                                        "$": "102.8",
                                    }
                                },
                                {
                                    "VALUE": {
                                        "@time": "20260800",
                                        "$": "102.5",
                                    }
                                },
                            ]
                        }
                    }
                }
            },
        )

        result = get_data_from_stat_of_jp(
            "0703010601010090040",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=102.8, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=102.5, comment=""),
        ]

    def test_calculate_equal_group_gini_and_palma_from_decile_means(self):
        """
        GIVEN FIES-style equal-decile yearly-income means
        WHEN computing Gini and Palma
        THEN the discrete equal-group formulas match the expected values
        """
        decile_means = [
            124.0,
            204.0,
            270.0,
            333.0,
            400.0,
            486.0,
            588.0,
            716.0,
            890.0,
            1384.0,
        ]
        assert calculate_equal_group_gini(decile_means) == 0.35631139944392953
        assert calculate_palma_from_decile_means(decile_means) == 1.4865735767991408

    def test_extract_fies_decile_means_from_xlsx(self):
        """
        GIVEN a minimal FIES-like Table 3 workbook with yearly-income deciles
        WHEN extracting yearly-income decile means
        THEN the ten equal-decile means are returned in order
        """
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        assert worksheet is not None
        worksheet.title = "総"
        worksheet.cell(row=20, column=8, value="年間収入(万円)")
        decile_means = [
            124.0,
            204.0,
            270.0,
            333.0,
            400.0,
            486.0,
            588.0,
            716.0,
            890.0,
            1384.0,
        ]
        for column_offset, decile_mean in enumerate(decile_means):
            worksheet.cell(row=20, column=23 + column_offset, value=decile_mean)
        workbook_buffer = io.BytesIO()
        workbook.save(workbook_buffer)
        assert _extract_fies_decile_means_from_xlsx(workbook_buffer.getvalue()) == (
            decile_means
        )

    @patch(
        "economic_overview.services.scrapers.stat_of_jp._fetch_fies_decile_means_for_year"
    )
    def test_get_data_from_stat_of_jp_fies_gini_and_palma(
        self, mock_fetch_fies_decile_means_for_year
    ):
        """
        GIVEN one year of FIES decile means
        WHEN scraping fies_gini and fies_palma
        THEN derived annual points are returned on the 0–100 / raw Palma scales
        """
        decile_means = [
            124.0,
            204.0,
            270.0,
            333.0,
            400.0,
            486.0,
            588.0,
            716.0,
            890.0,
            1384.0,
        ]

        def _means_for_year(year: int) -> list[float] | None:
            if year == 2025:
                return decile_means
            return None

        mock_fetch_fies_decile_means_for_year.side_effect = _means_for_year
        gini_series = get_data_from_stat_of_jp(
            FIES_GINI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        palma_series = get_data_from_stat_of_jp(
            FIES_PALMA_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert gini_series == [
            ScrapingResult(
                period=date(2025, 1, 1),
                data_value=35.631139944392956,
                comment="",
            )
        ]
        assert palma_series == [
            ScrapingResult(
                period=date(2025, 1, 1),
                data_value=1.4865735767991408,
                comment="",
            )
        ]
