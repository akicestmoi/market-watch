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
    asset_not_updated_holiday = serializers.ListField(child=serializers.CharField())
    date = serializers.DateField()


class BatchPriceIngestionResponseSerializerItem(serializers.Serializer):
    """Batch Price Ingestion Response Serializer Item."""

    short_name = serializers.CharField()
    status = serializers.CharField()
    error = serializers.CharField()
    asset_not_updated = serializers.ListField(child=serializers.CharField())
    asset_not_updated_holiday = serializers.ListField(child=serializers.CharField())


class BatchPriceIngestionResponseSerializer(serializers.Serializer):
    """Batch Price Ingestion Response Serializer."""

    message = serializers.CharField()
    results = serializers.ListField(child=BatchPriceIngestionResponseSerializerItem())


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


class DeleteMarketPricesResponseSerializer(serializers.Serializer):
    """Delete Market Prices Response Serializer."""

    message = serializers.CharField()
    deleted_count = serializers.IntegerField()


class MarkAsHolidayResponseSerializer(serializers.Serializer):
    """Mark As Holiday Response Serializer."""

    message = serializers.CharField()
    updated_count = serializers.IntegerField()
    not_found = serializers.ListField(child=serializers.CharField())
