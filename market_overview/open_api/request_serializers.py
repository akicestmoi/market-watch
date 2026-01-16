from rest_framework import serializers

from market_overview.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    PriceSourceChoices,
)


class BaseAssetSerializer(serializers.Serializer):
    """Base Asset Serializer."""

    short_name = serializers.CharField()


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


class BatchPriceIngestionItemSerializer(serializers.Serializer):
    """Batch Price Ingestion Item Serializer."""

    short_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        """Validate end_date is greater than start_date."""
        if attrs.get("end_date") and attrs.get("end_date") < attrs.get("start_date"):
            raise serializers.ValidationError(
                "end_date must be greater than or equal to start_date."
            )
        return attrs


class BatchPriceIngestionSerializer(serializers.ListSerializer):
    """Batch Price Ingestion Serializer."""

    child = BatchPriceIngestionItemSerializer()

    def validate(self, attrs):
        """Validate list is not empty."""
        if not attrs:
            raise serializers.ValidationError("List cannot be empty.")
        return attrs


class GetMarketPriceSerializer(serializers.Serializer):
    """Get Market Price Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()


class ListMarketPricesSerializer(serializers.Serializer):
    """List Market Prices Serializer."""

    date = serializers.DateField()


class GetPriceUpdateLogsSerializer(serializers.Serializer):
    """Get Price Update Logs Serializer."""

    price_date = serializers.DateField(required=False)
    short_name = serializers.CharField(required=False)


class GetAssetsWithoutPricesSerializer(serializers.Serializer):
    """Get Assets Without Prices Serializer."""

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    include_holidays = serializers.BooleanField(required=False)


class BulkUpdateAssetsPricesItemSerializer(serializers.Serializer):
    """Bulk Update Assets Prices Item Serializer."""

    short_name = serializers.CharField()
    date = serializers.DateField()
    price = serializers.FloatField()
    logs = serializers.CharField(required=False)


class BulkUpdateAssetsPricesSerializer(serializers.ListSerializer):
    """Bulk Update list-level validation (cross-item checks)."""

    child = BulkUpdateAssetsPricesItemSerializer()


class CsvBulkUpdateAssetsPricesSerializer(serializers.Serializer):
    """Csv Bulk Update Assets Prices Serializer."""

    csv_file = serializers.FileField()


class IngestHolidaysSerializer(serializers.Serializer):
    """Ingest Holidays Serializer."""

    date = serializers.DateField(required=False)
    location = serializers.ChoiceField(choices=LocationChoices.choices, required=False)


class ListHolidaysSerializer(serializers.Serializer):
    """List Holidays Serializer."""

    location = serializers.ChoiceField(choices=LocationChoices.choices, required=False)
    year = serializers.IntegerField(required=False)
    months = serializers.CharField(required=False)

    def validate_months(self, value):
        """Validate months is a valid list of months."""
        if value:
            months = value.split(",")
            for month in months:
                if not month.isdigit() or int(month) < 1 or int(month) > 12:
                    raise serializers.ValidationError("Invalid month.")
        return value


class DeleteHolidaysSerializer(serializers.Serializer):
    """Delete Holidays Serializer."""

    date = serializers.DateField()


class DeleteMarketPricesSerializer(serializers.Serializer):
    """Delete Market Prices Serializer."""

    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    short_names = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate_short_names(self, value):
        """Convert comma-separated string or list to list."""
        if not value:
            return None
        if isinstance(value, list):
            return [name.strip() for name in value if name and name.strip()]
        if isinstance(value, str) and value.strip():
            return [name.strip() for name in value.split(",") if name.strip()]
        return None

    def validate(self, attrs):
        """Validate that at least one parameter is provided."""
        short_names_str = attrs.pop("short_names", None)
        if short_names_str is not None:
            short_names_list = self.validate_short_names(short_names_str)
            if short_names_list:
                attrs["short_names"] = short_names_list

        # Check if at least one parameter is provided
        if not any(
            [
                attrs.get("start_date"),
                attrs.get("end_date"),
                attrs.get("short_names"),
            ]
        ):
            raise serializers.ValidationError(
                "At least one of 'start_date', 'end_date', or 'short_names' must be provided."
            )
        return attrs
