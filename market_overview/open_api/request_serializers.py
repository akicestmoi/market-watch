"""DRF request serializers for market overview API inputs."""

from rest_framework import serializers

from core.open_api.fields import CommaSeparatedIntegerField
from market_overview.models.common import EquityIndexChoices, LocationChoices
from market_overview.models.market_prices import (
    AssetClassChoices,
    AssetTypeChoices,
    PriceSourceChoices,
)


class MonthListField(CommaSeparatedIntegerField):
    """CSV of calendar months (1–12) with a month-specific error message."""

    def to_internal_value(self, data) -> list[int] | None:
        """Validate month tokens; map integer errors to 'Invalid month.'."""
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError as exc:
            messages = exc.detail if isinstance(exc.detail, list) else [exc.detail]
            if any("integer" in str(message).lower() for message in messages):
                raise serializers.ValidationError("Invalid month.") from exc
            raise


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
    logs = serializers.CharField(required=False, allow_null=True, allow_blank=True)


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
    months = MonthListField(
        required=False,
        allow_blank=True,
        allow_null=True,
        min_value=1,
        max_value=12,
    )


class DeleteHolidaysSerializer(serializers.Serializer):
    """Delete Holidays Serializer."""

    date = serializers.DateField()


class DeleteMarketPricesSerializer(serializers.Serializer):
    """Delete Market Prices Serializer."""

    ids = CommaSeparatedIntegerField(required=False, allow_blank=True, allow_null=True)


class MarkAsHolidayItemSerializer(serializers.Serializer):
    """Mark As Holiday Item Serializer."""

    short_name = serializers.CharField(required=True)
    date = serializers.DateField(required=True)


class MarkAsHolidaySerializer(serializers.ListSerializer):
    """Mark As Holiday Serializer - list of short_name and date pairs."""

    child = MarkAsHolidayItemSerializer()

    def validate(self, attrs):
        """Validate list is not empty."""
        if not attrs:
            raise serializers.ValidationError("List cannot be empty.")
        return attrs


class IngestSectorAnalysisSerializer(serializers.Serializer):
    """Ingest sector-analysis subsector day moves for a date window."""

    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    equity_index = serializers.ChoiceField(
        choices=EquityIndexChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        """Validate end_date is greater than or equal to start_date."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                "end_date must be greater than or equal to start_date."
            )
        return attrs


# Usage of tuple: DRF ChoiceField choices are (stored value, display label) pairs.
_SECTOR_ANALYSIS_LOCATION_CHOICES = [
    (LocationChoices.US.value, LocationChoices.US.label),
    (LocationChoices.FR.value, LocationChoices.FR.label),
    (LocationChoices.JP.value, LocationChoices.JP.label),
]


class GetSectorAnalysisSerializer(serializers.Serializer):
    """Get stored subsector day moves for one region and trading day."""

    date = serializers.DateField(required=True)
    location = serializers.ChoiceField(
        choices=_SECTOR_ANALYSIS_LOCATION_CHOICES,
        required=True,
    )


class IngestEarningsWatchlistSerializer(serializers.Serializer):
    """Ingest earnings watchlist: update, refresh weights, and T+1 roll."""

    equity_index = serializers.ChoiceField(
        choices=EquityIndexChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class RefreshEarningsWatchlistSerializer(serializers.Serializer):
    """Refresh earnings watchlist: update upcoming and weights (no roll)."""

    as_of = serializers.DateField(required=False)
    equity_index = serializers.ChoiceField(
        choices=EquityIndexChoices.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class GetEarningsWatchlistSerializer(serializers.Serializer):
    """Get stored earnings watchlist companies for one region."""

    location = serializers.ChoiceField(
        choices=_SECTOR_ANALYSIS_LOCATION_CHOICES,
        required=True,
    )
