"""Shared STIR futures price record produced by every futures scraper."""

from datetime import date
from typing import TypedDict

from central_banks_overview.models import (
    CentralBankChoices,
    StirFuturesNameChoices,
    StirFuturesSourceChoices,
)


class StirFutures(TypedDict):
    """Stir Futures Information."""

    central_bank: CentralBankChoices
    short_name: StirFuturesNameChoices
    full_name: str
    maturity: str
    first_accrual_date: date | None
    last_accrual_date: date | None
    date: date
    price: float | None
    source: StirFuturesSourceChoices
    comment: str | None
