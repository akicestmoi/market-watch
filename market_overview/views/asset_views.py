import json

from rest_framework import status
from rest_framework.response import Response

import core.services as core_services
import market_overview.services.market_data_services as market_data_services
from core.open_api import (
    ApiTags,
    BadRequestOpenApiResponse,
    OkOpenApiResponse,
    open_api,
)
from core.views import BaseAPIView
from market_overview.models import AssetModel
from market_overview.open_api.request_serializers import (
    BaseAssetSerializer,
    GetAssetNamesSerializer,
)
from market_overview.open_api.response_serializers import (
    AssetResponseSerializer,
    GetAssetNamesResponseSerializer,
)


class GenerateBaseAssetsDataView(BaseAPIView):
    """Generate Base Assets Data APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Generate Base Assets Data",
        description="Generate base assets data from JSON file.",
        error_responses=[BadRequestOpenApiResponse("short_name is required")],
    )
    def post(self, validated_data: dict) -> Response:
        """Generate asset data from market_data.json."""
        with open("market_overview/data_sources/market_data.json") as f:
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
            return Response(
                data={
                    "error_message": f"Duplicate asset short_name found: {duplicates}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for asset in assets_base_info:
            asset_data = {
                **{k: v for k, v in asset.items() if k != "id"},
                "asset_id": asset["id"],
            }
            if "short_name" not in asset_data:
                return Response(
                    data={"error_message": "short_name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            AssetModel.objects.update_or_create(
                short_name=asset_data["short_name"], defaults=asset_data
            )

        return Response(
            data={"message": "Asset data successfully generated."},
            status=status.HTTP_200_OK,
        )


class GetAssetNamesView(BaseAPIView):
    """Get Asset Names APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset Names",
        description="Get all asset names in the database.",
        request_serializer=GetAssetNamesSerializer,
        response=OkOpenApiResponse(GetAssetNamesResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """List all asset names in the database."""
        asset_names = market_data_services.get_asset_names(validated_data)
        return Response(
            data=GetAssetNamesResponseSerializer(asset_names).data,
            status=status.HTTP_200_OK,
        )


class AssetDetailsView(BaseAPIView):
    """Asset Details APIView."""

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Get Asset",
        description="Get an asset.",
        request_serializer=BaseAssetSerializer,
        response=OkOpenApiResponse(AssetResponseSerializer),
    )
    def get(self, validated_data: dict) -> Response:
        """Get an asset."""
        short_name: str = validated_data["short_name"]
        asset = core_services.get(AssetModel, short_name=short_name)
        return Response(
            data=AssetResponseSerializer(asset).data,
            status=status.HTTP_200_OK,
        )

    @open_api(
        tags=[ApiTags.ASSETS],
        summary="Delete Asset",
        description="Delete an asset.",
        request_serializer=BaseAssetSerializer,
    )
    def delete(self, validated_data: dict) -> Response:
        """Delete an asset."""
        short_name: str = validated_data["short_name"]
        asset = core_services.get(AssetModel, short_name=short_name)
        asset.delete()
        return Response(
            data={"message": "Asset deleted successfully."},
            status=status.HTTP_200_OK,
        )
