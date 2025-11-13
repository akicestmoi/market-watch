from rest_framework import serializers

from central_banks_overview.models import CentralBankChoices


class CentralBankBaseSerializer(serializers.Serializer):
    """Central Bank Base Serializer."""

    central_banks = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate_central_bank(self, value: str) -> str:
        """Validate central bank."""
        if value:
            for cb_value in value.split(","):
                cb_value = cb_value.strip()
                if cb_value not in CentralBankChoices.choices:
                    raise serializers.ValidationError(
                        f"Invalid central bank value: {value}"
                    )
        return value


class GetCentralBankMeetingDatesSerializer(CentralBankBaseSerializer):
    """Get Central Bank Meeting Dates Serializer."""

    pass


class StirFuturesPriceIngestionSerializer(serializers.Serializer):
    """Stir Futures Price Ingestion Serializer."""

    date = serializers.DateField()


class ListStirFuturesPricesSerializer(CentralBankBaseSerializer):
    """List Stir Futures Prices Serializer."""

    date = serializers.DateField(required=False, allow_null=True)

    def validate_central_bank(self, value: str) -> str:
        """Validate central bank."""
        if value:
            for cb_value in value.split(","):
                cb_value = cb_value.strip()
                if cb_value not in CentralBankChoices.choices:
                    raise serializers.ValidationError(
                        f"Invalid central bank value: {value}"
                    )
        return value


class GetCentralBankProbabilityMatrixSerializer(CentralBankBaseSerializer):
    """Get Central Bank Probability Matrix Serializer."""

    date = serializers.DateField()
