from datetime import date

from celery import shared_task
from pandas.tseries.offsets import BDay

import central_banks_overview.services.stir_prices_ingestion_services as stir_futures_services
from core.services import logger


@shared_task
def scheduled_stir_prices_ingestion():
    """
    Celery task to ingest STIR Futures prices.
    This task will be scheduled to run twice a day.
    """
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
    if today.month == 1:
        logs_date = date(today.year - 1, 12, 1)
    else:
        logs_date = date(today.year, today.month - 1, 1)
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
