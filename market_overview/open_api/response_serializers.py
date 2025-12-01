from rest_framework import serializers

from market_overview.models import (
    AssetModel,
    HolidayModel,
    MarketPriceModel,
    PriceUpdateLogModel,
)


class AssetNamesResponseSerializerItem(serializers.Serializer):
    """Asset Names Response Serializer Item."""

    short_name = serializers.CharField()
    full_name = serializers.CharField()


class GetAssetNamesResponseSerializer(serializers.ListSerializer):
    """Get Asset Names Response Serializer."""

    child = AssetNamesResponseSerializerItem()


class MarketPriceIngestionResponseSerializer(serializers.Serializer):
    """Market Price Ingestion Response Serializer."""

    message = serializers.CharField()
    asset_not_updated = serializers.ListField(child=serializers.CharField())
    date = serializers.DateField()


class SpecificAssetMarketPriceIngestionResponseSerializer(serializers.Serializer):
    """Market Price Ingestion Response Serializer."""

    message = serializers.CharField()
    asset_not_updated = serializers.ListField(child=serializers.DateField())


class AssetResponseSerializer(serializers.ModelSerializer):
    """Asset Serializer."""

    class Meta:
        model = AssetModel
        fields = [
            "asset_id",
            "short_name",
            "full_name",
            "asset_class",
            "location",
            "maturity",
            "asset_type",
            "ticker",
            "source",
        ]


class GetAssetWithoutPriceResponseSerializer(serializers.Serializer):
    """Get Asset Without Price Response Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()
    full_name = serializers.CharField()
    maturity = serializers.FloatField()
    comment = serializers.CharField()


class MarketPriceResponseSerializer(serializers.ModelSerializer):
    """Market Price Serializer with Asset information."""

    asset = AssetResponseSerializer(read_only=True)

    class Meta:
        model = MarketPriceModel
        fields = [
            "date",
            "price",
            "comment",
            "asset",
        ]


class PriceUpdateLogResponseSerializer(serializers.ModelSerializer):
    """Price Update Log Response Serializer."""

    class Meta:
        model = PriceUpdateLogModel
        fields = [
            "market_price_id",
            "logs",
        ]


class HolidayResponseSerializer(serializers.ModelSerializer):
    """Holiday Response Serializer."""

    class Meta:
        model = HolidayModel
        fields = [
            "date",
            "name",
            "location",
        ]
