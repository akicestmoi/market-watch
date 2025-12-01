from datetime import date
from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
from bs4 import BeautifulSoup

from core.tests import MockResponse, read_file_content
from market_overview.services.price_ingestion_services import (
    ScrappingResult,
    _get_bund_yield_from_bundesbank,
    _get_jgb_yield_from_bb,
    _get_mutan_rate_from_boj,
    _get_treasury_yield_curve_from_dep_treasury,
    _get_treasury_yield_from_dep_treasury,
    _scrap_jgb_yield_curve_from_bb,
    _scrap_rate_from_nyfed_xml,
    get_webstat_rates,
    get_yahoo_finance_closing_prices,
    scrap_from_global_rates,
)


def _read_yfinance_mock(file_path: str) -> pd.DataFrame:
    """Read Yahoo Finance mock data from CSV file."""
    mock_df = pd.read_csv(file_path)
    mock_df["Date"] = pd.to_datetime(mock_df["Date"])
    return mock_df


class TestYahooFinanceScraping:
    """Test cases for get_yahoo_finance_closing_prices."""

    MOCK_YAHOO_FINANCE_SUCCESS = _read_yfinance_mock(
        "market_overview/tests/mock_web_data/yfinance/success.csv"
    )
    MOCK_YAHOO_FINANCE_EMPTY = _read_yfinance_mock(
        "market_overview/tests/mock_web_data/yfinance/empty.csv"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_yahoo_finance_closing_prices.cache_clear()

    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    def test_yahoo_finance_success(self, mock_ticker):
        """
        GIVEN a successful yfinance API response
        WHEN getting the closing prices for a specific date
        THEN the closing prices of this date should be returned
        """
        target_date = date(2024, 1, 15)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_SUCCESS
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrappingResult(price=110.0, comment="")

    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    def test_yahoo_finance_empty_dataframe(self, mock_ticker):
        """
        GIVEN a yfinance API with empty DataFrame
        WHEN getting the closing prices for a specific date
        THEN the closing prices should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_EMPTY
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Yahoo Finance: No prices found."
        )

    @patch("market_overview.services.price_ingestion_services.yf.Ticker")
    def test_yahoo_finance_date_not_found(self, mock_ticker):
        """
        GIVEN a yfinance API with a DataFrame but no data for the target date
        WHEN getting the closing prices for a specific date
        THEN the closing prices should be None and commented accordingly
        """
        target_date = date(2024, 2, 20)
        ticker = "^DJI"

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value.reset_index.return_value = (
            self.MOCK_YAHOO_FINANCE_SUCCESS
        )
        mock_ticker.return_value = mock_ticker_instance

        result = get_yahoo_finance_closing_prices(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Yahoo Finance: No prices found."
        )


class TestGlobalRatesScraping:
    """Test cases for scrap_from_global_rates."""

    MOCK_GLOBAL_RATES_EURIBOR_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_success.html"
    )
    MOCK_GLOBAL_RATES_EURIBOR_INVALID_DATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_invalid_date.html"
    )
    MOCK_GLOBAL_RATES_EURIBOR_INVALID_RATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/euribor_invalid_rate.html"
    )
    MOCK_GLOBAL_RATES_CENTRAL_BANK_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/central_bank_success.html"
    )
    MOCK_GLOBAL_RATES_CENTRAL_BANK_EMPTY_RATE = read_file_content(
        "market_overview/tests/mock_web_data/global_rates/central_bank_empty_rate.html"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        scrap_from_global_rates.cache_clear()

    @patch("core.services.requests.get")
    def test_global_rates_euribor_success(self, mock_get):
        """
        GIVEN a successful Global Rates HTML response with EURIBOR data
        WHEN scraping the EURIBOR rate for a specific date
        THEN the EURIBOR rate should be returned successfully
        """
        target_date = date(2025, 11, 25)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_SUCCESS,
        )

        result = scrap_from_global_rates(target_date, ticker)
        assert result == ScrappingResult(price=1.926, comment="")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_not_found(self, mock_get):
        """
        GIVEN a Global Rates HTML response without data for the target date
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_SUCCESS,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Euribor rate not found.")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_invalid_date(self, mock_get):
        """
        GIVEN a Global Rates HTML response with invalid date format
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_INVALID_DATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Euribor rate not found.")

    @patch("core.services.requests.get")
    def test_global_rates_euribor_invalid_rate(self, mock_get):
        """
        GIVEN a Global Rates HTML response with invalid rate format
        WHEN scraping the EURIBOR rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_EURIBOR_INVALID_RATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Could not parse Euribor rate: invalid-rate"
        )

    @patch("core.services.requests.get")
    def test_global_rates_central_bank_success(self, mock_get):
        """
        GIVEN a successful Global Rates HTML response with central bank data
        WHEN scraping the central bank rate
        THEN the central bank rate should be returned successfully
        """
        ticker = "central-banks/9/japanese-boj-overnight-call-rate/"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_CENTRAL_BANK_SUCCESS,
        )

        result = scrap_from_global_rates(None, ticker)

        assert result == ScrappingResult(price=0.5, comment="")

    @patch("core.services.requests.get")
    def test_global_rates_central_bank_empty_rate(self, mock_get):
        """
        GIVEN a Global Rates HTML response with an empty rate cell
        WHEN scraping the central bank rate
        THEN the rate should be None and commented accordingly
        """
        target_date = None
        ticker = "central-banks/ecb/ecb-interest-rate"

        mock_get.return_value = MockResponse(
            status_code=200,
            content=self.MOCK_GLOBAL_RATES_CENTRAL_BANK_EMPTY_RATE,
        )

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Rate cell is empty")

    @patch("market_overview.services.price_ingestion_services.fetch_html")
    def test_global_rates_fetch_failed(self, mock_fetch_html):
        """
        GIVEN a failed HTML fetch (fetch_html returns None)
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        mock_fetch_html.return_value = None

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(
            price=None,
            comment="Failed to fetch HTML from https://www.global-rates.com/en/interest-rates",
        )

    @patch("market_overview.services.price_ingestion_services.fetch_html")
    def test_global_rates_no_table(self, mock_fetch_html):
        """
        GIVEN a Global Rates HTML response with no table
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "euribor/1/euribor-interest-1-month/"

        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        mock_fetch_html.return_value = soup

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Could not find interest rates table on page"
        )

    @patch("market_overview.services.price_ingestion_services.fetch_html")
    def test_global_rates_unsupported_rate_type(self, mock_fetch_html):
        """
        GIVEN a Global Rates HTML response with an unsupported rate type
        WHEN scraping rates from Global Rates
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "unknown/rate-type"

        soup = BeautifulSoup("<html><body><table></table></body></html>", "html.parser")
        mock_fetch_html.return_value = soup

        result = scrap_from_global_rates(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Unsupported rate type: unknown"
        )


class TestNYFedScraping:
    """Test cases for _scrap_rate_from_nyfed_xml."""

    MOCK_NYFED_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/nyfed/success.xml"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _scrap_rate_from_nyfed_xml.cache_clear()

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_nyfed_success(self, mock_get):
        """
        GIVEN a NY Fed XML with a success response
        WHEN scraping the rate for a specific date
        THEN the rate should be scraped successfully
        """
        target_date = date(2025, 11, 24)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_NYFED_SUCCESS, text="Success"
        )

        result = _scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrappingResult(price=3.96, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_nyfed_not_found(self, mock_get):
        """
        GIVEN a NY Fed XML with a success response
        WHEN scraping the rate for a specific date not included in the XML
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_NYFED_SUCCESS, text="Success"
        )

        result = _scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Rate not found.")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_nyfed_http_error(self, mock_get):
        """
        GIVEN a NY Fed XML with a HTTP error response
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "SOFR"

        mock_get.return_value = MockResponse(
            status_code=404, content=self.MOCK_NYFED_SUCCESS, text="Not Found"
        )

        result = _scrap_rate_from_nyfed_xml(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Not Found")


class TestTreasuryDeptScraping:
    """Test cases for _get_treasury_yield_from_dep_treasury."""

    MOCK_TREASURY_DEPT_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/treasury_dept/success.xml"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_treasury_yield_curve_from_dep_treasury.cache_clear()

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_treasury_yield_success(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date
        THEN the yield should be scraped successfully
        """
        target_date = date(2025, 1, 6)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = _get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrappingResult(price=4.62, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_treasury_yield_not_found(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date not included in the XML
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = _get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Yield curve not found.")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_treasury_yield_invalid_ticker(self, mock_get):
        """
        GIVEN a Treasury department XML with a success response
        WHEN scraping the yield for a specific date with an invalid ticker
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "INVALID"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_TREASURY_DEPT_SUCCESS, text="Success"
        )

        result = _get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Ticker not found in mapping."
        )

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_treasury_yield_http_error(self, mock_get):
        """
        GIVEN a Treasury department XML with an HTTP error response
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "UST10Y"

        mock_get.return_value = MockResponse(
            status_code=500,
            content=self.MOCK_TREASURY_DEPT_SUCCESS,
            text="Internal Server Error",
        )

        result = _get_treasury_yield_from_dep_treasury(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Internal Server Error")


class TestWebstatScraping:
    """Test cases for get_webstat_rates."""

    MOCK_WEBSTAT_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/webstat/success.csv"
    )
    MOCK_WEBSTAT_NON_FRENCH_DECIMAL_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/webstat/non_french_decimal.csv"
    )
    MOCK_WEBSTAT_INVALID_VALUE = read_file_content(
        "market_overview/tests/mock_web_data/webstat/invalid_value.csv"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_webstat_rates.cache_clear()

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_webstat_success(self, mock_get):
        """
        GIVEN a successful Webstat CSV response with rate data
        WHEN scraping the rate for a specific date
        THEN the rate should be returned successfully
        """
        target_date = date(2025, 11, 25)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrappingResult(price=2.7, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_webstat_not_found(self, mock_get):
        """
        GIVEN a Webstat CSV response without data for the target date
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Webstat rate not found.")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_webstat_not_french_decimal_format(self, mock_get):
        """
        GIVEN a Webstat CSV response with non-French decimal format (dot)
        WHEN scraping the rate for a specific date
        THEN the rate should be parsed correctly and returned
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_NON_FRENCH_DECIMAL_SUCCESS
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrappingResult(price=3.45, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_webstat_invalid_value(self, mock_get):
        """
        GIVEN a Webstat CSV response with an invalid rate value
        WHEN scraping the rate for a specific date
        THEN a ValueError should be raised
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_WEBSTAT_INVALID_VALUE
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Could not convert rate to float: invalid"
        )

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_webstat_http_error(self, mock_get):
        """
        GIVEN a Webstat HTTP error response
        WHEN scraping the rate for a specific date
        THEN the rate should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "FM/FM.D.FR.EUR.FR2.BB.FRMOYTEC5.HSTA"

        mock_get.return_value = MockResponse(
            status_code=404, content=b"", text="Not Found"
        )

        result = get_webstat_rates(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Not Found")


class TestBundesbankScraping:
    """Test cases for _get_bund_yield_from_bundesbank."""

    MOCK_BUNDESBANK_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/bundesbank/success.xml"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_bund_yield_from_bundesbank.cache_clear()

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_bundesbank_success(self, mock_get):
        """
        GIVEN a successful Bundesbank XML response with yield data
        WHEN scraping the yield for a specific date
        THEN the yield should be returned successfully
        """
        target_date = date(2020, 5, 27)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BUNDESBANK_SUCCESS, text="Success"
        )

        result = _get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrappingResult(price=-0.56, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_bundesbank_not_found(self, mock_get):
        """
        GIVEN a Bundesbank XML response without data for the target date
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BUNDESBANK_SUCCESS, text="Success"
        )

        result = _get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Bunds rate not found.")

    @patch("market_overview.services.price_ingestion_services.requests.get")
    def test_bundesbank_http_error(self, mock_get):
        """
        GIVEN a Bundesbank HTTP error response
        WHEN scraping the yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "D.REN.EUR.A607.000000WT7070.A"

        mock_get.return_value = MockResponse(
            status_code=500, content=b"", text="Internal Server Error"
        )

        result = _get_bund_yield_from_bundesbank(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Internal Server Error")


class TestBOJScraping:
    """Test cases for _get_mutan_rate_from_boj."""

    MOCK_BOJ_CERTIFIED_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/boj/certified_success.xlsx"
    )
    MOCK_BOJ_PREVISION_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/boj/previsional_success.xlsx"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_mutan_rate_from_boj.cache_clear()

    @patch("market_overview.services.price_ingestion_services.requests.get")
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

        result = _get_mutan_rate_from_boj(target_date)

        assert result == ScrappingResult(price=0.478, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
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

        result = _get_mutan_rate_from_boj(target_date)

        assert result == ScrappingResult(price=0.477, comment="")

    @patch("market_overview.services.price_ingestion_services.requests.get")
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

        result = _get_mutan_rate_from_boj(target_date)

        assert result == ScrappingResult(price=None, comment="Not Found")

    @patch("market_overview.services.price_ingestion_services.requests.get")
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

        result = _get_mutan_rate_from_boj(target_date)

        assert result == ScrappingResult(
            price=None, comment="BoJ file has likely changed. Review of code is needed."
        )


class TestBBScraping:
    """Test cases for _get_jgb_yield_from_bb."""

    MOCK_BB_SUCCESS = read_file_content(
        "market_overview/tests/mock_web_data/bb/success.html"
    )

    def teardown_method(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _scrap_jgb_yield_curve_from_bb.cache_clear()

    @patch("core.services.requests.get")
    def test_bb_success(self, mock_get):
        """
        GIVEN a successful BB HTML response with JGB yield data
        WHEN scraping the JGB yield for a specific date
        THEN the JGB yield should be returned successfully
        """
        target_date = date(2025, 11, 26)
        ticker = "JGB10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS
        )

        result = _get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrappingResult(price=1.8, comment="")

    @patch("core.services.requests.get")
    def test_bb_not_found(self, mock_get):
        """
        GIVEN a BB HTML response without data for the target date
        WHEN scraping the JGB yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 20)
        ticker = "JGB10Y"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS, text="Success"
        )

        result = _get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrappingResult(price=None, comment="Yield curve not found.")

    @patch("core.services.requests.get")
    def test_bb_invalid_ticker(self, mock_get):
        """
        GIVEN a BB HTML response with a valid date but an invalid ticker
        WHEN scraping the JGB yield for a specific date
        THEN the yield should be None and commented accordingly
        """
        target_date = date(2024, 1, 15)
        ticker = "INVALID"

        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_BB_SUCCESS
        )

        result = _get_jgb_yield_from_bb(target_date, ticker)

        assert result == ScrappingResult(
            price=None, comment="Ticker not found in mapping."
        )
