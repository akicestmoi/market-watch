"""Tests for the Japan Cabinet Office scraper."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.testing import MockResponse, read_file_content
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.config import (
    JP_CAO_NET_LENDING_AMOUNT_SHEET,
    JP_CAO_NET_LENDING_PCT_SHEET,
)
from economic_overview.services.scrapers.common import ScrapingResult
from economic_overview.services.scrapers.jp_cabinet_office import (
    _parse_japan_cabinet_office_ggd_workbook,
    _parse_japan_cabinet_office_levels_csv,
    _parse_japan_cabinet_office_net_lending_workbook,
    get_data_from_japan_cabinet_office,
)


class TestJapanCabinetOfficeDataIngestion(TestCase):
    """Tests for Cabinet Office quarterly GDP / debt scraping."""

    MOCK_GDP_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/gaku-jk.csv"
    )
    MOCK_NOMINAL_GDP_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/gaku-mk.csv"
    )
    MOCK_GGD_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/ggd.xlsx"
    )
    MOCK_NET_LENDING_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/net_lending.xlsx"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_japan_cabinet_office.cache_clear()

    def test_parse_japan_cabinet_office_gdp_csv(self):
        """
        GIVEN a Cabinet Office real SA GDP CSV fixture
        WHEN parsing headline GDP values
        THEN quarterly GDP levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_levels_csv(
            self.MOCK_GDP_CSV, column_index=1
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=599000.0, comment=""
        )
        assert result[-1] == ScrapingResult(
            period=date(1994, 1, 1), data_value=465071.2, comment=""
        )

    def test_parse_japan_cabinet_office_levels_csv_component_column(self):
        """
        GIVEN a real SA expenditure CSV fixture
        WHEN parsing the household-consumption column
        THEN quarterly component levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_levels_csv(
            self.MOCK_GDP_CSV, column_index=3
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=310000.0, comment=""
        )

    def test_parse_japan_cabinet_office_ggd_workbook(self):
        """
        GIVEN an SDDS Plus GGD Excel fixture
        WHEN parsing Total gross debt
        THEN end-quarter stocks are mapped to quarter-start dates newest-first
        """
        result = _parse_japan_cabinet_office_ggd_workbook(self.MOCK_GGD_XLSX)
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=1370000.0, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=1300000.0, comment=""),
        ]

    def test_parse_japan_cabinet_office_net_lending_workbook_amount(self):
        """
        GIVEN an SNA table 18 Excel fixture
        WHEN parsing the calendar-year amount sheet
        THEN general-government net lending levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_net_lending_workbook(
            self.MOCK_NET_LENDING_XLSX, JP_CAO_NET_LENDING_AMOUNT_SHEET
        )
        assert result == [
            ScrapingResult(period=date(2024, 1, 1), data_value=-10648.9, comment=""),
            ScrapingResult(period=date(2023, 1, 1), data_value=-14360.9, comment=""),
        ]

    def test_parse_japan_cabinet_office_net_lending_workbook_pct_gdp(self):
        """
        GIVEN an SNA table 18 Excel fixture
        WHEN parsing the calendar-year % of GDP sheet
        THEN general-government net lending ratios are returned newest-first
        """
        result = _parse_japan_cabinet_office_net_lending_workbook(
            self.MOCK_NET_LENDING_XLSX, JP_CAO_NET_LENDING_PCT_SHEET
        )
        assert result == [
            ScrapingResult(period=date(2024, 1, 1), data_value=-1.7, comment=""),
            ScrapingResult(period=date(2023, 1, 1), data_value=-2.4, comment=""),
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_success(self, mock_get):
        """
        GIVEN archive / menu / CSV responses for the latest GDP release
        WHEN getting Cabinet Office GDP data
        THEN parsed quarterly levels are returned
        """
        archive_html = (
            '<a href="/en/sna/data/sokuhou/files/2026/qe262_2/gdemenuea.html">'
            "latest</a>"
        )
        menu_html = (
            '<a href="/jp/sna/data/data_list/sokuhou/files/2026/qe262_2/tables/'
            'gaku-jk2622.csv">csv</a>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=archive_html.encode()),
            MockResponse(status_code=200, content=menu_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_GDP_CSV, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "gaku-jk",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=599000.0, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_component_ticker(self, mock_get):
        """
        GIVEN archive / menu / CSV responses for the latest GDP release
        WHEN getting a GDP component ticker
        THEN the mapped column level is returned
        """
        archive_html = (
            '<a href="/en/sna/data/sokuhou/files/2026/qe262_2/gdemenuea.html">'
            "latest</a>"
        )
        menu_html = (
            '<a href="/jp/sna/data/data_list/sokuhou/files/2026/qe262_2/tables/'
            'gaku-jk2622.csv">csv</a>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=archive_html.encode()),
            MockResponse(status_code=200, content=menu_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_GDP_CSV, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "gaku-jk-nx",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=12000.0, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_debt_outstanding(self, mock_get):
        """
        GIVEN SDDS Plus page and GGD Excel responses
        WHEN getting ggd_total
        THEN outstanding debt levels are returned
        """
        sdds_html = '<a href="tables/ggd.xlsx">General Government Gross Debt</a>'
        mock_get.side_effect = [
            MockResponse(status_code=200, content=sdds_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_GGD_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "ggd_total",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=1370000.0, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_debt_pct_gdp(self, mock_get):
        """
        GIVEN GGD Excel and nominal SA GDP CSV fixtures
        WHEN getting ggd_pct_gdp
        THEN debt as percent of annualized nominal GDP is returned
        """
        sdds_html = '<a href="tables/ggd.xlsx">General Government Gross Debt</a>'
        archive_html = (
            '<a href="/en/sna/data/sokuhou/files/2026/qe262_2/gdemenuea.html">'
            "latest</a>"
        )
        menu_html = (
            '<a href="/jp/sna/data/data_list/sokuhou/files/2026/qe262_2/tables/'
            'gaku-mk2622.csv">csv</a>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=sdds_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_GGD_XLSX, text=""),
            MockResponse(status_code=200, content=archive_html.encode()),
            MockResponse(status_code=200, content=menu_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_NOMINAL_GDP_CSV, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "ggd_pct_gdp",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=1370000.0 / 670000.0 * 100.0,
            comment="",
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_net_lending(self, mock_get):
        """
        GIVEN annual-accounts top / report / Excel responses
        WHEN getting net_lending_gg_cy
        THEN calendar-year general-government levels are returned
        """
        top_html = (
            '<a href="/en/sna/data/kakuhou/files/2024/2024annual_report_e.html">'
            "2024</a>"
        )
        report_html = '<a href="tables/2024s18_en.xlsx">Net Lending</a>'
        mock_get.side_effect = [
            MockResponse(status_code=200, content=top_html.encode()),
            MockResponse(status_code=200, content=report_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_NET_LENDING_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "net_lending_gg_cy",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result[0] == ScrapingResult(
            period=date(2024, 1, 1), data_value=-10648.9, comment=""
        )
