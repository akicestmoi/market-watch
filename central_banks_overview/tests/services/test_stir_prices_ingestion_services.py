# from datetime import date

# from django.test import TestCase

# from central_banks_overview.models import (
#     CentralBankChoices,
#     StirFuturesModel,
#     StirFuturesNameChoices,
#     StirFuturesSourceChoices,
# )
# from central_banks_overview.services.stir_prices_ingestion_services import (
#     get_futures_prices,
# )


# class TestStirPricesIngestionServices(TestCase):
#     """Test cases for stir_prices_ingestion_services functions."""

#     def setUp(self):
#         """Set up test fixtures."""
#         self.test_date = date(2024, 1, 15)
#         self.test_date_2 = date(2024, 2, 15)

#         # Create FRB futures prices
#         self.frb_future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.01",
#             first_accrual_date=date(2024, 1, 1),
#             last_accrual_date=date(2024, 1, 31),
#             date=self.test_date,
#             price=95.25,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         # Create ECB futures prices
#         self.ecb_future_1 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.ECB,
#             short_name=StirFuturesNameChoices.ESTR3M,
#             full_name="3 Month ESTR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=96.50,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         # Create another FRB future for different date
#         self.frb_future_2 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date_2,
#             price=95.50,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#     def test_get_futures_prices_with_date(self):
#         """
#         GIVEN futures prices for a specific date
#         WHEN getting futures prices with price_date
#         THEN the correct futures prices for that date are returned
#         """
#         result = get_futures_prices(self.test_date)
#         assert len(result) == 2
#         assert self.frb_future_1 in result
#         assert self.ecb_future_1 in result
#         assert self.frb_future_2 not in result

#     def test_get_futures_prices_with_central_banks_filter(self):
#         """
#         GIVEN futures prices for multiple central banks
#         WHEN getting futures prices with central_banks filter
#         THEN only futures prices for specified central banks are returned
#         """
#         result = get_futures_prices(self.test_date, [CentralBankChoices.FRB])
#         assert len(result) == 1
#         assert self.frb_future_1 in result
#         assert self.ecb_future_1 not in result

#     def test_get_futures_prices_empty(self):
#         """
#         GIVEN no futures prices for a date
#         WHEN getting futures prices for that date
#         THEN an empty list is returned
#         """
#         result = get_futures_prices(date(2025, 1, 1))
#         assert result == []

#     def test_get_futures_prices_multiple_maturities(self):
#         """
#         GIVEN futures prices with multiple maturities for same central bank
#         WHEN getting futures prices
#         THEN all maturities are returned sorted
#         """
#         # Add more FRB futures with different maturities
#         frb_future_3 = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.FRB,
#             short_name=StirFuturesNameChoices.FF1M,
#             full_name="1 Month Fed Funds STIR Futures",
#             maturity="24.03",
#             first_accrual_date=date(2024, 3, 1),
#             last_accrual_date=date(2024, 3, 31),
#             date=self.test_date,
#             price=95.75,
#             source=StirFuturesSourceChoices.YAHOO,
#             comment="",
#         )

#         result = get_futures_prices(self.test_date, [CentralBankChoices.FRB])
#         assert len(result) == 2
#         assert self.frb_future_1 in result
#         assert frb_future_3 in result
#         # Results should be ordered by maturity
#         assert result[0].maturity <= result[1].maturity

#     def test_get_futures_prices_with_none_price(self):
#         """
#         GIVEN futures price with None value
#         WHEN getting futures prices
#         THEN the futures with None price is still returned
#         """
#         future_with_none = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="24.04",
#             first_accrual_date=date(2024, 4, 1),
#             last_accrual_date=date(2024, 4, 30),
#             date=self.test_date,
#             price=None,
#             source=StirFuturesSourceChoices.TFX,
#             comment="No price available",
#         )

#         result = get_futures_prices(self.test_date, [CentralBankChoices.BOJ])
#         assert len(result) == 1
#         assert future_with_none in result
#         assert result[0].price is None

#     def test_get_futures_prices_multiple_central_banks(self):
#         """
#         GIVEN futures prices for multiple central banks
#         WHEN getting futures prices without filter
#         THEN all futures prices are returned
#         """
#         result = get_futures_prices(self.test_date)
#         assert len(result) == 2
#         assert self.frb_future_1 in result
#         assert self.ecb_future_1 in result

#     def test_get_futures_prices_sorted_by_central_bank_and_maturity(self):
#         """
#         GIVEN futures prices for multiple central banks and maturities
#         WHEN getting futures prices
#         THEN results are sorted by central_bank and maturity
#         """
#         # Add BOJ future
#         boj_future = StirFuturesModel.objects.create(
#             central_bank=CentralBankChoices.BOJ,
#             short_name=StirFuturesNameChoices.MUTAN3M,
#             full_name="3 Month Mutan STIR Futures",
#             maturity="24.02",
#             first_accrual_date=date(2024, 2, 1),
#             last_accrual_date=date(2024, 2, 29),
#             date=self.test_date,
#             price=99.50,
#             source=StirFuturesSourceChoices.TFX,
#             comment="",
#         )

#         result = get_futures_prices(self.test_date)
#         assert len(result) == 3

#         # Check ordering: should be by central_bank first, then maturity
#         central_banks = [r.central_bank for r in result]
#         # Should be sorted by central_bank (which is stored as string)
#         assert central_banks == sorted(central_banks)
