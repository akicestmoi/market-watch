"""DRF response serializers for economic overview API outputs."""

from rest_framework import serializers

from economic_overview.models.economic_indicators import (
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


class TradeRankingLocationResultSerializer(serializers.Serializer):
    """One location result inside a trade ranking ingest report."""

    location = serializers.CharField()
    trade_type = serializers.CharField()
    status = serializers.CharField()
    upserted_count = serializers.IntegerField()
    message = serializers.CharField()


class TradeRankingIngestionResponseSerializer(serializers.Serializer):
    """Trade ranking ingest report."""

    as_of = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    results = TradeRankingLocationResultSerializer(many=True)


class IndustryProfitabilityLocationResultSerializer(serializers.Serializer):
    """One location result inside an industry profitability ingest report."""

    location = serializers.CharField()
    status = serializers.CharField()
    upserted_count = serializers.IntegerField()
    message = serializers.CharField()


class IndustryProfitabilityIngestionResponseSerializer(serializers.Serializer):
    """Industry profitability ingest report."""

    as_of = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    results = IndustryProfitabilityLocationResultSerializer(many=True)


class MonthlyPublicationUpdateIndicatorResultSerializer(serializers.Serializer):
    """Per-indicator result from a monthly publication-update run."""

    name = serializers.CharField()
    status = serializers.CharField()


class MonthlyPublicationUpdateResponseSerializer(serializers.Serializer):
    """Monthly calendar-less publication update report."""

    as_of = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    checked = serializers.IntegerField()
    updated = serializers.ListField(child=serializers.CharField())
    failed = serializers.ListField(child=serializers.CharField())
    results = MonthlyPublicationUpdateIndicatorResultSerializer(many=True)


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
            "full_name",
            "location",
            "category",
            "subcategory",
            "series_label",
            "technical_name",
            "frequency",
            "source",
            "ticker",
            "description",
            "source_url",
            "measure_type",
            "parent_series_label",
            "expansion_relation",
            "is_hidden",
            "publication_schedule_mode",
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
