"""Tests for Eurostat HICP scraping in economic data ingestion."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from pydantic import TypeAdapter

from core.testing import MockResponse, load_json_mock
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    EUROSTAT_CORPORATE_GFCF_TICKER,
    EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER,
    EUROSTAT_GG_FINANCING_ACCOUNT_TICKER,
    EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER,
    EUROSTAT_GG_TAX_REVENUE_TICKER,
    EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER,
    EUROSTAT_HH_CONSUMPTION_RATIO_TICKER,
    EUROSTAT_HH_SAVING_RATIO_TICKER,
    EUROSTAT_NET_OPERATING_SURPLUS_TICKER,
    EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS,
    EUROSTAT_PALMA_TICKER,
    EUROSTAT_PALMA_TOP_DECILE_TICKER,
    EUROSTAT_REAL_HH_GDHI_TICKER,
    EurostatTickerParams,
)
from economic_overview.services.scrapers.common import (
    ScrapingResult,
    deflate_scraping_results_by_period,
    subtract_scraping_results_by_period,
    sum_scraping_results_by_period,
)
from economic_overview.services.scrapers.eurostat import (
    _build_eurostat_request_params,
    _EurostatJsonStatPayload,
    _parse_eurostat_jsonstat_values,
    _parse_eurostat_period_label,
    get_data_from_eurostat,
)

_EUROSTAT_JSONSTAT_ADAPTER = TypeAdapter(_EurostatJsonStatPayload)


class TestEurostatHicpIngestion(TestCase):
    """Tests for Eurostat 'prc_hicp_minr' scraping helpers."""

    MOCK_EUROSTAT_HICP_SUCCESS = load_json_mock(
        "economic_overview/tests/mock_web_data/eurostat/data/success.json"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_eurostat.cache_clear()

    def test_parse_eurostat_jsonstat_values(self):
        """
        GIVEN a Eurostat JSON-stat HICP fixture
        WHEN parsing values
        THEN periods and index levels are returned newest-first
        """
        payload = _EUROSTAT_JSONSTAT_ADAPTER.validate_python(
            self.MOCK_EUROSTAT_HICP_SUCCESS
        )
        result = _parse_eurostat_jsonstat_values(payload)
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1),
            data_value=104.31,
            comment="",
        )
        assert len(result) == 141
        assert result[-1] == ScrapingResult(
            period=date(2015, 1, 1),
            data_value=76.3,
            comment="",
        )

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_success_no_target_period(self, mock_get):
        """
        GIVEN a successful Eurostat JSON-stat response
        WHEN getting data without target period
        THEN all values are returned with the latest first
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_EUROSTAT_HICP_SUCCESS,
        )

        result = get_data_from_eurostat(
            "prc_hicp_minr",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
            location="EU",
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 9, 1),
            data_value=104.31,
            comment="",
        )
        assert len(result) == 141

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_filters_target_period(self, mock_get):
        """
        GIVEN Eurostat returns several months
        WHEN requesting a specific YYYY-MM period
        THEN only that period is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data=self.MOCK_EUROSTAT_HICP_SUCCESS,
        )

        result = get_data_from_eurostat(
            "prc_hicp_minr",
            "2024-09",
            EconomicPublicationFrequencyChoices.MONTHLY,
            location="EU",
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 9, 1),
                data_value=98.33,
                comment="",
            )
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_http_error(self, mock_get):
        """
        GIVEN an HTTP error from the Eurostat Statistics API
        WHEN getting data
        THEN a single error ScrapingResult is returned
        """
        mock_get.return_value = MockResponse(
            status_code=404,
            content=b"Not Found",
        )

        result = get_data_from_eurostat("prc_hicp_minr", location="EU")
        assert result == [
            ScrapingResult(period=None, data_value=None, comment="Not Found")
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_unknown_ticker(self, mock_get):
        """
        GIVEN a configured series ID with no Eurostat template
        WHEN getting data
        THEN an unsupported-ticker ScrapingResult is returned without calling the API
        """
        result = get_data_from_eurostat("prc_hicp_midx", location="EU")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Unsupported Eurostat ticker: prc_hicp_midx",
            )
        ]
        mock_get.assert_not_called()

    def test_parse_eurostat_period_label_annual(self):
        """
        GIVEN an annual Eurostat time label
        WHEN parsing the period
        THEN January 1 of that year is returned
        """
        assert _parse_eurostat_period_label("2024") == date(2024, 1, 1)
        assert _parse_eurostat_period_label("2024-Q2") == date(2024, 4, 1)
        assert _parse_eurostat_period_label("2024-09") == date(2024, 9, 1)

    def test_eurostat_location_supplies_geo(self):
        """
        GIVEN configured Eurostat series IDs and indicator locations
        WHEN resolving request params
        THEN geo comes from location (EU → EA21)
        """
        for location in ("DE", "ES", "IT"):
            assert _build_eurostat_request_params(
                "gov_10q_ggnfa_balance", location
            ) == EurostatTickerParams(
                dataset="gov_10q_ggnfa",
                params={
                    "freq": "Q",
                    "sinceTimePeriod": "2010-Q1",
                    "unit": "MIO_EUR",
                    "na_item": "B9",
                    "sector": "S13",
                    "s_adj": "NSA",
                    "geo": location,
                },
            )
        assert _build_eurostat_request_params(
            "prc_hicp_minr", "EU"
        ) == EurostatTickerParams(
            dataset="prc_hicp_minr",
            params={
                "freq": "M",
                "sinceTimePeriod": "2015-01",
                "unit": "I25",
                "coicop18": "TOTAL",
                "geo": "EA21",
            },
        )
        assert _build_eurostat_request_params(
            "prc_hicp_minr", "DE"
        ) == EurostatTickerParams(
            dataset="prc_hicp_minr",
            params={
                "freq": "M",
                "sinceTimePeriod": "2015-01",
                "unit": "I25",
                "coicop18": "TOTAL",
                "geo": "DE",
            },
        )
        assert _build_eurostat_request_params("unknown_series", "DE") is None

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_quarterly_budget_balance(self, mock_get):
        """
        GIVEN a quarterly gov_10q_ggnfa B.9 million-euro JSON-stat payload
        WHEN scraping with QUARTERLY frequency
        THEN quarterly net-lending values are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200,
            json_data={
                "version": "2.0",
                "class": "dataset",
                "label": "Quarterly non-financial accounts for general government",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {"0": -154321.0, "1": -160000.0, "2": -148500.0},
                "id": ["freq", "unit", "s_adj", "sector", "na_item", "geo", "time"],
                "size": [1, 1, 1, 1, 1, 1, 3],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"MIO_EUR": 0},
                            "label": {"MIO_EUR": "Million euro"},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"NSA": 0},
                            "label": {"NSA": "Unadjusted data"},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S13": 0},
                            "label": {"S13": "General government"},
                        },
                    },
                    "na_item": {
                        "label": "NA item",
                        "category": {
                            "index": {"B9": 0},
                            "label": {"B9": "Net lending/borrowing"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"DE": 0},
                            "label": {"DE": "Germany"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                "2025-Q2": 0,
                                "2025-Q3": 1,
                                "2025-Q4": 2,
                            },
                            "label": {
                                "2025-Q2": "2025-Q2",
                                "2025-Q3": "2025-Q3",
                                "2025-Q4": "2025-Q4",
                            },
                        },
                    },
                },
            },
        )
        result = get_data_from_eurostat(
            "gov_10q_ggnfa_balance",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="DE",
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 10, 1), data_value=-148500.0, comment=""
        )
        assert len(result) == 3

    def test_sum_scraping_results_by_period(self):
        """
        GIVEN S.11 and S.12 GFCF series with overlapping periods
        WHEN summing by period
        THEN totals match S.11 + S.12 and stay newest-first
        """
        assert sum_scraping_results_by_period(
            [
                [
                    ScrapingResult(
                        period=date(2024, 4, 1), data_value=100.0, comment=""
                    ),
                    ScrapingResult(
                        period=date(2024, 1, 1), data_value=90.0, comment=""
                    ),
                ],
                [
                    ScrapingResult(
                        period=date(2024, 4, 1), data_value=20.0, comment=""
                    ),
                    ScrapingResult(
                        period=date(2023, 10, 1), data_value=15.0, comment=""
                    ),
                ],
            ]
        ) == [
            ScrapingResult(period=date(2024, 4, 1), data_value=120.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=90.0, comment=""),
            ScrapingResult(period=date(2023, 10, 1), data_value=15.0, comment=""),
        ]

    def test_subtract_scraping_results_by_period(self):
        """
        GIVEN export and import series with overlapping periods
        WHEN subtracting imports from exports
        THEN shared periods keep exports minus imports newest-first
        """
        assert subtract_scraping_results_by_period(
            [
                ScrapingResult(period=date(2024, 4, 1), data_value=100.0, comment=""),
                ScrapingResult(period=date(2024, 1, 1), data_value=90.0, comment=""),
            ],
            [
                ScrapingResult(period=date(2024, 4, 1), data_value=40.0, comment=""),
                ScrapingResult(period=date(2023, 10, 1), data_value=10.0, comment=""),
            ],
        ) == [
            ScrapingResult(period=date(2024, 4, 1), data_value=60.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_corporate_gfcf_sums_sectors(self, mock_get):
        """
        GIVEN S.11 and S.12 nasq_10_nf_tr GFCF responses
        WHEN scraping the corporate GFCF composite ticker
        THEN period values are the sum of both sectors
        """

        def _sector_payload(sector: str, values_by_time: dict[str, float]):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Corporate GFCF",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "unit",
                    "direct",
                    "sector",
                    "na_item",
                    "s_adj",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"CP_MEUR": 0},
                            "label": {"CP_MEUR": "Current prices, million euro"},
                        },
                    },
                    "direct": {
                        "label": "Direct",
                        "category": {"index": {"PAID": 0}, "label": {"PAID": "Paid"}},
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {sector: 0},
                            "label": {sector: sector},
                        },
                    },
                    "na_item": {
                        "label": "NA item",
                        "category": {
                            "index": {"P51G": 0},
                            "label": {"P51G": "GFCF"},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"NSA": 0},
                            "label": {"NSA": "Unadjusted"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_sector_payload("S11", {"2024-Q1": 100.0, "2024-Q2": 110.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_sector_payload("S12", {"2024-Q1": 20.0, "2024-Q2": 25.0}),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_CORPORATE_GFCF_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=135.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=120.0, comment=""),
        ]
        assert mock_get.call_count == 2

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_net_operating_surplus(self, mock_get):
        """
        GIVEN S.11 B2A3G and P51C NSA responses
        WHEN scraping nasq_10_nf_tr_nos
        THEN shared periods keep gross minus CFC newest-first
        """

        def _payload(na_item: str, values_by_time: dict[str, float]):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": na_item,
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "unit",
                    "direct",
                    "sector",
                    "na_item",
                    "s_adj",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"CP_MEUR": 0},
                            "label": {"CP_MEUR": "Current prices, million euro"},
                        },
                    },
                    "direct": {
                        "label": "Direct",
                        "category": {"index": {"PAID": 0}, "label": {"PAID": "Paid"}},
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S11": 0},
                            "label": {"S11": "Non-financial corporations"},
                        },
                    },
                    "na_item": {
                        "label": "National accounts indicator",
                        "category": {
                            "index": {na_item: 0},
                            "label": {na_item: na_item},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"NSA": 0},
                            "label": {"NSA": "Unadjusted data"},
                        },
                    },
                    "geo": {
                        "label": "Geopolitical entity",
                        "category": {"index": {"FR": 0}, "label": {"FR": "France"}},
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_payload("B2A3G", {"2024-Q1": 100.0, "2024-Q2": 120.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_payload("P51C", {"2024-Q1": 40.0, "2024-Q2": 50.0}),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_NET_OPERATING_SURPLUS_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=70.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=60.0, comment=""),
        ]
        assert mock_get.call_count == 2

    def test_deflate_scraping_results_by_period_index_base_100(self):
        """
        GIVEN nominal levels and a base-100 price deflator on shared periods
        WHEN deflating with deflator_is_index_base_100
        THEN shared periods keep nominal divided by deflator/100 newest-first
        """
        assert deflate_scraping_results_by_period(
            [
                ScrapingResult(period=date(2024, 4, 1), data_value=250.0, comment=""),
                ScrapingResult(period=date(2024, 1, 1), data_value=200.0, comment=""),
            ],
            [
                ScrapingResult(period=date(2024, 4, 1), data_value=125.0, comment=""),
                ScrapingResult(period=date(2023, 10, 1), data_value=100.0, comment=""),
            ],
            deflator_is_index_base_100=True,
        ) == [
            ScrapingResult(period=date(2024, 4, 1), data_value=200.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_real_hh_gdhi_deflates(self, mock_get):
        """
        GIVEN B6G current-price and P31 PD20 responses for Germany
        WHEN scraping the real household GDHI composite ticker
        THEN period values are B6G divided by PD20/100
        """

        def _namq_payload(
            *,
            unit: str,
            na_item: str,
            values_by_time: dict[str, float],
            sector: str | None = None,
        ):
            time_labels = list(values_by_time.keys())
            dimension_ids = ["freq", "unit", "na_item", "s_adj", "geo", "time"]
            dimensions = {
                "freq": {
                    "label": "Time frequency",
                    "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                },
                "unit": {
                    "label": "Unit",
                    "category": {"index": {unit: 0}, "label": {unit: unit}},
                },
                "na_item": {
                    "label": "National accounts indicator",
                    "category": {
                        "index": {na_item: 0},
                        "label": {na_item: na_item},
                    },
                },
                "s_adj": {
                    "label": "Seasonal adjustment",
                    "category": {
                        "index": {"SCA": 0},
                        "label": {"SCA": "Seasonally and calendar adjusted"},
                    },
                },
                "geo": {
                    "label": "Geo",
                    "category": {
                        "index": {"DE": 0},
                        "label": {"DE": "Germany"},
                    },
                },
                "time": {
                    "label": "Time",
                    "category": {
                        "index": {
                            label: index for index, label in enumerate(time_labels)
                        },
                        "label": {label: label for label in time_labels},
                    },
                },
            }
            if sector is not None:
                dimension_ids.insert(2, "sector")
                dimensions["sector"] = {
                    "label": "Sector",
                    "category": {
                        "index": {sector: 0},
                        "label": {sector: sector},
                    },
                }
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Real GDHI components",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": dimension_ids,
                "size": [1] * (len(dimension_ids) - 1) + [len(time_labels)],
                "dimension": dimensions,
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_namq_payload(
                    unit="CP_MEUR",
                    na_item="B6G",
                    sector="S14_S15",
                    values_by_time={"2024-Q1": 200.0, "2024-Q2": 250.0},
                ),
            ),
            MockResponse(
                status_code=200,
                json_data=_namq_payload(
                    unit="PD20_EUR",
                    na_item="P31_S14_S15",
                    values_by_time={"2024-Q1": 100.0, "2024-Q2": 125.0},
                ),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_REAL_HH_GDHI_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="DE",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=200.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=200.0, comment=""),
        ]
        assert mock_get.call_count == 2

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_hh_saving_ratio_uses_b6g_plus_d8(self, mock_get):
        """
        GIVEN B8G, B6G, and D8 responses for France
        WHEN scraping the household saving-ratio composite ticker
        THEN period values are B8G / (B6G + D8) × 100
        """

        def _nf_tr_payload(
            *,
            na_item: str,
            direct: str,
            values_by_time: dict[str, float],
        ):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Non-financial transactions",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "unit",
                    "direct",
                    "sector",
                    "na_item",
                    "s_adj",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {
                            "index": {"Q": 0},
                            "label": {"Q": "Quarterly"},
                        },
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"CP_MEUR": 0},
                            "label": {"CP_MEUR": "Current prices"},
                        },
                    },
                    "direct": {
                        "label": "Direction",
                        "category": {
                            "index": {direct: 0},
                            "label": {direct: direct},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S14_S15": 0},
                            "label": {"S14_S15": "Households"},
                        },
                    },
                    "na_item": {
                        "label": "National accounts indicator",
                        "category": {
                            "index": {na_item: 0},
                            "label": {na_item: na_item},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"SCA": 0},
                            "label": {"SCA": "Seasonally and calendar adjusted"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="B8G",
                    direct="RECV",
                    values_by_time={"2024-Q1": 80.0, "2024-Q2": 90.0},
                ),
            ),
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="B6G",
                    direct="RECV",
                    values_by_time={"2024-Q1": 400.0, "2024-Q2": 450.0},
                ),
            ),
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="D8",
                    direct="RECV",
                    values_by_time={"2024-Q1": 10.0, "2024-Q2": 15.0},
                ),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_HH_SAVING_RATIO_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 4, 1),
                data_value=100.0 * 90.0 / (450.0 + 15.0),
                comment="",
            ),
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=100.0 * 80.0 / (400.0 + 10.0),
                comment="",
            ),
        ]
        assert mock_get.call_count == 3

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_hh_consumption_ratio_uses_p31_over_b6g_plus_d8(
        self, mock_get
    ):
        """
        GIVEN P31, B6G, and D8 responses for France
        WHEN scraping the household consumption-ratio composite ticker
        THEN period values are P31 / (B6G + D8) × 100
        """

        def _nf_tr_payload(
            *,
            na_item: str,
            direct: str,
            values_by_time: dict[str, float],
        ):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Non-financial transactions",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "unit",
                    "direct",
                    "sector",
                    "na_item",
                    "s_adj",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {
                            "index": {"Q": 0},
                            "label": {"Q": "Quarterly"},
                        },
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"CP_MEUR": 0},
                            "label": {"CP_MEUR": "Current prices"},
                        },
                    },
                    "direct": {
                        "label": "Direction",
                        "category": {
                            "index": {direct: 0},
                            "label": {direct: direct},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S14_S15": 0},
                            "label": {"S14_S15": "Households"},
                        },
                    },
                    "na_item": {
                        "label": "National accounts indicator",
                        "category": {
                            "index": {na_item: 0},
                            "label": {na_item: na_item},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"SCA": 0},
                            "label": {"SCA": "Seasonally and calendar adjusted"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="P31",
                    direct="PAID",
                    values_by_time={"2024-Q1": 330.0, "2024-Q2": 375.0},
                ),
            ),
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="B6G",
                    direct="RECV",
                    values_by_time={"2024-Q1": 400.0, "2024-Q2": 450.0},
                ),
            ),
            MockResponse(
                status_code=200,
                json_data=_nf_tr_payload(
                    na_item="D8",
                    direct="RECV",
                    values_by_time={"2024-Q1": 10.0, "2024-Q2": 15.0},
                ),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_HH_CONSUMPTION_RATIO_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 4, 1),
                data_value=100.0 * 375.0 / (450.0 + 15.0),
                comment="",
            ),
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=100.0 * 330.0 / (400.0 + 10.0),
                comment="",
            ),
        ]
        assert mock_get.call_count == 3

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_government_tax_revenue_sca(self, mock_get):
        """
        GIVEN Eurostat SCA D2REC / D5REC / D91REC payloads
        WHEN getting gov_10q_ggnfa_taxes_sca
        THEN tax revenue equals the sum of the three components by quarter
        """

        def _ggnfa_payload(na_item: str, values_by_time: dict[str, float]):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Quarterly non-financial accounts for general government",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "unit",
                    "sector",
                    "na_item",
                    "s_adj",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"MIO_EUR": 0},
                            "label": {"MIO_EUR": "Million euro"},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S13": 0},
                            "label": {"S13": "General government"},
                        },
                    },
                    "na_item": {
                        "label": "NA item",
                        "category": {
                            "index": {na_item: 0},
                            "label": {na_item: na_item},
                        },
                    },
                    "s_adj": {
                        "label": "Seasonal adjustment",
                        "category": {
                            "index": {"SCA": 0},
                            "label": {"SCA": "Seasonally and calendar adjusted"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_ggnfa_payload("D2REC", {"2024-Q1": 100.0, "2024-Q2": 110.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_ggnfa_payload("D5REC", {"2024-Q1": 40.0, "2024-Q2": 45.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_ggnfa_payload("D91REC", {"2024-Q1": 5.0, "2024-Q2": 6.0}),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_GG_TAX_REVENUE_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=161.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=145.0, comment=""),
        ]
        assert mock_get.call_count == 3

    @patch("economic_overview.services.scrapers.eurostat.requests.get")
    def test_get_data_from_eurostat_other_liability_transactions(self, mock_get):
        """
        GIVEN Eurostat F / F3 / F4 LIAB TRN payloads
        WHEN getting gov_10q_ggfa_other_liab_trn
        THEN other liabilities equal F minus F3 minus F4 by quarter
        """

        def _ggfa_payload(na_item: str, values_by_time: dict[str, float]):
            time_labels = list(values_by_time.keys())
            return {
                "version": "2.0",
                "class": "dataset",
                "label": "Quarterly financial accounts for general government",
                "source": "ESTAT",
                "updated": "2026-10-21T11:00:00+0200",
                "value": {
                    str(index): value
                    for index, value in enumerate(values_by_time.values())
                },
                "id": [
                    "freq",
                    "na_item",
                    "finpos",
                    "stk_flow",
                    "sector",
                    "sector2",
                    "co_nco",
                    "unit",
                    "geo",
                    "time",
                ],
                "size": [1, 1, 1, 1, 1, 1, 1, 1, 1, len(time_labels)],
                "dimension": {
                    "freq": {
                        "label": "Time frequency",
                        "category": {"index": {"Q": 0}, "label": {"Q": "Quarterly"}},
                    },
                    "na_item": {
                        "label": "NA item",
                        "category": {
                            "index": {na_item: 0},
                            "label": {na_item: na_item},
                        },
                    },
                    "finpos": {
                        "label": "Financial position",
                        "category": {
                            "index": {"LIAB": 0},
                            "label": {"LIAB": "Liabilities"},
                        },
                    },
                    "stk_flow": {
                        "label": "Stock or flow",
                        "category": {
                            "index": {"TRN": 0},
                            "label": {"TRN": "Transactions"},
                        },
                    },
                    "sector": {
                        "label": "Sector",
                        "category": {
                            "index": {"S13": 0},
                            "label": {"S13": "General government"},
                        },
                    },
                    "sector2": {
                        "label": "Sector 2",
                        "category": {
                            "index": {"S1_S2": 0},
                            "label": {"S1_S2": "Total"},
                        },
                    },
                    "co_nco": {
                        "label": "Consolidation",
                        "category": {
                            "index": {"CO": 0},
                            "label": {"CO": "Consolidated"},
                        },
                    },
                    "unit": {
                        "label": "Unit",
                        "category": {
                            "index": {"MIO_EUR": 0},
                            "label": {"MIO_EUR": "Million euro"},
                        },
                    },
                    "geo": {
                        "label": "Geo",
                        "category": {
                            "index": {"FR": 0},
                            "label": {"FR": "France"},
                        },
                    },
                    "time": {
                        "label": "Time",
                        "category": {
                            "index": {
                                label: index for index, label in enumerate(time_labels)
                            },
                            "label": {label: label for label in time_labels},
                        },
                    },
                },
            }

        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data=_ggfa_payload("F", {"2024-Q1": 100.0, "2024-Q2": 120.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_ggfa_payload("F3", {"2024-Q1": 60.0, "2024-Q2": 70.0}),
            ),
            MockResponse(
                status_code=200,
                json_data=_ggfa_payload("F4", {"2024-Q1": 10.0, "2024-Q2": 15.0}),
            ),
        ]
        result = get_data_from_eurostat(
            EUROSTAT_GG_OTHER_LIABILITY_TRANSACTIONS_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=35.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=30.0, comment=""),
        ]
        assert mock_get.call_count == 3

    @patch("economic_overview.services.scrapers.eurostat.get_data_from_eurostat")
    def test_get_data_from_eurostat_financing_account(
        self, mock_get_data_from_eurostat
    ):
        """
        GIVEN F LIAB and F ASS series for shared quarters
        WHEN getting gg_financing_account
        THEN net financing equals liabilities minus assets by quarter
        """
        mock_get_data_from_eurostat.side_effect = (
            lambda ticker, target_period=None, frequency=None, location="": {
                EUROSTAT_GG_TOTAL_LIABILITY_TRANSACTIONS_TICKER: [
                    ScrapingResult(
                        period=date(2024, 4, 1), data_value=120.0, comment=""
                    ),
                    ScrapingResult(
                        period=date(2024, 1, 1), data_value=100.0, comment=""
                    ),
                ],
                EUROSTAT_GG_ASSET_TRANSACTIONS_TICKER: [
                    ScrapingResult(
                        period=date(2024, 4, 1), data_value=45.0, comment=""
                    ),
                    ScrapingResult(
                        period=date(2024, 1, 1), data_value=40.0, comment=""
                    ),
                ],
            }[ticker]
        )
        result = get_data_from_eurostat.__wrapped__(
            EUROSTAT_GG_FINANCING_ACCOUNT_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
            location="FR",
        )
        assert result == [
            ScrapingResult(period=date(2024, 4, 1), data_value=75.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=60.0, comment=""),
        ]

    @patch("economic_overview.services.scrapers.eurostat.get_data_from_eurostat")
    def test_get_data_from_eurostat_palma_ratio(self, mock_get_data_from_eurostat):
        """
        GIVEN ilc_di01 D10 and D1–D4 SHARE series for one country
        WHEN scraping ilc_di01_palma
        THEN shared years keep D10 / (D1+D2+D3+D4)
        """
        # Usage of dict: maps Palma input tickers to annual SHARE scraping results.
        share_series_by_ticker = {
            EUROSTAT_PALMA_TOP_DECILE_TICKER: [
                ScrapingResult(period=date(2024, 1, 1), data_value=24.6, comment=""),
                ScrapingResult(period=date(2023, 1, 1), data_value=24.0, comment=""),
            ],
            EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS[0]: [
                ScrapingResult(period=date(2024, 1, 1), data_value=3.1, comment=""),
                ScrapingResult(period=date(2023, 1, 1), data_value=3.0, comment=""),
            ],
            EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS[1]: [
                ScrapingResult(period=date(2024, 1, 1), data_value=5.3, comment=""),
                ScrapingResult(period=date(2023, 1, 1), data_value=5.2, comment=""),
            ],
            EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS[2]: [
                ScrapingResult(period=date(2024, 1, 1), data_value=6.8, comment=""),
                ScrapingResult(period=date(2023, 1, 1), data_value=6.7, comment=""),
            ],
            EUROSTAT_PALMA_BOTTOM_DECILE_TICKERS[3]: [
                ScrapingResult(period=date(2024, 1, 1), data_value=8.0, comment=""),
                ScrapingResult(period=date(2023, 1, 1), data_value=7.9, comment=""),
            ],
        }
        mock_get_data_from_eurostat.side_effect = (
            lambda ticker, target_period=None, frequency=None, location="": (
                share_series_by_ticker[ticker]
            )
        )
        result = get_data_from_eurostat.__wrapped__(
            EUROSTAT_PALMA_TICKER,
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
            location="FR",
        )
        assert result == [
            ScrapingResult(
                period=date(2024, 1, 1),
                data_value=24.6 / (3.1 + 5.3 + 6.8 + 8.0),
                comment="",
            ),
            ScrapingResult(
                period=date(2023, 1, 1),
                data_value=24.0 / (3.0 + 5.2 + 6.7 + 7.9),
                comment="",
            ),
        ]
