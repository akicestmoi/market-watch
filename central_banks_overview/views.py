from datetime import date
from typing import List, Optional

from rest_framework import status
from rest_framework.response import Response

import central_banks_overview.services.cb_data_services as cb_data_services
import central_banks_overview.services.cb_inference_services as cb_inference_services
import central_banks_overview.services.cb_meetings_services as cb_meetings_services
import central_banks_overview.services.stir_prices_ingestion_services as stir_futures_services
from central_banks_overview.models import CentralBankChoices
from central_banks_overview.open_api.request_serializers import (
    BulkUpdateStirFuturesPricesSerializer,
    CentralBankDataIngestionItemSerializer,
    CentralBankDataIngestionSerializer,
    CsvBulkUpdateStirFuturesPricesSerializer,
    EstrPriceIngestionViaPdfSerializer,
    GetCentralBankMeetingDatesSerializer,
    GetCentralBankProbabilityMatrixSerializer,
    ListCentralBankDataSerializer,
    ListStirFuturesPricesSerializer,
    StirFuturesPriceIngestionSerializer,
)
from central_banks_overview.open_api.response_serializers import (
    CentralBankDataIngestionResponseSerializer,
    CentralBankDataResponseSerializer,
    CentralBankMeetingDatesResponseSerializer,
    CentralBankProbabilityMatrixResponseSerializer,
    StirFuturesPriceIngestionResponseSerializer,
    StirFuturesPriceResponseSerializer,
)
from central_banks_overview.services.cb_data_services import CentralBankDataDates
from central_banks_overview.services.stir_prices_ingestion_services import (
    BulkUpdateFuturesPricesItem,
)
from core.open_api import ApiTags, CreatedOpenApiResponse, OkOpenApiResponse, open_api
from core.services import logger
from core.views import BaseAPIView


class CentralBankDataIngestionView(BaseAPIView):
    """Central Bank Data Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Data",
        description="Ingest Central Bank Data for a given date.",
        request_serializer=CentralBankDataIngestionSerializer,
        response=CreatedOpenApiResponse(CentralBankDataIngestionResponseSerializer),
    )
    def post(
        self, validated_data: List[CentralBankDataIngestionItemSerializer]
    ) -> Response:
        """Ingest central bank data."""
        requested_central_bank_data_dates: List[CentralBankDataDates] = validated_data  # type: ignore[reportAssignmentType]

        central_bank_data_dates = cb_data_services.get_all_central_bank_data_dates(
            requested_central_bank_data_dates
        )
        central_bank_data_updated = cb_data_services.ingest_central_bank_data(
            central_bank_data_dates
        )
        return Response(
            data=CentralBankDataIngestionResponseSerializer(
                {
                    "message": "Central Bank Data successfully ingested",
                    "updates": central_bank_data_updated,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ListCentralBankDataView(BaseAPIView):
    """List Central Bank Data APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Central Bank Data",
        description="List Central Bank Data for a specific date and central bank.",
        request_serializer=ListCentralBankDataSerializer,
        response=OkOpenApiResponse(CentralBankDataResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List Central Bank Data for a specific date and central bank."""
        target_date: Optional[date] = validated_data.get("date")
        last_value: bool = validated_data.get("last_value", False)
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        central_bank_data = cb_data_services.get_central_bank_data(
            target_date, central_banks, last_value
        )
        return Response(
            data=CentralBankDataResponseSerializer(central_bank_data, many=True).data,
            status=status.HTTP_200_OK,
        )


class StirFuturesPriceIngestionView(BaseAPIView):
    """Stir Futures Price Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Stir Futures Prices",
        description="Ingest Stir Futures Prices for a given date and maturity month.",
        request_serializer=StirFuturesPriceIngestionSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest market prices gathered from various sources."""
        price_date: date = validated_data["date"]

        logger.info(f"Ingesting STIR Futures prices for date: {price_date}")
        stir_futures_prices = stir_futures_services.extract_all_stir_futures_prices(
            price_date
        )
        stir_futures_updated = stir_futures_services.ingest_stir_futures_prices(
            stir_futures_prices
        )
        return Response(
            data=StirFuturesPriceIngestionResponseSerializer(
                {
                    "message": "STIR Futures prices successfully ingested",
                    "stir_futures_updated": [
                        f"{stir_future_price['short_name']}.{stir_future_price['maturity']}"
                        for stir_future_price in stir_futures_updated
                    ],
                    "date": price_date,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class EstrPriceIngestionViaPdfView(BaseAPIView):
    """ESTR Price Ingestion via PDF APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest ESTR Prices via PDF",
        description="Ingest ESTR Prices via PDF for a given date.",
        request_serializer=EstrPriceIngestionViaPdfSerializer,
        response=CreatedOpenApiResponse(StirFuturesPriceIngestionResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Ingest PDF Prices for a given date."""
        pdf_file = validated_data["pdf_file"]
        price_date: date = validated_data["date"]

        estr_prices = stir_futures_services.extract_estr_prices_from_pdf(
            pdf_file.read(), price_date
        )
        stir_futures_updated = stir_futures_services.ingest_stir_futures_prices(
            estr_prices
        )
        return Response(
            data=StirFuturesPriceIngestionResponseSerializer(
                {
                    "message": "STIR Futures prices successfully ingested",
                    "stir_futures_updated": [
                        f"{stir_future_price['short_name']}.{stir_future_price['maturity']}"
                        for stir_future_price in stir_futures_updated
                    ],
                    "date": price_date,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CentralBankMeetingDatesIngestionView(BaseAPIView):
    """Central Bank Meeting Dates Ingestion APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Ingest Central Bank Meeting Dates",
        description="Ingest Central Bank Meeting Dates for a given date.",
        response=CreatedOpenApiResponse(),
    )
    def post(self, validated_data: dict) -> Response:
        """Get Central Bank Meeting Dates for a given date."""
        cb_meetings_services.ingest_central_bank_meeting_dates()
        return Response(
            data={"message": "Central Bank Meeting Dates successfully ingested"},
            status=status.HTTP_201_CREATED,
        )


class ListStirFuturesPricesView(BaseAPIView):
    """List Stir Futures Prices APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="List Stir Futures Prices",
        description="List Stir Futures Prices for a given date.",
        request_serializer=ListStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List Stir Futures Prices for a given date."""
        price_date: date = validated_data["date"]
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        prices = stir_futures_services.get_futures_prices(price_date, central_banks)
        return Response(
            data=StirFuturesPriceResponseSerializer(prices, many=True).data,
            status=status.HTTP_200_OK,
        )


class BulkUpdateStirFuturesPricesView(BaseAPIView):
    """Bulk Update Stir Futures Prices APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Bulk Update Stir Futures Prices",
        description="Bulk update stir futures prices.",
        request_serializer=BulkUpdateStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def patch(self, validated_data: List[BulkUpdateFuturesPricesItem]) -> Response:
        """Bulk update stir futures prices."""
        updates: List[BulkUpdateFuturesPricesItem] = validated_data

        futures_prices = stir_futures_services.bulk_update_futures_prices(updates)
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )


class CsvBulkUpdateStirFuturesPricesView(BaseAPIView):
    """Bulk Update Stir Futures Prices from CSV APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Bulk Update Stir Futures Prices from CSV",
        description="Bulk update stir futures prices from a CSV file.",
        request_serializer=CsvBulkUpdateStirFuturesPricesSerializer,
        response=OkOpenApiResponse(StirFuturesPriceResponseSerializer),
    )
    def post(self, validated_data: dict) -> Response:
        """Bulk update stir futures prices from a CSV file."""
        uploaded_file = validated_data["csv_file"]
        csv_file_bytes = uploaded_file.read()
        futures_prices = stir_futures_services.bulk_update_futures_prices_from_csv(
            csv_file_bytes
        )
        return Response(
            data=StirFuturesPriceResponseSerializer(futures_prices, many=True).data,
            status=status.HTTP_200_OK,
        )


class GetCentralBankMeetingDatesView(BaseAPIView):
    """Get Central Bank Meeting Dates APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Meeting Dates",
        description="Get Central Bank Meeting Dates.",
        request_serializer=GetCentralBankMeetingDatesSerializer,
        response=OkOpenApiResponse(CentralBankMeetingDatesResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get Central Bank Meeting Dates."""
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        meeting_dates = cb_meetings_services.get_central_bank_meeting_dates(
            central_banks
        )
        return Response(
            data=CentralBankMeetingDatesResponseSerializer(
                meeting_dates, many=True
            ).data,
            status=status.HTTP_200_OK,
        )


class GetCentralBankProbabilityMatrixView(BaseAPIView):
    """Get Central Bank Probability Matrix APIView."""

    @open_api(
        tags=[ApiTags.CENTRAL_BANKS],
        summary="Get Central Bank Probability Matrix",
        description="Get Central Bank Probability Matrix.",
        request_serializer=GetCentralBankProbabilityMatrixSerializer,
        response=OkOpenApiResponse(CentralBankProbabilityMatrixResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get Central Bank Probability Matrix."""
        target_date: date = validated_data["date"]
        central_banks_str: Optional[str] = validated_data.get("central_banks")
        central_banks = (
            [CentralBankChoices(cb) for cb in central_banks_str.split(",")]
            if central_banks_str
            else []
        )

        probability_matrices = (
            cb_inference_services.get_central_bank_probability_matrices(
                target_date, central_banks
            )
        )
        return Response(
            data=CentralBankProbabilityMatrixResponseSerializer(
                probability_matrices, many=True
            ).data,
            status=status.HTTP_200_OK,
        )
