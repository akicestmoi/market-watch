"""Tests for TFX Mutan futures scraper."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from django.test import TestCase
from freezegun import freeze_time

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.scrapers.common import StirFutures
from central_banks_overview.services.scrapers.tfx_mutan_futures import (
    _get_mutan_futures_accrual_dates,
    _get_mutan_futures_prices_from_tfx,
    get_mutan_futures_prices,
)
from core.testing import MockResponse, read_file_content


class TestMutanFuturesPricesIngestion(TestCase):
    """Test cases for ingestion functions related to mutan futures."""

    MOCK_MUTAN_CSV_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/success.csv"
    )

    MOCK_MUTAN_REFERENCE_DATES_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/mutan_stir_futures/reference_date_success.html"
    )

    def setUp(self):
        """Set up maturity months and mock HTML/CSV fixtures."""
        self.maturity_months = [
            "25.09",
            "25.12",
            "26.03",
            "26.06",
            "26.09",
            "26.12",
            "27.03",
            "27.06",
            "27.09",
            "27.12",
            "28.03",
            "28.06",
            "28.09",
            "28.12",
            "29.03",
            "29.06",
            "29.09",
            "29.12",
            "30.03",
            "30.06",
        ]

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_mutan_futures_prices_from_tfx.cache_clear()
        _get_mutan_futures_accrual_dates.cache_clear()

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_from_tfx_success(self, mock_get):
        """
        GIVEN TFX CSV response with mutan futures prices
        WHEN getting mutan futures prices from TFX
        THEN prices for the target date are returned as DataFrame
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
        )

        target_date = date(2025, 12, 5)
        result = _get_mutan_futures_prices_from_tfx(target_date)
        expected_data_length = 20
        jp_product_name = "無担保コールオーバーナイト３ヵ月金利先物"
        en_product_name = "Three-month TONA Futures"
        price_day = "2025-12-05"
        prices = [
            99.521,
            99.311,
            99.248,
            99.138,
            99.03,
            98.938,
            98.855,
            98.775,
            98.654,
            98.603,
            98.559,
            98.521,
            98.486,
            98.451,
            98.419,
            98.388,
            98.357,
            98.327,
            98.297,
            98.268,
        ]
        expected = pd.DataFrame(
            {
                "商品名": [jp_product_name] * expected_data_length,
                "Product": [en_product_name] * expected_data_length,
                "限月": self.maturity_months,
                "取引日": [price_day] * expected_data_length,
                "公式終値": prices,
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_from_tfx_no_data_for_date(self, mock_get):
        """
        GIVEN TFX CSV response with no data for target date
        WHEN getting mutan futures prices from TFX
        THEN an empty DataFrame is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_CSV_SUCCESS
        )

        target_date = date(2026, 1, 1)  # Date not in mock data
        result = _get_mutan_futures_prices_from_tfx(target_date)
        # When there's no data, the function returns an empty DataFrame
        # but with the same column structure (5 columns)
        # The "公式終値" column should be float64 (pandas infers it from CSV)
        expected = pd.DataFrame(
            columns=["商品名", "Product", "限月", "取引日", "公式終値"]
        )
        expected["公式終値"] = expected["公式終値"].astype("float64")
        pd.testing.assert_frame_equal(result, expected)

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    def test_get_mutan_futures_prices_from_tfx_request_exception(self, mock_get):
        """
        GIVEN a request exception when fetching from TFX
        WHEN getting mutan futures prices from TFX
        THEN a ValueError is raised
        """
        mock_get.side_effect = Exception("Connection error")

        target_date = date(2025, 12, 5)
        with pytest.raises(ValueError, match="Failed to fetch data from TFX"):
            _get_mutan_futures_prices_from_tfx(target_date)

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    def test_get_mutan_futures_prices_from_tfx_no_header(self, mock_get):
        """
        GIVEN TFX CSV response without expected header
        WHEN getting mutan futures prices from TFX
        THEN a ValueError is raised
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=b"No header here\nJust data"
        )

        target_date = date(2025, 12, 5)
        with pytest.raises(ValueError, match="Could not find data header"):
            _get_mutan_futures_prices_from_tfx(target_date)

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    def test_get_mutan_futures_accrual_dates_success(self, mock_get):
        """
        GIVEN TFX HTML response with trading calendar
        WHEN getting mutan futures reference dates
        THEN reference dates are returned as DataFrame
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_MUTAN_REFERENCE_DATES_SUCCESS
        )

        result = _get_mutan_futures_accrual_dates()
        additional_maturity_months = [
            "23.03",
            "23.06",
            "23.09",
            "23.12",
            "24.03",
            "24.06",
            "24.09",
            "24.12",
            "25.03",
            "25.06",
        ]
        first_accrual_dates = [
            date(2023, 3, 15),
            date(2023, 6, 21),
            date(2023, 9, 20),
            date(2023, 12, 20),
            date(2024, 3, 21),
            date(2024, 6, 19),
            date(2024, 9, 18),
            date(2024, 12, 18),
            date(2025, 3, 19),
            date(2025, 6, 18),
            date(2025, 9, 17),
            date(2025, 12, 17),
            date(2026, 3, 18),
            date(2026, 6, 17),
            date(2026, 9, 16),
            date(2026, 12, 16),
            date(2027, 3, 17),
            date(2027, 6, 16),
            date(2027, 9, 15),
            date(2027, 12, 15),
            date(2028, 3, 15),
            date(2028, 6, 21),
            date(2028, 9, 20),
            date(2028, 12, 20),
            date(2029, 3, 21),
            date(2029, 6, 20),
            date(2029, 9, 19),
            date(2029, 12, 19),
            date(2030, 3, 21),
            date(2030, 6, 19),
        ]
        last_accrual_dates = [
            date(2023, 6, 20),
            date(2023, 9, 19),
            date(2023, 12, 19),
            date(2024, 3, 20),
            date(2024, 6, 18),
            date(2024, 9, 17),
            date(2024, 12, 17),
            date(2025, 3, 18),
            date(2025, 6, 17),
            date(2025, 9, 16),
            date(2025, 12, 16),
            date(2026, 3, 17),
            date(2026, 6, 16),
            date(2026, 9, 15),
            date(2026, 12, 15),
            date(2027, 3, 16),
            date(2027, 6, 15),
            date(2027, 9, 14),
            date(2027, 12, 14),
            date(2028, 3, 14),
            date(2028, 6, 20),
            date(2028, 9, 19),
            date(2028, 12, 19),
            date(2029, 3, 20),
            date(2029, 6, 19),
            date(2029, 9, 18),
            date(2029, 12, 18),
            date(2030, 3, 20),
            date(2030, 6, 18),
            date(2030, 9, 17),
        ]
        expected = pd.DataFrame(
            {
                "限月": additional_maturity_months + self.maturity_months,
                "first_accrual_date": first_accrual_dates,
                "last_accrual_date": last_accrual_dates,
            }
        )
        pd.testing.assert_frame_equal(result, expected)

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    def test_get_mutan_futures_accrual_dates_request_exception(self, mock_get):
        """
        GIVEN a request exception when fetching trading calendar
        WHEN getting mutan futures reference dates
        THEN a ValueError is raised
        """
        mock_get.side_effect = Exception("Connection error")

        with pytest.raises(ValueError, match="Failed to fetch trading calendar"):
            _get_mutan_futures_accrual_dates()

    @patch("central_banks_overview.services.scrapers.tfx_mutan_futures.requests.get")
    def test_get_mutan_futures_accrual_dates_no_table(self, mock_get):
        """
        GIVEN TFX HTML response without expected table
        WHEN getting mutan futures reference dates
        THEN a ValueError is raised
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=b"<html><body>No table here</body></html>"
        )

        with pytest.raises(ValueError, match="Could not find trading calendar table"):
            _get_mutan_futures_accrual_dates()

    @patch(
        "central_banks_overview.services.scrapers.tfx_mutan_futures._get_mutan_futures_prices_from_tfx"
    )
    @patch(
        "central_banks_overview.services.scrapers.tfx_mutan_futures._get_mutan_futures_accrual_dates"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_success(self, mock_ref_dates, mock_prices):
        """
        GIVEN TFX prices and reference dates DataFrames
        WHEN getting mutan futures prices
        THEN combined StirFutures list is returned
        """
        mock_prices.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "取引日": "2025-12-05",
                    "公式終値": 99.500,
                }
            ]
        )
        mock_ref_dates.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "first_accrual_date": date(2025, 12, 17),
                    "last_accrual_date": date(2026, 3, 16),
                }
            ]
        )

        target_date = date(2025, 12, 5)
        result = get_mutan_futures_prices(target_date)
        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.BOJ,
                short_name=StirFuturesNameChoices.MUTAN3M,
                full_name="3 Month Mutan STIR Futures",
                maturity="25.12",
                first_accrual_date=date(2025, 12, 17),
                last_accrual_date=date(2026, 3, 16),
                date=target_date,
                price=99.500,
                source=StirFuturesSourceChoices.TFX,
                comment="",
            )
        ]

    @patch(
        "central_banks_overview.services.scrapers.tfx_mutan_futures._get_mutan_futures_prices_from_tfx"
    )
    @patch(
        "central_banks_overview.services.scrapers.tfx_mutan_futures._get_mutan_futures_accrual_dates"
    )
    @freeze_time("2025-12-05 12:00:00")
    def test_get_mutan_futures_prices_no_matching_maturity(
        self, mock_ref_dates, mock_prices
    ):
        """
        GIVEN TFX prices with no matching reference dates
        WHEN getting mutan futures prices
        THEN prices are returned with None for accrual dates
        """
        mock_prices.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.12",
                    "取引日": "2025-12-05",
                    "公式終値": 99.500,
                }
            ]
        )
        mock_ref_dates.return_value = pd.DataFrame(
            [
                {
                    "限月": "25.06",  # Different maturity
                    "first_accrual_date": date(2025, 6, 18),
                    "last_accrual_date": date(2025, 9, 16),
                }
            ]
        )

        target_date = date(2025, 12, 5)
        result = get_mutan_futures_prices(target_date)
        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.BOJ,
                short_name=StirFuturesNameChoices.MUTAN3M,
                full_name="3 Month Mutan STIR Futures",
                maturity="25.12",
                first_accrual_date=None,
                last_accrual_date=None,
                date=target_date,
                price=99.500,
                source=StirFuturesSourceChoices.TFX,
                comment="",
            )
        ]
