"""Tests for FRED series scraping in economic data ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.fred import get_data_from_fred


class TestFredDataIngestion(TestCase):
    """Tests for FRED series/observations scraping helpers."""

    MOCK_FRED_OBSERVATIONS_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/fred/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_fred.cache_clear()

    @override_settings(FRED_API_KEY="")
    def test_get_data_from_fred_missing_api_key(self):
        """
        GIVEN FRED_API_KEY is empty
        WHEN getting FRED data
        THEN a configuration-error ScrapingResult is returned
        """
        result = get_data_from_fred("CPIAUCSL")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="FRED_API_KEY is not configured.",
            )
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_success_no_target_period(self, mock_get):
        """
        GIVEN a successful FRED series/observations response
        WHEN getting data without target period
        THEN values are returned newest-first and missing values are skipped
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_FRED_OBSERVATIONS_SUCCESS,
        )

        result = get_data_from_fred(
            "CPIAUCSL",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 9, 1), data_value=324.1, comment=""),
            ScrapingResult(period=date(2026, 8, 1), data_value=323.0, comment=""),
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_filters_target_period(self, mock_get):
        """
        GIVEN FRED returns several months
        WHEN requesting a specific YYYY-MM period
        THEN only that period is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_FRED_OBSERVATIONS_SUCCESS,
        )

        result = get_data_from_fred(
            "CPIAUCSL",
            "2026-08",
            EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 8, 1), data_value=323.0, comment="")
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_http_error(self, mock_get):
        """
        GIVEN an HTTP error from the FRED API
        WHEN getting data
        THEN a single error ScrapingResult is returned
        """
        mock_get.return_value = MockResponse(status_code=400, content=b"Bad Request")

        result = get_data_from_fred("CPIAUCSL")
        assert result == [
            ScrapingResult(period=None, data_value=None, comment="Bad Request")
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_quarterly_budget_balance_filters_period(self, mock_get):
        """
        GIVEN quarterly FRED government net-lending values
        WHEN requesting a specific quarter
        THEN only the matching period value is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "observations": [
                    {"date": "2026-04-01", "value": "-1234.5"},
                    {"date": "2026-01-01", "value": "-1100.0"},
                    {"date": "2025-10-01", "value": "."},
                ]
            },
        )

        result = get_data_from_fred(
            "AD01RC1Q027SBEA",
            "2026-Q1",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 1, 1), data_value=-1100.0, comment="")
        ]

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_hh_consumption_ratio(self, mock_get):
        """
        GIVEN PCE and DSPI observation responses
        WHEN scraping hh_consumption_ratio
        THEN period values are PCE / DSPI × 100
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-09-01", "value": "22000.0"},
                        {"date": "2026-08-01", "value": "21000.0"},
                    ]
                },
            ),
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-09-01", "value": "25000.0"},
                        {"date": "2026-08-01", "value": "24000.0"},
                    ]
                },
            ),
        ]

        result = get_data_from_fred(
            "hh_consumption_ratio",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 9, 1),
                data_value=100.0 * 22000.0 / 25000.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 8, 1),
                data_value=100.0 * 21000.0 / 24000.0,
                comment="",
            ),
        ]
        assert mock_get.call_count == 2

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_gg_debt_securities_loans(self, mock_get):
        """
        GIVEN Z.1 debt-securities and loans observation responses
        WHEN scraping gg_debt_securities_loans
        THEN period values are the sum of both components
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-04-01", "value": "30000000"},
                        {"date": "2026-01-01", "value": "29000000"},
                    ]
                },
            ),
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-04-01", "value": "4000000"},
                        {"date": "2026-01-01", "value": "3900000"},
                    ]
                },
            ),
        ]

        result = get_data_from_fred(
            "gg_debt_securities_loans",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=34000000.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=32900000.0, comment=""),
        ]
        assert mock_get.call_count == 2

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_gross_capital_share(self, mock_get):
        """
        GIVEN Z.1 NOS, CFC, and GVA observation responses
        WHEN scraping gross_capital_share
        THEN period values are (NOS + CFC) / GVA × 100
        """
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-04-01", "value": "900.0"},
                        {"date": "2026-01-01", "value": "800.0"},
                    ]
                },
            ),
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-04-01", "value": "600.0"},
                        {"date": "2026-01-01", "value": "500.0"},
                    ]
                },
            ),
            MockResponse(
                status_code=200,
                json_data={
                    "observations": [
                        {"date": "2026-04-01", "value": "4000.0"},
                        {"date": "2026-01-01", "value": "3900.0"},
                    ]
                },
            ),
        ]

        result = get_data_from_fred(
            "gross_capital_share",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=100.0 * (900.0 + 600.0) / 4000.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=100.0 * (800.0 + 500.0) / 3900.0,
                comment="",
            ),
        ]
        assert mock_get.call_count == 3

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_gg_other_revenue(self, mock_get):
        """
        GIVEN GRECPT, current tax receipts, and social-contribution responses
        WHEN scraping gg_other_revenue
        THEN values are receipts − taxes − contributions on periods all three share
        """
        observations_by_series_id = {
            "GRECPT": [
                {"date": "2026-04-01", "value": "9275.0"},
                {"date": "2026-01-01", "value": "9105.0"},
            ],
            "W054RC1Q027SBEA": [
                {"date": "2026-04-01", "value": "6607.5"},
                {"date": "2026-01-01", "value": "6459.5"},
            ],
            "W782RC1Q027SBEA": [
                {"date": "2026-07-01", "value": "2109.0"},
                {"date": "2026-04-01", "value": "2093.0"},
                {"date": "2026-01-01", "value": "2075.0"},
            ],
        }
        mock_get.side_effect = lambda url, params, timeout: MockResponse(
            status_code=200,
            json_data={"observations": observations_by_series_id[params["series_id"]]},
        )

        result = get_data_from_fred(
            "gg_other_revenue",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=9275.0 - 6607.5 - 2093.0,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=9105.0 - 6459.5 - 2075.0,
                comment="",
            ),
        ]
        assert mock_get.call_count == 3

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_z1_gg_financing_account(self, mock_get):
        """
        GIVEN Z.1 S.13 total liability and total asset transactions in millions
        WHEN scraping z1_gg_financing_account
        THEN values are liabilities − assets, scaled to billions
        """
        observations_by_series_id = {
            "BOGZ1FA374190005Q": [
                {"date": "2026-04-01", "value": "2084000"},
                {"date": "2026-01-01", "value": "3622000"},
            ],
            "BOGZ1FA374090005Q": [
                {"date": "2026-04-01", "value": "272000"},
                {"date": "2026-01-01", "value": "642000"},
            ],
        }
        mock_get.side_effect = lambda url, params, timeout: MockResponse(
            status_code=200,
            json_data={"observations": observations_by_series_id[params["series_id"]]},
        )

        result = get_data_from_fred(
            "z1_gg_financing_account",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=2084000 * 0.001 - 272000 * 0.001,
                comment="",
            ),
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=3622000 * 0.001 - 642000 * 0.001,
                comment="",
            ),
        ]
        assert mock_get.call_count == 2

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_z1_gg_other_liability_transactions(self, mock_get):
        """
        GIVEN Z.1 S.13 total liability, debt-security, and loan transactions
        WHEN scraping z1_gg_other_liability_transactions for 2026-Q2
        THEN the value is liabilities − securities − loans, scaled to billions
        """
        observations_by_series_id = {
            "BOGZ1FA374190005Q": [
                {"date": "2026-04-01", "value": "2084000"},
                {"date": "2026-01-01", "value": "3622000"},
            ],
            "BOGZ1FA374122005Q": [
                {"date": "2026-04-01", "value": "1705000"},
                {"date": "2026-01-01", "value": "2324000"},
            ],
            "BOGZ1FA374123005Q": [
                {"date": "2026-04-01", "value": "144000"},
                {"date": "2026-01-01", "value": "124000"},
            ],
        }
        mock_get.side_effect = lambda url, params, timeout: MockResponse(
            status_code=200,
            json_data={"observations": observations_by_series_id[params["series_id"]]},
        )

        result = get_data_from_fred(
            "z1_gg_other_liability_transactions",
            "2026-Q2",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=2084000 * 0.001 - 1705000 * 0.001 - 144000 * 0.001,
                comment="",
            )
        ]
        assert mock_get.call_count == 3

    @override_settings(FRED_API_KEY="test-fred-key")
    @patch("economic_overview.services.scrapers.fred.requests.get")
    def test_get_data_from_fred_derived_series_unsupported_frequency(self, mock_get):
        """
        GIVEN a quarterly-only derived general-government ticker
        WHEN requesting it at monthly frequency
        THEN an unsupported-frequency error result is returned without HTTP calls
        """
        result = get_data_from_fred(
            "gg_other_revenue",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for FRED derived series gg_other_revenue: "
                    f"{EconomicPublicationFrequencyChoices.MONTHLY}"
                ),
            )
        ]
        mock_get.assert_not_called()
