import io
import zipfile
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from core.tests import MockResponse, read_file_content
from economic_overview.services.data_ingestion_services import (
    ScrapingResult,
    _get_data_from_insee,
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

    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_get_data_from_insee_success_no_target_period(self, mock_get):
        """
        GIVEN a successful INSEE ZIP response with CSV data
        WHEN getting data without target period
        THEN the latest data should be returned
        """
        mock_get.return_value = MockResponse(
            status_code=200, content=self.MOCK_INSEE_SUCCESS_ZIP, text=""
        )

        result = _get_data_from_insee("001565530")
        assert result == ScrapingResult(
            period=date(2025, 11, 1),
            data_value=97.6,
            comment="",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=date(2024, 10, 1),
            data_value=97.0,
            comment="",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_get_data_from_insee_http_error(self, mock_get):
        """
        GIVEN an HTTP error response from INSEE
        WHEN getting data
        THEN None values should be returned with error comment in a ScrapingResult
        """
        mock_get.return_value = MockResponse(status_code=404, content=b"Not Found")

        result = _get_data_from_insee("001565530")
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="Not Found",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="Error reading ZIP content: File is not a zip file",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="No 'valeurs_mensuelles' CSV found in archive.",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="Data is not in the expected format.",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="No data found.",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
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
        assert result == ScrapingResult(
            period=None,
            data_value=None,
            comment="Target period not found.",
        )

    @patch("economic_overview.services.data_ingestion_services.requests.get")
    def test_get_data_from_insee_invalid_data_value(self, mock_get):
        """
        GIVEN a CSV file with invalid data value format
        WHEN getting data
        THEN an error should be raised
        """
        csv_content = "Libellé;Valeur\nPériode;2024-01\n2024-01;invalid\n"
        mock_zip = _create_mock_zip_with_csv("valeurs_mensuelles.csv", csv_content)
        mock_get.return_value = MockResponse(status_code=200, content=mock_zip, text="")

        with self.assertRaises(ValueError):
            _get_data_from_insee("001565530")
