from datetime import date

from celery import shared_task

import economic_overview.services.data_ingestion_services as data_ingestion_services
import economic_overview.services.economic_data_services as economic_data_services
import economic_overview.services.publication_services as publication_services
from core.services import logger


@shared_task
def scheduled_economic_data_and_schedule_update():
    """
    Celery task to ingest economic data and update schedules.
    This task will be scheduled to run daily.
    """
    today = date.today()
    try:
        economic_indicators_to_update = (
            economic_data_services.get_economic_indicators_to_update(
                end_date=today,
            )
        )
        if not economic_indicators_to_update.exists():
            logger.info(f"No economic indicators to update found for {today}")
            return {
                "status": "success",
                "message": "No economic indicators to update found.",
                "date": today.isoformat(),
            }

        logger.info(f"Ingesting economic data for {today}")
        data_ingestion_services.ingest_economic_data(economic_indicators_to_update)
        logger.info("Updating publication schedules.")
        publication_services.update_publication_schedules(economic_indicators_to_update)
        return {
            "status": "success",
            "message": "Economic data ingested successfully.",
            "date": today.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in economic data ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": today.isoformat(),
        }


@shared_task
def scheduled_economic_data_update_logs_cleanup():
    """
    Celery task to clean up economic data update logs.
    This task will be scheduled to run daily.
    """
    today = date.today()
    if today.month == 1:
        logs_date = date(today.year - 1, 12, 1)
    else:
        logs_date = date(today.year, today.month - 1, 1)
    try:
        logger.info(f"Cleaning up economic data update logs for {logs_date}")
        economic_data_services.delete_economic_data_update_logs_before_date(logs_date)
        return {
            "status": "success",
            "message": f"Economic data update logs deleted successfully for {logs_date}",
            "date": logs_date.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in economic data update logs cleanup task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": logs_date.isoformat(),
        }
