"""Tests for economic indicator scraping helpers."""

import io
import zipfile
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.conftest import MockResponse, read_file_content
from economic_overview.models import EconomicPublicationFrequencyChoices
from economic_overview.services.data_ingestion import (
    ScrapingResult,
    _get_data_from_insee,
    _parse_insee_period,
)


def _create_mock_zip_with_csv(csv_name: str, csv_content: str) -> bytes:
    """Helper to create a mock ZIP file with CSV content."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(csv_name, csv_content)
    return zip_buffer.getvalue()


class TestInseeDataScraping(TestCase):
    """Test cases for INSEE data scraping functions."""

    # Load success.zip and convert text files to UTF-8 encoding
    MOCK_INSEE_SUCCESS_ZIP = read_file_content(
        "economic_overview/tests/mock_web_data/insee/data/success.zip"
    )

    def tearDown(self):
        """Clear cache after each test to prevent state leakage between tests."""
        _get_data_from_insee.cache_clear()

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_success_no_target_period(self, mock_get):
        """
        GIVEN a successful INSEE ZIP response with CSV data
        WHEN getting data without target period
        THEN all observations are returned with the latest first
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_INSEE_SUCCESS_ZIP, text=""
        )

        result = _get_data_from_insee("001565530")
        assert result[0] == ScrapingResult(
            period=date(2025, 11, 1),
            data_value=97.6,
            comment="",
        )
        assert len(result) > 1

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_success_with_target_period(self, mock_get):
        """
        GIVEN a successful INSEE ZIP response with CSV data
        WHEN getting data with target period
        THEN the data for that period should be returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_INSEE_SUCCESS_ZIP, text=""
        )

        result = _get_data_from_insee("001565530", "2024-10")
        assert result == [
            ScrapingResult(
                period=date(2024, 10, 1),
                data_value=97.0,
                comment="",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_http_error(self, mock_get):
        """
        GIVEN an HTTP error response from INSEE
        WHEN getting data
        THEN None values should be returned with error comment in a ScrapingResult
        """
        mock_get.return_value = MockResponse(status_code=404, content=b"Not Found")

        result = _get_data_from_insee("001565530")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Not Found",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_invalid_zip(self, mock_get):
        """
        GIVEN an invalid ZIP file response
        WHEN getting data
        THEN None values should be returned with error comment
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=b"Invalid ZIP content", text=""
        )

        result = _get_data_from_insee("001565530")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Error reading ZIP content: File is not a zip file",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_no_csv_file(self, mock_get):
        """
        GIVEN a ZIP file without valeurs_mensuelles CSV
        WHEN getting data
        THEN None values should be returned with error comment
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("other_file.csv", "data")
        mock_get.return_value = MockResponse(
            status_code=200, content=zip_buffer.getvalue(), text=""
        )

        result = _get_data_from_insee("001565530")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No 'valeurs_mensuelles' CSV found in archive.",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_invalid_csv_format(self, mock_get):
        """
        GIVEN a CSV file with invalid format
        WHEN getting data
        THEN None values should be returned with error comment
        """
        csv_content = "Invalid;Format\nData;Here\n"
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee("001565530")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Data is not in the expected format.",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_no_data_rows(self, mock_get):
        """
        GIVEN a CSV file with only header row
        WHEN getting data
        THEN None values should be returned with error comment
        """
        csv_content = "Libellé;Valeur\nPériode;2024-01\n"
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee("001565530")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No data found.",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_target_period_not_found(self, mock_get):
        """
        GIVEN a CSV file without the target period
        WHEN getting data for that period
        THEN None values should be returned with error comment
        """
        csv_content = "Libellé;Valeur\n" "Période;2024-01\n" "2024-01;100.5\n"
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee("001565530", "2024-03")
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="Target period not found.",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_invalid_data_value(self, mock_get):
        """
        GIVEN a CSV file with invalid data value format
        WHEN getting data without a target period
        THEN unparseable rows are skipped
        """
        csv_content = "Libellé;Valeur\nPériode;2024-01\n2024-01;invalid\n"
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee("001565530")
        assert result == []

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_quarterly_success(self, mock_get):
        """
        GIVEN a successful quarterly INSEE ZIP response
        WHEN getting data with QUARTERLY frequency
        THEN all quarterly observations are returned with the latest first
        """
        csv_content = (
            "Libellé;Valeur;Codes\n" "Période;;\n" "2026-T2;8.3;A\n" "2026-T1;8.1;A\n"
        )
        mock_zip = _create_mock_zip_with_csv("valeurs_trimestrielles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee(
            "001688527",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(period=date(2026, 4, 1), data_value=8.3, comment=""),
            ScrapingResult(period=date(2026, 1, 1), data_value=8.1, comment=""),
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_quarterly_with_target_period(self, mock_get):
        """
        GIVEN a quarterly INSEE ZIP response
        WHEN getting data for a specific YYYY-Tn period
        THEN that quarter's observation should be returned
        """
        csv_content = (
            "Libellé;Valeur;Codes\n" "Période;;\n" "2026-T2;8.3;A\n" "2026-T1;8.1;A\n"
        )
        mock_zip = _create_mock_zip_with_csv("valeurs_trimestrielles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee(
            "001688527",
            "2026-T1",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=date(2026, 1, 1),
                data_value=8.1,
                comment="",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_quarterly_no_csv_file(self, mock_get):
        """
        GIVEN a ZIP without valeurs_trimestrielles when frequency is quarterly
        WHEN getting data
        THEN None values should be returned with error comment
        """
        mock_zip = _create_mock_zip_with_csv(
            "valeurs_mensuelles.csv", "Libellé;Valeur\nPériode;\n2024-01;100.0\n"
        )
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee(
            "001688527",
            frequency=EconomicPublicationFrequencyChoices.QUARTERLY,
        )
        assert result == [
            ScrapingResult(
                period=None,
                data_value=None,
                comment="No 'valeurs_trimestrielles' CSV found in archive.",
            )
        ]

    @patch("economic_overview.services.data_ingestion.requests.get")
    def test_get_data_from_insee_returns_all_economic_data(self, mock_get):
        """
        GIVEN a monthly INSEE ZIP with several periods
        WHEN getting data without a target period
        THEN every parseable economic data row is returned
        """
        csv_content = (
            "Libellé;Valeur\n"
            "Période;\n"
            "2024-03;103.0\n"
            "2024-02;102.0\n"
            "2024-01;101.0\n"
            "2023-12;100.0\n"
        )
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        result = _get_data_from_insee(
            "001565530",
            frequency=EconomicPublicationFrequencyChoices.MONTHLY,
        )
        assert result == [
            ScrapingResult(period=date(2024, 3, 1), data_value=103.0, comment=""),
            ScrapingResult(period=date(2024, 2, 1), data_value=102.0, comment=""),
            ScrapingResult(period=date(2024, 1, 1), data_value=101.0, comment=""),
            ScrapingResult(period=date(2023, 12, 1), data_value=100.0, comment=""),
        ]


class TestParseInseePeriod(TestCase):
    """Test cases for INSEE period parsing."""

    def test_parse_monthly_period(self):
        """
        GIVEN a YYYY-MM monthly period string
        WHEN _parse_insee_period is called with MONTHLY frequency
        THEN the first day of that month is returned
        """
        assert _parse_insee_period(
            "2024-10", EconomicPublicationFrequencyChoices.MONTHLY
        ) == date(2024, 10, 1)

    def test_parse_quarterly_period_french_format(self):
        """
        GIVEN a French T-quarter period string
        WHEN _parse_insee_period is called with QUARTERLY frequency
        THEN the first day of that quarter is returned
        """
        assert _parse_insee_period(
            "2026-T2", EconomicPublicationFrequencyChoices.QUARTERLY
        ) == date(2026, 4, 1)

    def test_parse_quarterly_period_sdmx_format(self):
        """
        GIVEN an SDMX Q-quarter period string
        WHEN _parse_insee_period is called with QUARTERLY frequency
        THEN the first day of that quarter is returned
        """
        assert _parse_insee_period(
            "2026-Q1", EconomicPublicationFrequencyChoices.QUARTERLY
        ) == date(2026, 1, 1)

    def test_parse_annual_period(self):
        """
        GIVEN a YYYY annual period string
        WHEN _parse_insee_period is called with ANNUAL frequency
        THEN January 1 of that year is returned
        """
        assert _parse_insee_period(
            "2025", EconomicPublicationFrequencyChoices.ANNUAL
        ) == date(2025, 1, 1)

    def test_parse_invalid_quarterly_period(self):
        """
        GIVEN a monthly-format string for quarterly frequency
        WHEN _parse_insee_period is called with QUARTERLY frequency
        THEN a ValueError is raised
        """
        with self.assertRaises(ValueError):
            _parse_insee_period(
                "2026-05", EconomicPublicationFrequencyChoices.QUARTERLY
            )
