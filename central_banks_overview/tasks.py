"""Celery tasks for STIR prices, CB data, and meetings ingestion."""

from datetime import date, datetime, timedelta, timezone

from celery import shared_task
from pandas.tseries.offsets import BDay

import central_banks_overview.services.central_banks_data as central_banks_data
import central_banks_overview.services.central_banks_meetings as central_banks_meetings
import central_banks_overview.services.stir_prices_ingestion as stir_prices_ingestion
from central_banks_overview.models import CentralBankChoices
from core.locks import release_redis_lock, try_acquire_redis_lock
from core.services import logger


@shared_task
def scheduled_stir_prices_ingestion(two_bdays_ago: bool = False):
    """
    Celery task to ingest STIR Futures prices.
    This task will be scheduled to run twice a day.
    """
    match two_bdays_ago:
        case True:
            price_date = (date.today() - BDay(2)).date()
        case False:
            price_date = (date.today() - BDay(1)).date()

    lock_key = stir_prices_ingestion.get_stir_price_ingestion_lock_key(price_date)
    lock = try_acquire_redis_lock(lock_key)
    if lock is None:
        logger.warning(
            "Skipping STIR Futures prices ingestion for %s: already in progress.",
            price_date.isoformat(),
        )
        return {
            "status": "skipped",
            "message": (
                "STIR Futures prices ingestion already in progress for "
                f"{price_date.isoformat()}"
            ),
            "date": price_date.isoformat(),
        }

    try:
        logger.info(f"Ingesting STIR Futures prices for {price_date}")
        stir_futures_prices = stir_prices_ingestion.extract_all_stir_futures_prices(
            price_date
        )
        stir_futures_updated = stir_prices_ingestion.ingest_stir_futures_prices(
            stir_futures_prices
        )
        return {
            "status": "success",
            "message": f"STIR Futures prices successfully ingested for {price_date}",
            "stir_futures_updated": [
                f"{stir_future_price['short_name']}.{stir_future_price['maturity']}"
                for stir_future_price in stir_futures_updated
            ],
            "date": price_date.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in STIR Futures prices ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": price_date.isoformat(),
        }
    finally:
        release_redis_lock(lock, lock_key)


@shared_task
def scheduled_stir_futures_price_update_logs_cleanup():
    """
    Celery task to clean up stir futures price update logs.
    This task will be scheduled to run daily.
    """
    today = date.today()
    logs_date = (
        date(today.year - 1, 12, 1)
        if today.month == 1
        else date(today.year, today.month - 1, 1)
    )
    try:
        logger.info(f"Cleaning up stir futures price update logs for {logs_date}")
        stir_prices_ingestion.delete_stir_futures_price_update_logs_before_date(
            logs_date
        )
        return {
            "status": "success",
            "message": f"Stir futures price update logs deleted successfully for {logs_date}",
            "date": logs_date.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in stir futures price update logs cleanup task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": logs_date.isoformat(),
        }


@shared_task
def scheduled_update_cb_info_and_stir_futures_prices_cleanup_after_meetings():
    """
    Celery task to update central bank meetings and stir futures prices.
    This task will be scheduled to run daily.
    """
    DAYS_TO_KEEP = 7
    results = []
    try:
        for central_bank in CentralBankChoices:
            logger.info(f"Checking Central Bank: {central_bank.label}")
            meeting_date = central_banks_meetings.get_central_bank_next_meeting_date(
                central_bank
            )
            if not meeting_date or meeting_date >= datetime.now(timezone.utc):
                logger.info(
                    f"No central bank meeting date found for Central Bank: {central_bank.label}. Skipping cleanup."
                )
                continue

            price_date = date.today() - timedelta(days=DAYS_TO_KEEP)
            results.append(f"{central_bank.value} - {price_date.isoformat()}")
            logger.info(
                f"Cleaning up stir futures prices for Central Bank: {central_bank.label} on {price_date}"
            )
            stir_prices_ingestion.delete_stir_futures_prices_before_date(
                central_bank, price_date
            )
            cb_data_date = (date.today() - BDay(1)).date()
            cb_lock_key = central_banks_data.get_cb_data_ingestion_lock_key(
                central_bank, cb_data_date
            )
            cb_lock = try_acquire_redis_lock(cb_lock_key)
            if cb_lock is None:
                logger.warning(
                    "Skipping CB data ingestion for %s on %s: already in progress.",
                    central_bank.value,
                    cb_data_date.isoformat(),
                )
            else:
                try:
                    central_banks_data.ingest_central_bank_data(
                        central_bank=central_bank,
                        date_to_ingest=cb_data_date,
                    )
                finally:
                    release_redis_lock(cb_lock, cb_lock_key)
            central_banks_meetings.ingest_central_bank_meeting_dates(central_bank)

        return {
            "status": "success",
            "message": (
                "No central bank meetings to update"
                if not results
                else f"Central bank meetings updated successfully for {results}"
            ),
        }
    except Exception as e:
        logger.error(f"Error in stir futures prices cleanup task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
        }
