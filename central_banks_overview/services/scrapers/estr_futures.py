"""Parse ESTR 3M futures prices from the ICE settlement PDF."""

from datetime import date, timedelta
from io import BytesIO
from typing import NamedTuple

import pdfplumber
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import BDay

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)
from central_banks_overview.services.config import MONTH_NUMBER_BY_ABBREVIATION
from central_banks_overview.services.scrapers.common import StirFutures


def _parse_maturity_from_estr_pdf(maturity: str) -> str:
    """Parse maturity from ESTR PDF."""
    if len(maturity) < 5:
        raise ValueError(f"Invalid maturity: {maturity}")
    month_str = maturity[:3].lower()
    year_str = maturity[3:]

    month_number = MONTH_NUMBER_BY_ABBREVIATION.get(month_str)
    if month_number is None or not year_str.isdigit():
        raise ValueError(f"Invalid maturity: {maturity}")

    return f"{year_str}.{month_number:02d}"


def _get_third_wednesday_of_month(year: int, month: int) -> date:
    """Get the third Wednesday of a given month."""
    first_day = date(year, month, 1)

    # weekday() returns 0=Monday, 1=Tuesday, 2=Wednesday, etc.
    first_day_weekday = first_day.weekday()

    # Calculate days to add to get to the first Wednesday
    # (2 - weekday) % 7 correctly handles all cases:
    # - If weekday <= 2: gives days to add within the week
    # - If weekday > 2: gives days to add to reach next week's Wednesday
    days_to_first_wednesday = (2 - first_day_weekday) % 7
    first_wednesday = first_day + timedelta(days=days_to_first_wednesday)
    # Third Wednesday is 14 days after the first Wednesday
    third_wednesday = first_wednesday + timedelta(days=14)
    return third_wednesday


class _EstrReferenceDates(NamedTuple):
    """ESTR futures accrual window derived from maturity."""

    start: date
    end: date


def calculate_estr_reference_dates(maturity: str) -> _EstrReferenceDates:
    """Calculate ESTR reference start and end dates from maturity.

    Source: https://www.ice.com/products/82908552/Three-Month-ESTR-Indexed-Future
    """
    try:
        # Parse maturity string "YY.MM" to year and month
        parts = maturity.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid maturity format: {maturity}")

        year_str, month_str = parts
        year = 2000 + int(year_str)
        month = int(month_str)

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month in maturity: {maturity}")

        # Calculate First Accrual Date: Third Wednesday of the delivery month
        first_accrual_date = _get_third_wednesday_of_month(year, month)

        # Calculate Last Accrual Date:
        # Business day prior to the third Wednesday of the third calendar month
        # after the First Accrual Date
        third_month_after = first_accrual_date + relativedelta(months=3)
        third_wednesday_third_month = _get_third_wednesday_of_month(
            third_month_after.year, third_month_after.month
        )
        last_accrual_date = third_wednesday_third_month - BDay(1)

        return _EstrReferenceDates(
            start=first_accrual_date, end=last_accrual_date.date()
        )

    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Failed to calculate reference dates from maturity {maturity}: {e}"
        ) from e


def extract_estr_prices_from_pdf(
    pdf_file: bytes, price_date: date
) -> list[StirFutures]:
    """Extract ESTR Prices from PDF."""
    try:
        tables = []
        with pdfplumber.open(BytesIO(pdf_file)) as pdf_reader:
            for page in pdf_reader.pages:
                tables.extend(page.extract_tables())
    except Exception as e:
        raise ValueError(f"Failed to parse PDF file: {e}") from e

    stir_futures_prices = []
    for table in tables:
        for row in table:
            if len(row) >= 6 and row[0] == "ER3":
                maturity = row[1]
                parsed_maturity = _parse_maturity_from_estr_pdf(maturity)
                closing_price = row[5]
                volume = int(row[8].replace(",", ""))
                first_accrual_date, last_accrual_date = calculate_estr_reference_dates(
                    parsed_maturity
                )

                if (
                    parsed_maturity
                    and closing_price
                    and volume > 1000
                    and last_accrual_date > date.today()
                ):
                    stir_futures_prices.append(
                        StirFutures(
                            central_bank=CentralBankChoices.ECB,
                            short_name=StirFuturesNameChoices.ESTR3M,
                            full_name=str(StirFuturesNameChoices.ESTR3M.label),
                            maturity=parsed_maturity,
                            first_accrual_date=first_accrual_date,
                            last_accrual_date=last_accrual_date,
                            date=price_date,
                            price=float(closing_price),
                            source=StirFuturesSourceChoices.PDF,
                            comment="Prices extracted from PDF file.",
                        )
                    )
    return stir_futures_prices
