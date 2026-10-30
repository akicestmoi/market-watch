"""Tests for ESTR PDF scraper."""

from datetime import date

import pytest
from django.test import TestCase
from freezegun import freeze_time

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.scrapers.common import StirFutures
from central_banks_overview.services.scrapers.estr_futures import (
    _get_third_wednesday_of_month,
    calculate_estr_reference_dates,
    extract_estr_prices_from_pdf,
)
from core.conftest import read_file_content


class TestEstrFuturesPricesIngestion(TestCase):
    """Test cases for ingestion functions related to estr futures."""

    MOCK_ESTR_PDF_SUCCESS = read_file_content(
        "central_banks_overview/tests/mock_web_data/estr_stir_futures/success.pdf"
    )

    def test_get_third_wednesday_of_month(self):
        """
        GIVEN a specific month and year
        WHEN getting the third Wednesday
        THEN the correct date is returned
        """
        result = _get_third_wednesday_of_month(2024, 1)
        assert result == date(2024, 1, 17)

    def test_get_third_wednesday_of_month_when_first_day_is_wednesday(self):
        """
        GIVEN a month where the first day is a Wednesday
        WHEN getting the third Wednesday
        THEN the correct date is returned (21st day)
        """
        result = _get_third_wednesday_of_month(2024, 5)  # May 1, 2024 is Wednesday
        assert result == date(2024, 5, 15)

    def test_calculate_estr_reference_dates_valid_maturity(self):
        """
        GIVEN a valid maturity string "24.03"
        WHEN calculating ESTR reference dates
        THEN correct first and last accrual dates are returned
        """
        first_date, last_date = calculate_estr_reference_dates("24.03")
        assert first_date == date(2024, 3, 20)  # Third Wednesday of March 2024
        # Last accrual date: business day prior to third Wednesday of June 2024 (June 19)
        assert last_date == date(
            2024, 6, 18
        )  # June 18, 2024 is a Tuesday (BDay(1) before June 19)

    def test_calculate_estr_reference_dates_invalid_format(self):
        """
        GIVEN an invalid maturity format
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid maturity format"):
            calculate_estr_reference_dates("invalid")

    def test_calculate_estr_reference_dates_invalid_month(self):
        """
        GIVEN a maturity with invalid month
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid month"):
            calculate_estr_reference_dates("24.13")

    def test_calculate_estr_reference_dates_missing_dot(self):
        """
        GIVEN a maturity without a dot separator
        WHEN calculating ESTR reference dates
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError, match="Invalid maturity format"):
            calculate_estr_reference_dates("2403")

    @freeze_time("2025-12-14 12:00:00")
    def test_extract_estr_prices_from_pdf_success(self):
        """
        GIVEN a valid ESTR PDF file
        WHEN extracting ESTR prices from PDF
        THEN list of StirFutures is returned
        """
        target_date = date(2024, 1, 15)
        result = extract_estr_prices_from_pdf(self.MOCK_ESTR_PDF_SUCCESS, target_date)

        assert result == [
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                short_name=StirFuturesNameChoices.ESTR3M,
                full_name="3 Month ESTR Futures",
                maturity="25.09",
                first_accrual_date=date(2025, 9, 17),
                last_accrual_date=date(2025, 12, 16),
                date=date(2024, 1, 15),
                price=98.07,
                source=StirFuturesSourceChoices.PDF,
                comment="Prices extracted from PDF file.",
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2025, 12, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 3, 17),
                maturity="25.12",
                price=98.0675,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 3, 18),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 6, 16),
                maturity="26.03",
                price=98.0875,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 6, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 9, 15),
                maturity="26.06",
                price=98.1125,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 9, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2026, 12, 15),
                maturity="26.09",
                price=98.1025,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2026, 12, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 3, 16),
                maturity="26.12",
                price=98.0575,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 3, 17),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 6, 15),
                maturity="27.03",
                price=97.9975,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 6, 16),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 9, 14),
                maturity="27.06",
                price=97.935,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 9, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2027, 12, 14),
                maturity="27.09",
                price=97.8725,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2027, 12, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 3, 14),
                maturity="27.12",
                price=97.81,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 3, 15),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 6, 20),
                maturity="28.03",
                price=97.7475,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 6, 21),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 9, 19),
                maturity="28.06",
                price=97.6875,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
            StirFutures(
                central_bank=CentralBankChoices.ECB,
                comment="Prices extracted from PDF file.",
                date=date(2024, 1, 15),
                first_accrual_date=date(2028, 9, 20),
                full_name="3 Month ESTR Futures",
                last_accrual_date=date(2028, 12, 19),
                maturity="28.09",
                price=97.63,
                short_name=StirFuturesNameChoices.ESTR3M,
                source=StirFuturesSourceChoices.PDF,
            ),
        ]

    def test_extract_estr_prices_from_pdf_invalid_pdf(self):
        """
        GIVEN an invalid PDF file
        WHEN extracting ESTR prices from PDF
        THEN a ValueError is raised
        """
        invalid_pdf = b"Not a valid PDF"
        target_date = date(2024, 1, 15)

        with pytest.raises(ValueError, match="Failed to parse PDF"):
            extract_estr_prices_from_pdf(invalid_pdf, target_date)

    def test_extract_estr_prices_from_pdf_no_valid_rows(self):
        """
        GIVEN a PDF with no valid ESTR rows
        WHEN extracting ESTR prices from PDF
        THEN an empty list is returned
        """
        # Create a minimal PDF that will parse but has no ER3 data
        # Using a simple PDF structure that pdfplumber can parse
        # but won't contain ER3 rows
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
            b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
            b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n"
            b"/Contents 4 0 R\n>>\nendobj\n"
            b"4 0 obj\n<<\n/Length 44\n>>\nstream\nBT /F1 12 Tf 100 700 Td (No ER3 data) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000206 00000 n \n"
            b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n290\n%%EOF"
        )

        target_date = date(2024, 1, 15)
        result = extract_estr_prices_from_pdf(pdf_content, target_date)

        assert result == []
