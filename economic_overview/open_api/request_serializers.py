"""DRF request serializers for economic overview API inputs."""

from rest_framework import serializers

from core.open_api.fields import CommaSeparatedIntegerField


class LatestEconomicDataIngestionSerializer(serializers.Serializer):
    """Latest Economic Data Ingestion Serializer."""

    update_schedule = serializers.BooleanField(required=False, default=True)


class HistoricalEconomicDataIngestionSerializer(serializers.Serializer):
    """Historical Economic Data Ingestion Serializer."""

    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    indicators = serializers.ListField(
        child=serializers.CharField(), required=False, default=[]
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


class UpdatePublicationScheduleSerializer(serializers.Serializer):
    """Update Publication Schedule Serializer."""

    indicator_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[],
        help_text="Indicator names to update. Omit or pass [] to update all.",
    )


class SpecificEconomicDataIngestionSerializerItem(serializers.Serializer):
    """Specific Economic Data Ingestion Serializer Item."""

    indicator_name = serializers.CharField(required=True)
    periods = serializers.ListField(child=serializers.CharField(), required=True)


class SpecificEconomicDataIngestionSerializer(serializers.ListSerializer):
    """Specific Economic Data Ingestion Serializer."""

    child = SpecificEconomicDataIngestionSerializerItem()


class ListEconomicDataSerializer(serializers.Serializer):
    """List Economic Data Serializer."""

    indicator_names = serializers.ListField(
        child=serializers.CharField(), required=False, default=[]
    )
    period = serializers.CharField(required=False)


class DeleteEconomicDataSerializer(serializers.Serializer):
    """Delete Economic Data Serializer."""

    ids = CommaSeparatedIntegerField(required=True)
