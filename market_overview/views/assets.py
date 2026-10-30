"""API views for listing and managing market assets."""

import json
from typing import TypedDict

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


class GenerateBaseAssetsDataView(BaseAPIView):
    """Generate Base Assets Data APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Generate Base Assets Data",
        description="Generate base assets data from JSON file.",
        error_responses=[BadRequestOpenApiResponse("short_name is required")],
    )
    def post(self, _request: Request) -> Response:
        """Generate asset data from market_data.json."""
        with open(MARKET_DATA_JSON) as f:
            assets_base_info = json.load(f)

        short_names = set()
        duplicates = []
        for asset in assets_base_info:
            short_name = asset.get("short_name")
            if short_name:
                if short_name in short_names:
                    if short_name not in duplicates:
                        duplicates.append(short_name)
                short_names.add(short_name)
        if duplicates:
            raise ValidationError(
                detail=f"Duplicate asset short_name found: {duplicates}"
            )

        for asset in assets_base_info:
            asset_data = {
                **{k: v for k, v in asset.items() if k != "id"},
                "asset_id": asset["id"],
            }
            if "short_name" not in asset_data:
                raise ValidationError(detail="short_name is required")
            AssetModel.objects.update_or_create(
                short_name=asset_data["short_name"], defaults=asset_data
            )

        return Response(
            data={"message": "Asset data successfully generated."},
            status=status.HTTP_200_OK,
        )


class _GetAssetNamesValidatedData(TypedDict, total=False):
    """Validated data for ``GetAssetNamesSerializer``."""

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
    """Validated data for ``BaseAssetSerializer``."""

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
