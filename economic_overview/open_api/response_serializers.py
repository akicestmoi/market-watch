"""DRF response serializers for economic overview API outputs."""

from rest_framework import serializers

from economic_overview.models import (
    EconomicDataModel,
    EconomicIndicatorInformationModel,
)


class UpdatePublicationScheduleResponseSerializer(serializers.Serializer):
    """Update Publication Schedule Response Serializer."""

    message = serializers.CharField()
    schedule_not_updated = serializers.ListField(child=serializers.CharField())


class LatestEconomicDataIngestionResponseSerializer(serializers.Serializer):
    """Latest Economic Data Ingestion Response Serializer."""

    message = serializers.CharField()
    updated_indicators = serializers.ListField(child=serializers.CharField())
    indicator_not_updated = serializers.ListField(child=serializers.CharField())
    schedule_not_updated = serializers.ListField(child=serializers.CharField())


class SpecificEconomicDataIngestionResponseSerializerItem(serializers.Serializer):
    """Specific Economic Data Ingestion Response Serializer Item."""

    indicator = serializers.CharField()
    period = serializers.CharField()


class SpecificEconomicDataIngestionResponseSerializer(serializers.Serializer):
    """Specific Economic Data Ingestion Response Serializer."""

    message = serializers.CharField()
    indicator_not_updated = serializers.ListField(
        child=SpecificEconomicDataIngestionResponseSerializerItem()
    )


class HistoricalEconomicDataIngestionResponseSerializer(serializers.Serializer):
    """Historical Economic Data Ingestion Response Serializer."""

    message = serializers.CharField()
    updated_indicators = serializers.ListField(child=serializers.CharField())
    indicator_not_updated = serializers.ListField(
        child=SpecificEconomicDataIngestionResponseSerializerItem()
    )


class EconomicIndicatorInformationSerializer(serializers.ModelSerializer):
    """Economic Indicator Information Serializer."""

    class Meta:
        """Economic indicator information serializer metadata."""

        model = EconomicIndicatorInformationModel
        fields = [
            "name",
            "location",
            "category",
            "type",
            "technical_name",
            "frequency",
            "source",
            "ticker",
        ]


class EconomicDataResponseSerializer(serializers.ModelSerializer):
    """Economic Data Response Serializer."""

    indicator = EconomicIndicatorInformationSerializer(read_only=True)
    id = serializers.IntegerField(source="pk", read_only=True)

    class Meta:
        """Economic data response serializer metadata."""

        model = EconomicDataModel
        fields = [
            "id",
            "indicator",
            "period",
            "data_value",
            "comment",
        ]


class DeleteEconomicDataResponseSerializer(serializers.Serializer):
    """Delete Economic Data Response Serializer."""

    message = serializers.CharField()
    deleted_count = serializers.IntegerField()
