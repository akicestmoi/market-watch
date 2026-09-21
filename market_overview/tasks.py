from datetime import date, timedelta

from celery import shared_task
from pandas.tseries.offsets import BDay

import market_overview.services.holiday_services as holiday_services
import market_overview.services.market_data_services as market_data_services
import market_overview.services.price_ingestion_services as price_ingestion_services
from core.locks import try_acquire_redis_lock
from core.services import logger
from market_overview.services.holiday_services import HOLIDAY_COUNTRIES


@shared_task
def scheduled_market_data_ingestion(two_bdays_ago: bool = False):
    """
    Celery task to ingest market data.
    This task will be scheduled to run 3 times a day.
    """
    match two_bdays_ago:
        case True:
            price_date = (date.today() - BDay(2)).date()
        case False:
            price_date = (date.today() - BDay(1)).date()

    lock_key = price_ingestion_services.market_price_ingestion_lock_key(price_date)
    lock = try_acquire_redis_lock(lock_key)
    if lock is None:
        logger.warning(
            "Skipping market data ingestion for %s: already in progress.",
            price_date.isoformat(),
        )
        return {
            "status": "skipped",
            "message": (
                f"Market data ingestion already in progress for {price_date.isoformat()}"
            ),
            "date": price_date.isoformat(),
        }

    try:
        logger.info(f"Ingesting market data for {price_date}")
        market_data = price_ingestion_services.get_market_data(price_date)
        ingestion_result = price_ingestion_services.ingest_market_data(market_data)
        return {
            "status": "success",
            "message": f"Market data ingested successfully for {price_date}",
            "date": price_date.isoformat(),
            "asset_not_updated": ingestion_result["asset_not_updated"],
            "asset_not_updated_holiday": ingestion_result["asset_not_updated_holiday"],
        }

    except Exception as e:
        logger.error(f"Error in market data ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": price_date.isoformat(),
        }
    finally:
        try:
            lock.release()
        except Exception:
            logger.warning(
                "Could not release market price ingestion lock for %s",
                price_date.isoformat(),
            )


@shared_task
def scheduled_price_update_logs_cleanup():
    """
    Celery task to clean up price update logs.
    This task will be scheduled to run daily.
    """
    today = date.today()
    logs_date = (
        date(today.year - 1, 12, 1)
        if today.month == 1
        else date(today.year, today.month - 1, 1)
    )
    try:
        logger.info(f"Cleaning up price update logs for {logs_date}")
        market_data_services.delete_price_update_logs_before_date(logs_date)
        return {
            "status": "success",
            "message": f"Price update logs deleted successfully for {logs_date}",
            "date": logs_date.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in price update logs cleanup task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": logs_date.isoformat(),
        }


@shared_task
def scheduled_holidays_ingestion():
    """
    Celery task to ingest holidays.
    This task will be scheduled to run monthly.
    """
    today = date.today()
    before_date = today - timedelta(days=30)
    try:
        for country in HOLIDAY_COUNTRIES:
            holiday_services.ingest_one_year_holidays(today, country)
        holiday_services.delete_holidays_before_date(before_date)
        return {
            "status": "success",
            "message": "Holidays successfully ingested.",
        }
    except Exception as e:
        logger.error(f"Error in holidays ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
        }
