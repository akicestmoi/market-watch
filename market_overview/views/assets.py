"""API views for listing and managing market assets."""

import json
from typing import TypedDict

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

import market_overview.services.market_data as market_data
from core.open_api.schema import (
    ApiTags,
    BadRequestOpenApiResponse,
    NotFoundOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    PriceSourceChoices,
)
from market_overview.open_api.request_serializers import (
    BaseAssetSerializer,
    GetAssetNamesSerializer,
)
from market_overview.open_api.response_serializers import (
    AssetResponseSerializer,
    GetAssetNamesResponseSerializer,
)

MARKET_DATA_JSON = "market_overview/data_sources/market_data.json"


class _AssetJsonRecord(TypedDict):
    """One asset record from 'market_data.json'."""

    id: int
    short_name: str
    asset_class: AssetClassChoices
    location: LocationChoices | None
    full_name: str
    maturity: float | None
    asset_type: AssetTypeChoices
    ticker: str
    source: PriceSourceChoices


class _AssetModelDefaults(TypedDict):
    """ORM defaults for 'AssetModel.update_or_create' from a JSON catalog record."""

    asset_id: int
    asset_class: AssetClassChoices
    location: LocationChoices | None
    full_name: str
    maturity: float | None
    asset_type: AssetTypeChoices
    ticker: str
    source: PriceSourceChoices


_ASSET_JSON_ADAPTER = TypeAdapter(list[_AssetJsonRecord])


class GenerateBaseAssetsDataView(BaseAPIView):
    """Generate Base Assets Data APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Generate Base Assets Data",
        description="Generate base assets data from JSON file.",
        error_responses=[
            BadRequestOpenApiResponse(
                "short_name is required | Duplicate asset short_name found | "
                "Invalid market_data.json"
            )
        ],
    )
    def post(self, _request: Request) -> Response:
        """Generate asset data from 'market_data.json'."""
        with open(MARKET_DATA_JSON) as f:
            raw_payload = json.load(f)
        try:
            asset_json_entries = _ASSET_JSON_ADAPTER.validate_python(raw_payload)
        except PydanticValidationError as exc:
            raise ValidationError(detail=f"Invalid market_data.json: {exc}") from exc

        short_names: set[str] = set()
        duplicates: list[str] = []
        for asset_json_entry in asset_json_entries:
            short_name = asset_json_entry["short_name"]
            if not short_name:
                raise ValidationError(detail="short_name is required")
            if short_name in short_names:
                if short_name not in duplicates:
                    duplicates.append(short_name)
            short_names.add(short_name)
        if duplicates:
            raise ValidationError(
                detail=f"Duplicate asset short_name found: {duplicates}"
            )

        for asset_json_entry in asset_json_entries:
            AssetModel.objects.update_or_create(
                short_name=asset_json_entry["short_name"],
                defaults=_AssetModelDefaults(
                    asset_id=asset_json_entry["id"],
                    asset_class=asset_json_entry["asset_class"],
                    location=asset_json_entry["location"],
                    full_name=asset_json_entry["full_name"],
                    maturity=asset_json_entry["maturity"],
                    asset_type=asset_json_entry["asset_type"],
                    ticker=asset_json_entry["ticker"],
                    source=asset_json_entry["source"],
                ),
            )

        return Response(
            data={"message": "Asset data successfully generated."},
            status=status.HTTP_200_OK,
        )


class _GetAssetNamesValidatedData(TypedDict, total=False):
    """Validated data for 'GetAssetNamesSerializer'."""

    asset_class: AssetClassChoices | None
    asset_type: AssetTypeChoices | None
    location: LocationChoices | None
    source: PriceSourceChoices | None


class GetAssetNamesView(BaseAPIView):
    """Get Asset Names APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset Names",
        description="Get all asset names in the database.",
        request_serializer=GetAssetNamesSerializer,
        response=OkOpenApiResponse(GetAssetNamesResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse(
                "Invalid asset_class, asset_type, location, or source."
            )
        ],
    )
    def get(self, validated_data: _GetAssetNamesValidatedData) -> Response:
        """List all asset names in the database."""
        asset_names = market_data.get_asset_names(validated_data)
        return Response(
            data=GetAssetNamesResponseSerializer(asset_names).data,
            status=status.HTTP_200_OK,
        )


class _BaseAssetValidatedData(TypedDict):
    """Validated data for 'BaseAssetSerializer'."""

    short_name: str


class AssetDetailsView(BaseAPIView):
    """Asset Details APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset",
        description="Get an asset.",
        request_serializer=BaseAssetSerializer,
        response=OkOpenApiResponse(AssetResponseSerializer),
        error_responses=[
            BadRequestOpenApiResponse("short_name is required"),
            NotFoundOpenApiResponse("Asset not found"),
        ],
    )
    def get(self, validated_data: _BaseAssetValidatedData) -> Response:
        """Get an asset."""
        short_name: str = validated_data["short_name"]
        asset = AssetModel.objects.get(short_name=short_name)
        return Response(
            data=AssetResponseSerializer(asset).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Delete Asset",
        description="Delete an asset.",
        request_serializer=BaseAssetSerializer,
        error_responses=[
            BadRequestOpenApiResponse("short_name is required"),
            NotFoundOpenApiResponse("Asset not found"),
        ],
    )
    def delete(self, validated_data: _BaseAssetValidatedData) -> Response:
        """Delete an asset."""
        short_name: str = validated_data["short_name"]
        asset = AssetModel.objects.get(short_name=short_name)
        asset.delete()
        return Response(
            data={"message": "Asset deleted successfully."},
            status=status.HTTP_200_OK,
        )
