from rest_framework import serializers


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
