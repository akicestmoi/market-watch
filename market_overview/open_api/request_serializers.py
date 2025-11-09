from rest_framework import serializers

from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    PriceSourceChoices,
)


class GetAssetNamesSerializer(serializers.Serializer):
    """Get Asset Names Serializer."""

    asset_class = serializers.ChoiceField(
        choices=AssetClassChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    asset_type = serializers.ChoiceField(
        choices=AssetTypeChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    location = serializers.ChoiceField(
        choices=LocationChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    source = serializers.ChoiceField(
        choices=PriceSourceChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class MarketPriceIngestionSerializer(serializers.Serializer):
    """Market Price Ingestion Serializer."""

    date = serializers.DateField()


class SpecificAssetMarketPriceIngestionSerializer(serializers.Serializer):
    """Specific Asset Market Price Ingestion Serializer."""

    short_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        """Validate end_date is greater than start_date."""
        if attrs.get("end_date") <= attrs.get("start_date"):
            raise serializers.ValidationError(
                "end_date must be greater than start_date."
            )
        return attrs


class CalculatePriceDiffSerializer(serializers.Serializer):
    """Calculate Price Diff Serializer."""

    reference_date = serializers.DateField()
    previous_date = serializers.DateField()

    def validate(self, attrs):
        """Validate that reference_date is greater than previous_date."""
        if attrs.get("reference_date") <= attrs.get("previous_date"):
            raise serializers.ValidationError(
                "reference_date must be greater than previous_date."
            )
        return attrs


class GetMarketPriceSerializer(serializers.Serializer):
    """Get Market Price Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()


class ListMarketPricesSerializer(serializers.Serializer):
    """List Market Prices Serializer."""

    date = serializers.DateField()


class GetHistoricalPricesSerializer(serializers.Serializer):
    """Get Historical Prices Serializer."""

    short_name = serializers.CharField()
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        """Validate that end_date is greater than start_date."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                "end_date must be greater than start_date"
            )
        return attrs


class GetYieldCurveSerializer(serializers.Serializer):
    """Get Yield Curve Serializer."""

    date = serializers.DateField()
    location = serializers.ChoiceField(choices=LocationChoices.choices)


class GetPriceUpdateLogsSerializer(serializers.Serializer):
    """Get Price Update Logs Serializer."""

    price_date = serializers.DateField(required=False)
    short_name = serializers.CharField(required=False)


class GetAssetsWithoutPricesSerializer(serializers.Serializer):
    """Get Assets Without Prices Serializer."""

    price_date = serializers.DateField(required=False)


class BulkUpdateAssetsPricesItemSerializer(serializers.Serializer):
    """Bulk Update Assets Prices Item Serializer."""

    short_name = serializers.CharField()
    date = serializers.DateField()
    price = serializers.FloatField()
    logs = serializers.CharField(required=False)


class BulkUpdateAssetsPricesSerializer(serializers.ListSerializer):
    """Bulk Update list-level validation (cross-item checks)."""

    child = BulkUpdateAssetsPricesItemSerializer()
