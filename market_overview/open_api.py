from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse
from rest_framework import status

from market_overview.serializers import (
    BulkUpdateAssetsFieldsSerializer,
    BulkUpdateAssetsPricesSerializer,
    CalculatePriceDiffSerializer,
    DataCorrectionSerializer,
    MarketPriceIngestionSerializer,
    TargetedMarketPriceIngestionSerializer,
)
from shared.open_api import ApiTags, OpenApiBaseRequest

# Market Data Schemas
INGEST_DATA_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Ingest Market Prices",
    description="Ingest market prices gathered from various sources for a specific date. This endpoint scrapes data from multiple sources and stores it in the database.",
    request=MarketPriceIngestionSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_201_CREATED,
            description="Market prices successfully ingested",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "message": "Market prices successfully ingested",
                        "asset_not_updated": ["DJIA", "ESTR"],
                        "date": "2025-01-15",
                    },
                    response_only=True,
                    status_codes=["201"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid input data",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "error_message": {
                            "date": ["This field is required."],
                        }
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

INGEST_ASSET_DATA_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Ingest Specific Asset Market Prices",
    description="Ingest market prices for a specific asset over a target period. This endpoint scrapes historical data for a single asset.",
    request=TargetedMarketPriceIngestionSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_201_CREATED,
            description="Asset market prices successfully ingested",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "message": "Asset prices successfully ingested",
                        "no_update_dates": ["2025-01-01", "2025-01-02"],
                    },
                    response_only=True,
                    status_codes=["201"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    name="Asset Not Found",
                    value={
                        "error": "Asset 'INVALID_TICKER' does not exist",
                    },
                    response_only=True,
                    status_codes=["400"],
                ),
                OpenApiExample(
                    name="Date Range Error",
                    value={
                        "error": "end_date must be greater than start_date",
                    },
                    response_only=True,
                    status_codes=["400"],
                ),
            ],
        ),
    ],
)

CALCULATE_PRICE_CHANGE_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Calculate Price Changes",
    description="Calculate price changes for all assets between two specified dates. Returns percentage and absolute changes for each asset.",
    request=CalculatePriceDiffSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Price changes calculated successfully",
            examples=[
                OpenApiExample(
                    name="Price Changes Response",
                    value=[
                        {
                            "id": 944,
                            "date_added": "2025-10-18T09:58:18.042265Z",
                            "last_modified": "2025-10-18T09:58:18.042313Z",
                            "date": "2025-10-17",
                            "asset_class": "CRYPTO",
                            "location": None,
                            "short_name": "BTC",
                            "full_name": "BTC-USD Exchange Rate",
                            "price": 106467.7890625,
                            "maturity": None,
                            "asset_type": "CRYPTO_SPOT_RATE",
                            "source": "YAHOO",
                            "id_previous": 878,
                            "date_added_previous": "2025-10-18T09:38:24.940130Z",
                            "last_modified_previous": "2025-10-18T09:56:51.044801Z",
                            "date_previous": "2025-10-16",
                            "asset_class_previous": "CRYPTO",
                            "location_previous": None,
                            "full_name_previous": "BTC-USD Exchange Rate",
                            "price_previous": 108186.0390625,
                            "maturity_previous": None,
                            "asset_type_previous": "CRYPTO_SPOT_RATE",
                            "source_previous": "YAHOO",
                            "price_change": -1718.25,
                            "price_change_pct": -1.588236351834038,
                        },
                    ],
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid input data or no data found for specified dates",
            examples=[
                OpenApiExample(
                    name="No Data Found",
                    value={
                        "error_message": {
                            "reference_date": ["This field is required."],
                            "previous_date": ["This field is required."],
                        }
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_YIELD_CURVE_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Yield Curve",
    description="Retrieve yield curve data for a specific date and location. Returns bond yields across different maturities.",
    parameters=[
        OpenApiParameter(
            name="date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Date for yield curve data (YYYY-MM-DD format)",
            required=True,
        ),
        OpenApiParameter(
            name="location",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Location filter (e.g., US, EU, JP)",
            required=False,
        ),
        OpenApiParameter(
            name="asset_type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Asset type filter (e.g., GOVERNMENT_BOND_RATE, CORPORATE_BOND_RATE)",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Yield curve retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Yield Curve Data",
                    value=[
                        {"maturity": 2.0, "yield": 4.5, "location": "US"},
                        {"maturity": 10.0, "yield": 4.8, "location": "US"},
                        {"maturity": 30.0, "yield": 5.2, "location": "US"},
                    ],
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid parameters",
            examples=[
                OpenApiExample(
                    name="Parameter Error",
                    value={
                        "error": "date parameter is required",
                        "details": "Please provide a valid date in YYYY-MM-DD format",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_ASSET_NAMES_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Asset Names",
    description="Retrieve a list of all asset names in the database with optional filtering by asset class, type, location, or source.",
    parameters=[
        OpenApiParameter(
            name="asset_class",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter by asset class",
            required=False,
        ),
        OpenApiParameter(
            name="asset_type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter by asset type",
            required=False,
        ),
        OpenApiParameter(
            name="location",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter by location",
            required=False,
        ),
        OpenApiParameter(
            name="source",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter by data source",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Asset names retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Asset List",
                    value=[
                        {
                            "short_name": "AAPL",
                            "full_name": "Apple Inc.",
                            "asset_class": "STOCKS",
                            "location": "US",
                        },
                        {
                            "short_name": "BTC",
                            "full_name": "Bitcoin",
                            "asset_class": "CRYPTO",
                            "location": "GLOBAL",
                        },
                    ],
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid query parameters",
            examples=[
                OpenApiExample(
                    name="Parameter Error",
                    value={
                        "error": "Parameters not accepted",
                        "details": "Invalid asset_class value. Valid values are: STOCKS, COMMODITIES, FX, CRYPTO, RATES, CB_RATES, OTHERS",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_HISTORICAL_PRICES_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Historical Prices",
    description="Retrieve historical price data for a specific asset within an optional date range.",
    parameters=[
        OpenApiParameter(
            name="short_name",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Asset short name (e.g., AAPL, BTC, EURUSD)",
            required=True,
        ),
        OpenApiParameter(
            name="start_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Start date for historical data (YYYY-MM-DD format)",
            required=False,
        ),
        OpenApiParameter(
            name="end_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="End date for historical data (YYYY-MM-DD format)",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Historical prices retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Historical Prices",
                    value=[
                        {
                            "price_date": "2024-01-01",
                            "price": 150.0,
                            "short_name": "AAPL",
                        },
                        {
                            "price_date": "2024-01-02",
                            "price": 152.5,
                            "short_name": "AAPL",
                        },
                        {
                            "price_date": "2024-01-03",
                            "price": 148.8,
                            "short_name": "AAPL",
                        },
                    ],
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid parameters",
            examples=[
                OpenApiExample(
                    name="Parameter Error",
                    value={
                        "error": "short_name parameter is required",
                        "details": "Please provide a valid asset short name (e.g., AAPL, BTC, EURUSD)",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_MARKET_PRICE_DATA_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Market Price Data",
    description="Retrieve market price data from the database. Supports two actions: GET (single asset) and LIST (all assets for a date).",
    parameters=[
        OpenApiParameter(
            name="action",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Action to perform: GET for single asset, LIST for all assets",
            required=True,
        ),
        OpenApiParameter(
            name="date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Date for market data (YYYY-MM-DD format)",
            required=True,
        ),
        OpenApiParameter(
            name="short_name",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Asset short name (required when action=GET)",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Market price data retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Market Price Data",
                    value={
                        "date": "2024-01-01",
                        "short_name": "AAPL",
                        "price": 150.0,
                        "asset_class": "STOCKS",
                    },
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid parameters",
            examples=[
                OpenApiExample(
                    name="Parameter Error",
                    value={
                        "error": "action parameter is required",
                        "details": "Please specify 'GET' for single asset or 'LIST' for all assets",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

UPDATE_MARKET_PRICE_DATA_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Update Market Price Data",
    description="Update market price data for a specific asset and date. Creates a log entry for the update.",
    request=DataCorrectionSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Market price data updated successfully",
            examples=[
                OpenApiExample(
                    name="Update Success",
                    value={
                        "date": "2024-01-01",
                        "short_name": "AAPL",
                        "price": 150.0,
                        "logs": "Manual price correction applied",
                    },
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid input data or asset not found",
            examples=[
                OpenApiExample(
                    name="Asset Not Found",
                    value={
                        "error": "asset does not exist in database",
                        "details": "The asset 'INVALID_TICKER' was not found in our database.",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_PRICE_UPDATE_LOGS_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Price Update Logs",
    description="Retrieve price update logs with optional filtering by date and/or asset. Useful for tracking data changes and corrections.",
    parameters=[
        OpenApiParameter(
            name="date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Filter logs by date (YYYY-MM-DD format)",
            required=False,
        ),
        OpenApiParameter(
            name="short_name",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter logs by asset short name",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Price update logs retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Price Update Logs",
                    value=[
                        {
                            "id": 1,
                            "date": "2024-01-01",
                            "short_name": "AAPL",
                            "logs": "Automated price update from Yahoo Finance",
                            "created_at": "2024-01-01T10:00:00Z",
                        },
                        {
                            "id": 2,
                            "date": "2024-01-01",
                            "short_name": "AAPL",
                            "logs": "Manual price correction applied",
                            "created_at": "2024-01-01T15:30:00Z",
                        },
                    ],
                    response_only=True,
                    status_codes=["200"],
                )
            ],
        ),
        OpenApiResponse(
            response=status.HTTP_400_BAD_REQUEST,
            description="Invalid parameters",
            examples=[
                OpenApiExample(
                    name="Parameter Error",
                    value={
                        "error": "Invalid date format",
                        "details": "Please provide date in YYYY-MM-DD format",
                    },
                    response_only=True,
                    status_codes=["400"],
                )
            ],
        ),
    ],
)

GET_ASSETS_WITHOUT_PRICES_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Get Assets Without Prices",
    description="Retrieve a list of all assets that do not have prices in the database.",
    parameters=[
        OpenApiParameter(
            name="price_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Filter assets by date (YYYY-MM-DD format)",
            required=False,
        ),
    ],
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Assets without prices retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Assets Without Prices",
                    value=[
                        {
                            "id": 634,
                            "date_added": "2025-10-14T19:11:06.239927Z",
                            "last_modified": "2025-10-14T19:11:06.239927Z",
                            "date": "2025-10-13",
                            "asset_class": "RATES",
                            "location": "US",
                            "short_name": "UST2M",
                            "full_name": "US TBills 2 Month",
                            "price": None,
                            "maturity": 0.166,
                            "asset_type": "GOVERNMENT_BOND_RATE",
                            "source": "GOV_TREASURY_DEPT",
                        },
                    ],
                ),
            ],
        ),
    ],
)

BULK_UPDATE_ASSETS_PRICES_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Bulk Update Assets Prices",
    description="Bulk update assets prices.",
    request=BulkUpdateAssetsPricesSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Assets prices updated successfully",
            examples=[
                OpenApiExample(
                    name="Updated Assets",
                    value=[
                        {
                            "id": 634,
                            "date_added": "2025-10-14T19:11:06.239927Z",
                            "last_modified": "2025-10-14T19:11:06.239927Z",
                            "date": "2025-10-13",
                            "asset_class": "RATES",
                            "location": "US",
                            "short_name": "UST2M",
                            "full_name": "US TBills 2 Month",
                            "price": 4.1,
                            "maturity": 0.166,
                            "asset_type": "GOVERNMENT_BOND_RATE",
                            "source": "GOV_TREASURY_DEPT",
                        },
                    ],
                ),
                OpenApiResponse(
                    response=status.HTTP_400_BAD_REQUEST,
                    description="Invalid input data",
                    examples=[
                        OpenApiExample(
                            name="Validation Error",
                            value={
                                "error_message": {
                                    "date": ["This field is required."],
                                }
                            },
                            response_only=True,
                            status_codes=["400"],
                        )
                    ],
                ),
            ],
        ),
    ],
)

BULK_UPDATE_ASSETS_FIELDS_SCHEMA = OpenApiBaseRequest(
    tags=[ApiTags.MARKET_DATA],
    summary="Bulk Update Assets Fields",
    description="Bulk update assets fields.",
    request=BulkUpdateAssetsFieldsSerializer,
    responses=[
        OpenApiResponse(
            response=status.HTTP_200_OK,
            description="Assets fields updated successfully",
            examples=[
                OpenApiExample(
                    name="Updated Assets",
                    value=[
                        {
                            "id": 634,
                            "date_added": "2025-10-14T19:11:06.239927Z",
                            "last_modified": "2025-10-14T19:11:06.239927Z",
                            "date": "2025-10-13",
                            "asset_class": "RATES",
                            "location": "US",
                            "short_name": "UST2M",
                            "full_name": "US TBills 2 Month",
                            "price": 4.1,
                            "maturity": 0.166,
                            "asset_type": "GOVERNMENT_BOND_RATE",
                            "source": "GOV_TREASURY_DEPT",
                        },
                    ],
                ),
                OpenApiResponse(
                    response=status.HTTP_400_BAD_REQUEST,
                    description="Invalid input data",
                    examples=[
                        OpenApiExample(
                            name="Validation Error",
                            value={
                                "error_message": {
                                    "short_name": ["This field is required."],
                                }
                            },
                            response_only=True,
                            status_codes=["400"],
                        )
                    ],
                ),
            ],
        ),
    ],
)
