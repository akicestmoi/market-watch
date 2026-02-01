from datetime import date, datetime, timedelta, timezone

from celery import shared_task
from pandas.tseries.offsets import BDay

import central_banks_overview.services.cb_data_services as cb_data_services
import central_banks_overview.services.cb_meetings_services as cb_meetings_services
import central_banks_overview.services.stir_prices_ingestion_services as stir_futures_services
from central_banks_overview.models import CentralBankChoices
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
    try:
        logger.info(f"Ingesting STIR Futures prices for {price_date}")
        stir_futures_prices = stir_futures_services.extract_all_stir_futures_prices(
            price_date
        )
        stir_futures_updated = stir_futures_services.ingest_stir_futures_prices(
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
        stir_futures_services.delete_stir_futures_price_update_logs_before_date(
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
            meeting_date = cb_meetings_services.get_central_bank_next_meeting_date(
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
            stir_futures_services.delete_stir_futures_prices_before_date(
                central_bank, price_date
            )
            cb_data_services.ingest_central_bank_data(
                central_bank=central_bank,
                date_to_ingest=(date.today() - BDay(1)).date(),
            )
            cb_meetings_services.ingest_central_bank_meeting_dates(central_bank)

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
