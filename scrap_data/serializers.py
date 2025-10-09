from rest_framework import serializers

from scrap_data.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    SourceChoices,
)


class MarketPriceIngestionSerializer(serializers.Serializer):
    """Market Price Ingestion Serializer."""

    date = serializers.DateField()


class TargetedMarketPriceIngestionSerializer(serializers.Serializer):
    """TargetedMarket Price Ingestion Serializer."""

    short_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)


class CalculatePriceDiffSerializer(serializers.Serializer):
    """Market Price Ingestion Serializer."""

    reference_date = serializers.DateField()
    previous_date = serializers.DateField()


class DataCorrectionSerializer(serializers.Serializer):
    """Data Correction Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()
    logs = serializers.CharField()

    asset_class = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    full_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    price = serializers.FloatField(required=False, allow_null=True)
    maturity = serializers.FloatField(required=False, allow_null=True)
    asset_type = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, data: dict):
        """Validate Serializer."""
        error_messages = {}
        if not data.get("date"):
            error_messages["date"] = "This field is required."
        if not data.get("short_name"):
            error_messages["short_name"] = "This field is required."
        if not data.get("logs"):
            error_messages["logs"] = "This field is required."

        if data.get("asset_class") and data.get("asset_class") not in AssetClassChoices:
            autorized_values = ", ".join([choice.value for choice in AssetClassChoices])
            error_messages["asset_class"] = (
                f"asset_class must be one of the following: {autorized_values}"
            )
        if data.get("location") and data.get("location") not in LocationChoices:
            autorized_values = ", ".join([choice.value for choice in LocationChoices])
            error_messages["location"] = (
                f"location must be one of the following: {autorized_values}"
            )
        if data.get("asset_type") and data.get("asset_type") not in AssetTypeChoices:
            autorized_values = ", ".join([choice.value for choice in AssetTypeChoices])
            error_messages["asset_type"] = (
                f"asset_type must be one of the following: {autorized_values}"
            )
        if data.get("source") and data.get("source") not in SourceChoices:
            autorized_values = ", ".join([choice.value for choice in SourceChoices])
            error_messages["source"] = (
                f"source must be one of the following: {autorized_values}"
            )
        if error_messages:
            raise serializers.ValidationError(error_messages)
        return data
