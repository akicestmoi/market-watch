from rest_framework import serializers

from economic_overview.models import (
    EconomicDataModel,
    EconomicIndicatorInformationModel,
)


class UpdatePublicationScheduleResponseSerializer(serializers.Serializer):
    """Update Publication Schedule Response Serializer."""

    message = serializers.CharField()
    schedule_not_updated = serializers.ListField(child=serializers.CharField())


class EconomicDataIngestionResponseSerializer(serializers.Serializer):
    """Economic Data Ingestion Response Serializer."""

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


class EconomicIndicatorInformationSerializer(serializers.ModelSerializer):
    """Economic Indicator Information Serializer."""

    class Meta:
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

    class Meta:
        model = EconomicDataModel
        fields = [
            "indicator",
            "period",
            "data_value",
            "comment",
        ]
