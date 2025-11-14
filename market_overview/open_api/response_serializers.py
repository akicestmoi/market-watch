from rest_framework import serializers

from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
    PriceSourceChoices,
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


class CalculatePriceChangeResponseSerializer(serializers.Serializer):
    """Calculate Price Change Response Serializer."""

    asset_id = serializers.IntegerField()
    asset_class = serializers.ChoiceField(choices=AssetClassChoices.choices)
    short_name = serializers.CharField()
    full_name = serializers.CharField()
    maturity = serializers.FloatField(required=False, allow_null=True)
    asset_type = serializers.ChoiceField(choices=AssetTypeChoices.choices)
    source = serializers.ChoiceField(choices=PriceSourceChoices.choices)
    location = serializers.ChoiceField(
        choices=LocationChoices.choices, required=False, allow_null=True
    )
    price = serializers.FloatField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_null=True)
    price_previous = serializers.FloatField(required=False, allow_null=True)
    comment_previous = serializers.CharField(required=False, allow_null=True)
    price_change = serializers.FloatField(required=False, allow_null=True)
    price_change_pct = serializers.FloatField(required=False, allow_null=True)


class GetHistoricalPriceResponseSerializer(serializers.Serializer):
    """Get Historical Price Response Serializer."""

    price_date = serializers.DateField()
    price = serializers.FloatField(required=False, allow_null=True)


class GetYieldCurveResponseSerializer(serializers.Serializer):
    """Get Yield Curve Response Serializer."""

    maturity = serializers.FloatField(required=False, allow_null=True)
    price = serializers.FloatField(required=False, allow_null=True)
    short_name = serializers.CharField()


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

    id = serializers.IntegerField()
    date = serializers.DateField()
    short_name = serializers.CharField()
    full_name = serializers.CharField()
    maturity = serializers.FloatField()
    comment = serializers.CharField()


class MarketPriceResponseSerializer(serializers.Serializer):
    """Market Price Serializer with Asset information."""

    asset = AssetResponseSerializer(read_only=True)

    class Meta:
        model = MarketPriceModel
        fields = [
            "id",
            "date",
            "price",
            "comment",
            "date_added",
            "last_modified",
            "asset",
        ]


class PriceUpdateLogResponseSerializer(serializers.ModelSerializer):
    """Price Update Log Response Serializer."""

    class Meta:
        model = PriceUpdateLogModel
        fields = [
            "id",
            "market_price_id",
            "date_added",
            "last_modified",
            "logs",
        ]
