import logging
from datetime import date

from celery import shared_task
from pandas.tseries.offsets import BDay

import market_overview.services as market_overview_services

logger = logging.getLogger(__name__)


@shared_task
def scheduled_market_data_ingestion():
    """
    Celery task to ingest market data.
    This task will be scheduled to run 3 times a day.
    """
    try:
        price_date = date.today() - BDay(1)
        market_data = market_overview_services.get_market_data(price_date)
        asset_not_updated = market_overview_services.ingest_market_data(market_data)

        logger.info(f"Market data ingestion completed for {price_date}")
        return {
            "status": "success",
            "message": f"Market data ingested successfully for {price_date}",
            "date": price_date.isoformat(),
            "asset_not_updated": [data["short_name"] for data in asset_not_updated],
        }

    except Exception as e:
        logger.error(f"Error in market data ingestion task: {str(e)}")
        return {
            "status": "error",
            "message": f"Error: {str(e)}",
            "date": price_date.isoformat(),
        }
