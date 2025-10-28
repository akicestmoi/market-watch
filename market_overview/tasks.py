from datetime import date

from celery import shared_task
from pandas.tseries.offsets import BDay

import market_overview.services.price_ingestion_services as price_ingestion_services
from core.services import logger


@shared_task
def scheduled_market_data_ingestion():
    """
    Celery task to ingest market data.
    This task will be scheduled to run 3 times a day.
    """
    price_date = (date.today() - BDay(1)).date()
    try:
        logger.info(f"Ingesting market data for {price_date}")
        market_data = price_ingestion_services.get_market_data(price_date)
        asset_not_updated = price_ingestion_services.ingest_market_data(market_data)
        return {
            "status": "success",
            "message": f"Market data ingested successfully for {price_date}",
            "date": price_date.isoformat(),
            "asset_not_updated": [
                data["asset"].short_name for data in asset_not_updated
            ],
        }

    except Exception as e:
        logger.error(f"Error in market data ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": price_date.isoformat(),
        }
