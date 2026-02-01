from rest_framework import serializers


class EconomicDataIngestionSerializer(serializers.Serializer):
    """Economic Data Ingestion Serializer."""

    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    update_schedule = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        """Validate end_date is greater than start_date."""
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError(
                "end_date must be greater than start_date."
            )
        return attrs


class UpdatePublicationScheduleSerializer(serializers.Serializer):
    """Update Publication Schedule Serializer."""

    indicator_names = serializers.ListField(
        child=serializers.CharField(), required=False, default=[]
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

    ids = serializers.CharField(required=True)

    def validate_ids(self, value):
        """Convert comma-separated string to list of integers."""
        if not value or not value.strip():
            return None
        try:
            return [
                int(id_str.strip()) for id_str in value.split(",") if id_str.strip()
            ]
        except ValueError:
            raise serializers.ValidationError("IDs must be comma-separated integers.")
