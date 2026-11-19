"""Tests for the Japan Cabinet Office scraper."""

from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from freezegun import freeze_time

from core.testing import MockResponse, read_file_content
from economic_overview.models.economic_indicators import (
    EconomicPublicationFrequencyChoices,
)
from economic_overview.services.config import (
    JP_CAO_GGO_EXPENSE_TICKER,
    JP_CAO_GGO_FINANCING_ACCOUNT_TICKER,
    JP_CAO_GGO_INTEREST_TICKER,
    JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER,
    JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER,
    JP_CAO_GGO_NET_LENDING_TICKER,
    JP_CAO_GGO_OTHER_REVENUE_TICKER,
    JP_CAO_GGO_REVENUE_TICKER,
    JP_CAO_GGO_ROW_LABEL_BY_TICKER,
    JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER,
    JP_CAO_GGO_TAXES_TICKER,
    JP_CAO_SHOUHI_CCI_COLUMN,
    JP_CAO_SHOUHI_EMPLOYMENT_COLUMN,
)
from economic_overview.services.scrapers.common import (
    ScrapedIndustryProfitability,
    ScrapingResult,
)
from economic_overview.services.scrapers.jp_cabinet_office import (
    _find_japan_cabinet_office_cofog_xlsx_url,
    _get_nominal_original_gva_csv_url,
    _parse_japan_cabinet_office_cofog_workbook,
    _parse_japan_cabinet_office_ggd_workbook,
    _parse_japan_cabinet_office_ggo_workbook,
    _parse_japan_cabinet_office_kakei_workbook,
    _parse_japan_cabinet_office_levels_csv,
    _parse_japan_cabinet_office_shouhi_workbook,
    get_data_from_japan_cabinet_office,
    get_industry_gva_from_esri,
)

_ESRI_GVA_TOP_HTML = """
<a href="/jp/sna/sonota/seisanqna/seisanqna_2023q4.html">latest</a>
"""

_ESRI_GVA_RELEASE_HTML = """
<a href="/jp/sna/data/data_list/seisanqna/files/tables/b2020/2023q4/gaku-mgf23q4.csv">
名目原系列
</a>
"""

_ESRI_GVA_CSV_TEXT = """\
経済活動別付加価値額,,,,,,,,,,,,,,,,,,,,
Value Added by Economic Activity,,,,,,,,,,,,,,,,,,,,
,note,,,,,,,,,,,,,,,,,,,,
,note,,,,,,,,,,,,,,,,,,,,
,名目原系列,,,,,,,,,,,,,,,,,,
,"Nominal, Original Series",,,,,,,,,,,,,,,,,,
,,１．農林水産業,２．鉱業,３．製造業,,,,,,,,４．電気,５．建設,６．卸売,７．運輸,８．宿泊,９．情報,１０．金融,１１．不動産,１２．専門,１３．公務,１４．教育,１５．保健,１６．その他,経済活動　計,合計,統計上の不突合,国内総生産(支出側),,
,,"1. Agriculture, forestry and fishing",2. Mining,3. Manufacturing,,,,,,,,"4. Electricity",5. Construction,6. Wholesale and retail trade,7. Transport and postal services,8. Accommodation and food service activities,9. Information and communications,10. Finance and insurance,11. Real estate,"12. Professional, scientific and technical activities",13. Public administration,14. Education,15. Human health and social work activities,16. Other service activities,All activities,Gross domestic product (not including statistical discrepancy),Statistical discrepancy,Gross domestic product (Expenditure Approach),,
年,期,,,（１）食料品,（２）繊維製品,（３）パルプ・紙・紙加工品,（４）化学,（５）石油・石炭製品,（６）窯業・土石製品,（７）一次金属,（８）金属製品,（９）はん用・生産用・業務用機械,（１０）電子部品・デバイス,（１１）電気機械,（１２）情報・通信機器,（１３）輸送用機械,（１４）その他の製造業,,,,,,,,,第１次産業,第２次産業,第３次産業,
year,quarter,,,(1)Food products and beverages,(2)Textile products,"(3)Pulp, paper and paper products",(4)Chemicals,(5)Petroleum and coal products,(6)Non-metallic mineral products,(7)Basic metal,(8)Fabricated metal products,"(9)General-purpose, production and business oriented machinery",(10)Electronic components and devices,"(11)Electrical machinery, equipment and supplies",(12)Information and communication electronics equipment,(13)Transport equipment,(14)Other manufacturing,,,,,,,,,Primary industries,Secondary industries,Tertiary industries,
2023,Ⅰ,2023Q1,1,2,30,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,5,6,7,8,9,10,11,12,13,14,15,16,100,100,0,100,10,20,70
2023,Ⅱ,2023Q2,1,2,30,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,5,6,7,8,9,10,11,12,13,14,15,16,100,100,0,100,10,20,70
2023,Ⅲ,2023Q3,1,2,30,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,5,6,7,8,9,10,11,12,13,14,15,16,100,100,0,100,10,20,70
2023,Ⅳ,2023Q4,1,2,30,3,3,3,3,3,3,3,3,3,3,3,3,3,3,4,5,6,7,8,9,10,11,12,13,14,15,16,100,100,0,100,10,20,70
"""


class TestJapanCabinetOfficeDataIngestion(TestCase):
    """Tests for Cabinet Office quarterly GDP / debt scraping."""

    MOCK_GDP_CSV = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/gaku-jk.csv"
    )
    MOCK_GGD_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/ggd.xlsx"
    )
    MOCK_GGO_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/ggo.xlsx"
    )
    MOCK_KAKEI_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/kakei.xlsx"
    )
    MOCK_SHOUHI_SA_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/shouhi2.xlsx"
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

    def test_parse_japan_cabinet_office_ggo_workbook_net_lending(self):
        """
        GIVEN an SDDS Plus GGO Excel fixture
        WHEN parsing the Net lending/borrowing row
        THEN quarterly NSA levels are returned newest-first without NA cells
        """
        result = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[JP_CAO_GGO_NET_LENDING_TICKER],
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=186.5, comment=""
        )
        assert result[1] == ScrapingResult(
            period=date(2025, 4, 1), data_value=1616.9, comment=""
        )
        assert len(result) == 43

    def test_parse_japan_cabinet_office_ggo_workbook_revenue(self):
        """
        GIVEN an SDDS Plus GGO Excel fixture
        WHEN parsing the Revenue row
        THEN quarterly NSA revenue levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[JP_CAO_GGO_REVENUE_TICKER],
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=60052.2, comment=""
        )

    def test_parse_japan_cabinet_office_ggo_workbook_expense(self):
        """
        GIVEN an SDDS Plus GGO Excel fixture
        WHEN parsing the Expenses row
        THEN quarterly NSA expense levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[JP_CAO_GGO_EXPENSE_TICKER],
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=59496.7, comment=""
        )

    def test_parse_japan_cabinet_office_ggo_workbook_interest(self):
        """
        GIVEN an SDDS Plus GGO Excel fixture
        WHEN parsing the Interest expense row
        THEN quarterly NSA interest levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[JP_CAO_GGO_INTEREST_TICKER],
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=3108.5, comment=""
        )

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
    def test_get_data_from_japan_cabinet_office_ggo_net_lending(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_net_lending
        THEN quarterly NSA net lending levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_NET_LENDING_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=186.5, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_revenue(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_revenue
        THEN quarterly NSA revenue levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_REVENUE_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=60052.2, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_interest(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_interest
        THEN quarterly NSA interest levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_INTEREST_TICKER,
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2025, 7, 1), data_value=3108.5, comment=""
        )

    def test_parse_japan_cabinet_office_kakei_workbook(self):
        """
        GIVEN a household disposable-income Excel fixture
        WHEN parsing the real disposable-income column
        THEN quarterly SA levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_kakei_workbook(
            self.MOCK_KAKEI_XLSX, column_index=16
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=304403.1, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=300000.0, comment=""),
            ScrapingResult(period=date(1994, 4, 1), data_value=280000.0, comment=""),
            ScrapingResult(period=date(1994, 1, 1), data_value=279460.8, comment=""),
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_kakei_nominal_saving(self, mock_get):
        """
        GIVEN kakei files-index and Excel responses
        WHEN getting kakei_nominal_saving
        THEN the latest workbook Saving column observation is returned
        """
        files_html = (
            '<a href="2026/tables/kakei_26q2.xlsx">q2</a>'
            '<a href="2025/tables/kakei_25q4.xlsx">q4</a>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "kakei_nominal_saving",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=4709.9, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_kakei_saving_ratio(self, mock_get):
        """
        GIVEN kakei files-index and Excel responses
        WHEN getting kakei_saving_ratio
        THEN saving / disposable income × 100 is returned (not the truncated %)
        """
        files_html = (
            '<a href="2026/tables/kakei_26q2.xlsx">q2</a>'
            '<a href="2025/tables/kakei_25q4.xlsx">q4</a>'
        )
        # Saving ratio derives saving + DI; each column download hits files + xlsx.
        mock_get.side_effect = [
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "kakei_saving_ratio",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=100.0 * 4709.9 / 355152.6,
            comment="",
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_kakei_nominal_consumption(
        self, mock_get
    ):
        """
        GIVEN kakei files-index and Excel responses
        WHEN getting kakei_nominal_consumption
        THEN the latest workbook Consumption of households observation is returned
        """
        files_html = (
            '<a href="2026/tables/kakei_26q2.xlsx">q2</a>'
            '<a href="2025/tables/kakei_25q4.xlsx">q4</a>'
        )
        mock_get.side_effect = [
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "kakei_nominal_consumption",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1), data_value=350442.7, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_kakei_consumption_ratio(self, mock_get):
        """
        GIVEN kakei files-index and Excel responses
        WHEN getting kakei_consumption_ratio
        THEN consumption / disposable income × 100 is returned
        """
        files_html = (
            '<a href="2026/tables/kakei_26q2.xlsx">q2</a>'
            '<a href="2025/tables/kakei_25q4.xlsx">q4</a>'
        )
        # Consumption ratio → consumption + DI (two column downloads).
        mock_get.side_effect = [
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
            MockResponse(status_code=200, content=files_html.encode()),
            MockResponse(status_code=200, content=self.MOCK_KAKEI_XLSX, text=""),
        ]

        result = get_data_from_japan_cabinet_office(
            "kakei_consumption_ratio",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 4, 1),
            data_value=100.0 * 350442.7 / 355152.6,
            comment="",
        )

    def test_parse_japan_cabinet_office_shouhi_workbook_cci(self):
        """
        GIVEN a Cabinet Office SA Consumer Confidence Survey workbook fixture
        WHEN parsing the headline Consumer Confidence Index column
        THEN monthly SA index levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_shouhi_workbook(
            self.MOCK_SHOUHI_SA_XLSX, JP_CAO_SHOUHI_CCI_COLUMN
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=35.0, comment=""
        )
        assert result[1] == ScrapingResult(
            period=date(2026, 9, 1), data_value=35.4, comment=""
        )

    def test_parse_japan_cabinet_office_shouhi_workbook_employment(self):
        """
        GIVEN a Cabinet Office SA Consumer Confidence Survey workbook fixture
        WHEN parsing the Employment perception column
        THEN monthly SA index levels are returned newest-first
        """
        result = _parse_japan_cabinet_office_shouhi_workbook(
            self.MOCK_SHOUHI_SA_XLSX, JP_CAO_SHOUHI_EMPLOYMENT_COLUMN
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=39.4, comment=""
        )
        assert result[1] == ScrapingResult(
            period=date(2026, 9, 1), data_value=40.0, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_shouhi_cci(self, mock_get):
        """
        GIVEN the ESRI shouhi2.xlsx download
        WHEN getting shouhi_cci_sa
        THEN parsed Consumer Confidence Index SA levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_SHOUHI_SA_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            "shouhi_cci_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=35.0, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_shouhi_employment(self, mock_get):
        """
        GIVEN the ESRI shouhi2.xlsx download
        WHEN getting shouhi_employment_sa
        THEN parsed Employment SA levels are returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_SHOUHI_SA_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            "shouhi_employment_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result[0] == ScrapingResult(
            period=date(2026, 10, 1), data_value=39.4, comment=""
        )

    @override_settings(ESTAT_APP_ID="test-estat-app-id")
    @patch("economic_overview.services.scrapers.stat_of_jp.requests.get")
    def test_get_data_from_japan_cabinet_office_machinery_orders(self, mock_get):
        """
        GIVEN an e-Stat getStatsData payload for private excl. volatile orders
        WHEN getting machinery_orders_private_ex_volatile_sa
        THEN SA billion-yen levels are returned newest-first
        """
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {
            "GET_STATS_DATA": {
                "RESULT": {"STATUS": 0, "ERROR_MSG": "正常に終了しました。"},
                "STATISTICAL_DATA": {
                    "CLASS_INF": {"CLASS_OBJ": []},
                    "DATA_INF": {
                        "VALUE": [
                            {
                                "@cat01": "160",
                                "@cat02": "100",
                                "@time": "2026000808",
                                "$": "920500.5",
                            },
                            {
                                "@cat01": "160",
                                "@cat02": "100",
                                "@time": "2026000707",
                                "$": "910000",
                            },
                            {
                                "@cat01": "160",
                                "@cat02": "100",
                                "@time": "2026000606",
                                "$": "900000",
                            },
                        ]
                    },
                },
            }
        }

        result = get_data_from_japan_cabinet_office(
            "machinery_orders_private_ex_volatile_sa",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 8, 1), data_value=920.5005, comment=""),
            ScrapingResult(period=date(2026, 7, 1), data_value=910.0, comment=""),
            ScrapingResult(period=date(2026, 6, 1), data_value=900.0, comment=""),
        ]


class TestJapanCabinetOfficeGovernmentRevenueAndFunctions(TestCase):
    """Tests for ESRI general-government revenue components and COFOG outlays."""

    MOCK_GGO_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/ggo.xlsx"
    )
    MOCK_COFOG_XLSX = read_file_content(
        "economic_overview/tests/mock_web_data/jp_cabinet_office/data/cofog_s7.xlsx"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        get_data_from_japan_cabinet_office.cache_clear()
        _find_japan_cabinet_office_cofog_xlsx_url.cache_clear()

    def test_parse_japan_cabinet_office_ggo_workbook_financial_account_rows(self):
        """
        GIVEN an SDDS Plus GGO Excel fixture
        WHEN parsing the net acquisition of financial assets and net incurrence
            of liabilities rows
        THEN every published quarter is returned newest-first
        """
        net_acquisition_financial_assets = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[
                JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER
            ],
        )
        net_incurrence_liabilities = _parse_japan_cabinet_office_ggo_workbook(
            self.MOCK_GGO_XLSX,
            JP_CAO_GGO_ROW_LABEL_BY_TICKER[
                JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER
            ],
        )
        assert len(net_acquisition_financial_assets) == 46
        assert net_acquisition_financial_assets[:2] == [
            ScrapingResult(period=date(2026, 4, 1), data_value=-14835.1, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=19320.7, comment=""),
        ]
        assert net_acquisition_financial_assets[-1] == ScrapingResult(
            period=date(2015, 1, 1), data_value=8448.4, comment=""
        )
        assert len(net_incurrence_liabilities) == 46
        assert net_incurrence_liabilities[:2] == [
            ScrapingResult(period=date(2026, 4, 1), data_value=-824.2, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=1266.0, comment=""),
        ]
        assert net_incurrence_liabilities[-1] == ScrapingResult(
            period=date(2015, 1, 1), data_value=2564.3, comment=""
        )

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_net_incurrence_liabilities(
        self, mock_get
    ):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_net_incurrence_liabilities for 2026-Q2
        THEN the quarterly NSA net incurrence of liabilities is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_NET_INCURRENCE_LIABILITIES_TICKER,
            "2026-Q2",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=-824.2, comment="")
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_net_acquisition_financial_assets(
        self, mock_get
    ):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_net_acquisition_financial_assets for 2026-Q2
        THEN the quarterly NSA net acquisition of financial assets is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_NET_ACQUISITION_FINANCIAL_ASSETS_TICKER,
            "2026-Q2",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=-14835.1, comment="")
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_financing_account(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_financing_account for 2026-Q2
        THEN the value is net incurrence of liabilities minus net acquisition of
            financial assets
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_FINANCING_ACCOUNT_TICKER,
            "2026-Q2",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 4, 1),
                data_value=-824.2 - -14835.1,
                comment="",
            )
        ]

    @freeze_time("2026-11-11")
    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_find_japan_cabinet_office_cofog_xlsx_url(self, mock_get):
        """
        GIVEN 2026 and 2025 COFOG workbook URLs that return 404, and a 2024
            workbook that downloads
        WHEN finding the COFOG workbook URL
        THEN the 2024 URL is returned after probing newest-first
        """
        mock_get.side_effect = [
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=200, content=self.MOCK_COFOG_XLSX, text=""),
        ]

        result = _find_japan_cabinet_office_cofog_xlsx_url()
        assert result == (
            "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/2024/tables/"
            "2024s7_en.xlsx"
        )
        assert [call.args[0] for call in mock_get.call_args_list] == [
            "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/2026/tables/"
            "2026s7_en.xlsx",
            "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/2025/tables/"
            "2025s7_en.xlsx",
            "https://www.esri.cao.go.jp/en/sna/data/kakuhou/files/2024/tables/"
            "2024s7_en.xlsx",
        ]

    @freeze_time("2026-11-11")
    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_find_japan_cabinet_office_cofog_xlsx_url_none_found(self, mock_get):
        """
        GIVEN every COFOG workbook URL in the lookback window returns 404 or a
            small HTML page with status 200
        WHEN finding the COFOG workbook URL
        THEN None is returned after probing the current year and five prior years
        """
        mock_get.side_effect = [
            MockResponse(status_code=200, content=b"<html>Moved</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
            MockResponse(status_code=404, content=b"<html>Not Found</html>"),
        ]

        result = _find_japan_cabinet_office_cofog_xlsx_url()
        assert result is None
        assert mock_get.call_count == 6

    @freeze_time("2026-11-11")
    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_cofog_no_workbook_found(self, mock_get):
        """
        GIVEN no COFOG workbook URL in the lookback window downloads
        WHEN getting esri_cofog_total at annual frequency
        THEN a not-found error result is returned
        """
        mock_get.return_value = MockResponse(
            status_code=404, content=b"<html>Not Found</html>"
        )

        result = get_data_from_japan_cabinet_office(
            "esri_cofog_total",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "No Japan Cabinet Office COFOG workbook found in the last 5 "
                    "annual-estimates releases."
                ),
            )
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_taxes(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_taxes for 2025-Q3
        THEN the quarterly NSA tax revenue level is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_TAXES_TICKER,
            "2025-Q3",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2025, 7, 1), data_value=33910.5, comment="")
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_social_contributions(
        self, mock_get
    ):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_social_contributions for 2025-Q3
        THEN the quarterly NSA social-contribution level is returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_SOCIAL_CONTRIBUTIONS_TICKER,
            "2025-Q3",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2025, 7, 1), data_value=20030.3, comment="")
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_ggo_other_revenue(self, mock_get):
        """
        GIVEN the SDDS Plus GGO workbook download
        WHEN getting ggo_other_revenue for 2025-Q3
        THEN the value is revenue minus taxes minus social contributions
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_GGO_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            JP_CAO_GGO_OTHER_REVENUE_TICKER,
            "2025-Q3",
            EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2025, 7, 1),
                data_value=60052.2 - 33910.5 - 20030.3,
                comment="",
            )
        ]

    def test_parse_japan_cabinet_office_cofog_workbook(self):
        """
        GIVEN a Supporting Table 7 fixture with FY2022 and FY2023 sheets
        WHEN parsing the Total row and Social protection (code 10)
        THEN each fiscal year's summed outlays are returned newest-first
        """
        total_outlays = _parse_japan_cabinet_office_cofog_workbook(
            self.MOCK_COFOG_XLSX, "Total"
        )
        social_protection_outlays = _parse_japan_cabinet_office_cofog_workbook(
            self.MOCK_COFOG_XLSX, "10"
        )
        assert total_outlays == [
            ScrapingResult(period=date(2023, 1, 1), data_value=243054.5, comment=""),
            ScrapingResult(period=date(2022, 1, 1), data_value=245845.4, comment=""),
        ]
        assert social_protection_outlays == [
            ScrapingResult(period=date(2023, 1, 1), data_value=95400.6, comment=""),
            ScrapingResult(period=date(2022, 1, 1), data_value=95439.7, comment=""),
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_cofog_general_public_services(
        self, mock_get
    ):
        """
        GIVEN the Supporting Table 7 (COFOG) workbook download
        WHEN getting esri_cofog_gf01 at annual frequency
        THEN General public services outlays are returned per fiscal year
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_COFOG_XLSX, text=""
        )

        result = get_data_from_japan_cabinet_office(
            "esri_cofog_gf01",
            frequency=EconomicPublicationFrequencyChoices.ANNUAL,
        )
        assert result == [
            ScrapingResult(period=date(2023, 1, 1), data_value=13315.1, comment=""),
            ScrapingResult(period=date(2022, 1, 1), data_value=13220.1, comment=""),
        ]

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_data_from_japan_cabinet_office_cofog_quarterly_unsupported(
        self, mock_get
    ):
        """
        GIVEN an annual-only COFOG ticker
        WHEN requesting it at quarterly frequency
        THEN an unsupported-frequency error result is returned without HTTP calls
        """
        result = get_data_from_japan_cabinet_office(
            "esri_cofog_total",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment=(
                    "Unsupported frequency for Japan Cabinet Office COFOG scrape: "
                    f"{EconomicPublicationFrequencyChoices.QUARTERLY}"
                ),
            )
        ]
        mock_get.assert_not_called()


class TestGetIndustryGvaFromEsri(TestCase):
    """Tests for get_industry_gva_from_esri."""

    def tearDown(self):
        """Clear scrape caches after each test."""
        get_industry_gva_from_esri.cache_clear()
        _get_nominal_original_gva_csv_url.cache_clear()

    @patch("economic_overview.services.scrapers.jp_cabinet_office.requests.get")
    def test_get_industry_gva_from_esri(self, mock_get):
        """
        GIVEN ESRI top/release pages and a nominal original GVA CSV
        WHEN scraping industry GVA
        THEN complete calendar years are annualized into million-yen leaf figures
        """
        top_response = Mock()
        top_response.raise_for_status.return_value = None
        top_response.text = _ESRI_GVA_TOP_HTML
        release_response = Mock()
        release_response.raise_for_status.return_value = None
        release_response.text = _ESRI_GVA_RELEASE_HTML
        csv_response = Mock()
        csv_response.raise_for_status.return_value = None
        csv_response.content = _ESRI_GVA_CSV_TEXT.encode("utf-8")
        mock_get.side_effect = [top_response, release_response, csv_response]

        scraped_industry_profitabilities = get_industry_gva_from_esri()
        agriculture = [
            scraped_industry_profitability
            for scraped_industry_profitability in scraped_industry_profitabilities
            if scraped_industry_profitability["industry_code"] == "1"
        ]
        food = [
            scraped_industry_profitability
            for scraped_industry_profitability in scraped_industry_profitabilities
            if scraped_industry_profitability["industry_code"] == "3.1"
        ]
        assert agriculture == [
            ScrapedIndustryProfitability(
                industry_code="1",
                industry_label="Agriculture, forestry and fishing",
                period=date(2023, 1, 1),
                turnover=None,
                operating_profit=None,
                gva=4000.0,
            )
        ]
        assert food == [
            ScrapedIndustryProfitability(
                industry_code="3.1",
                industry_label="Food products and beverages",
                period=date(2023, 1, 1),
                turnover=None,
                operating_profit=None,
                gva=12000.0,
            )
        ]
        assert all(
            scraped_industry_profitability["industry_code"] != "3"
            for scraped_industry_profitability in scraped_industry_profitabilities
        )
