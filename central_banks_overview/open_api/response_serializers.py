from rest_framework import serializers

from central_banks_overview.models import (
    CentralBankChoices,
    CentralBankDataModel,
    StirFuturesModel,
)


class CentralBankDataIngestionResponseItemSerializer(serializers.Serializer):
    """Central Bank Data Ingestion Response Item Serializer."""

    data_name = serializers.CharField()
    date = serializers.DateField()


class CentralBankDataIngestionResponseSerializer(serializers.Serializer):
    """Stir Futures Price Response Serializer."""

    message = serializers.CharField()
    updates = serializers.ListField(
        child=CentralBankDataIngestionResponseItemSerializer()
    )


class CentralBankDataResponseSerializer(serializers.ModelSerializer):
    """Central Bank Data Response Serializer."""

    id = serializers.IntegerField(source="pk", read_only=True)

    class Meta:
        model = CentralBankDataModel
        fields = [
            "id",
            "central_bank",
            "short_name",
            "full_name",
            "date",
            "value",
            "comment",
        ]


class CentralBankMeetingDatesResponseSerializer(serializers.Serializer):
    """Central Bank Meeting Dates Response Serializer."""

    central_bank = serializers.ChoiceField(choices=CentralBankChoices.choices)
    meeting_dates = serializers.ListField(child=serializers.DateTimeField())


class StirFuturesPriceIngestionResponseSerializer(serializers.Serializer):
    """Stir Futures Price Response Serializer."""

    message = serializers.CharField()
    stir_futures_updated = serializers.ListField(child=serializers.CharField())
    date = serializers.DateField()


class StirFuturesPriceResponseSerializer(serializers.ModelSerializer):
    """Stir Futures Price Response Serializer."""

    id = serializers.IntegerField(source="pk", read_only=True)

    class Meta:
        model = StirFuturesModel
        fields = [
            "id",
            "central_bank",
            "full_name",
            "maturity",
            "first_accrual_date",
            "last_accrual_date",
            "date",
            "price",
            "source",
            "comment",
        ]


class MeetingProbabilitiesResponseSerializer(serializers.Serializer):
    """Meeting Probabilities Response Serializer."""

    expected_rate_step = serializers.IntegerField()
    probabilities = serializers.ListField(child=serializers.FloatField())


class CentralBankProbabilityMatrixResponseSerializer(serializers.Serializer):
    """Central Bank Probability Matrix Response Serializer."""

    central_bank = serializers.ChoiceField(choices=CentralBankChoices.choices)
    meeting_dates = serializers.ListField(child=serializers.DateField())
    probability_matrix = serializers.ListField(
        child=MeetingProbabilitiesResponseSerializer()
    )


class DeleteStirFuturesPricesResponseSerializer(serializers.Serializer):
    """Delete STIR Futures Prices Response Serializer."""

    message = serializers.CharField()
    deleted_count = serializers.IntegerField()


class DeleteCentralBankDataResponseSerializer(serializers.Serializer):
    """Delete Central Bank Data Response Serializer."""

    message = serializers.CharField()
    deleted_count = serializers.IntegerField()
