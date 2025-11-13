from rest_framework import serializers

from central_banks_overview.models import CentralBankChoices, StirFuturesModel


class CentralBankMeetingDatesResponseSerializer(serializers.Serializer):
    """Central Bank Meeting Dates Response Serializer."""

    central_bank = serializers.ChoiceField(choices=CentralBankChoices.choices)
    meeting_dates = serializers.ListField(child=serializers.DateTimeField())


class StirFuturesPriceIngestionResponseSerializer(serializers.Serializer):
    """Stir Futures Price Response Serializer."""

    message = serializers.CharField()
    stir_futures_not_updated = serializers.ListField(child=serializers.CharField())
    date = serializers.DateField()


class StirFuturesPriceResponseSerializer(serializers.ModelSerializer):
    """Stir Futures Price Response Serializer."""

    class Meta:
        model = StirFuturesModel
        fields = [
            "central_bank",
            "full_name",
            "maturity",
            "reference_start_date",
            "reference_end_date",
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
