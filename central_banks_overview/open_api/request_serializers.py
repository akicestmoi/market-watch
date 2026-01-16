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


class CentralBankDataIngestionItemSerializer(serializers.Serializer):
    """Central Bank Data Ingestion Item Serializer."""

    central_bank = serializers.CharField()
    date = serializers.DateField()

    def validate_central_bank(self, value: str) -> str:
        """Validate central bank."""
        if value not in [choice.value for choice in CentralBankChoices]:
            raise serializers.ValidationError(f"Invalid central bank value: {value}")
        return value


class CentralBankDataIngestionSerializer(serializers.ListSerializer):
    """Central Bank Data Ingestion Serializer."""

    child = CentralBankDataIngestionItemSerializer(required=False)


class ListCentralBankDataSerializer(CentralBankBaseSerializer):
    """List Central Bank Data Serializer."""

    date = serializers.DateField(required=False, allow_null=True)
    last_value = serializers.BooleanField(required=False, default=False)


class GetCentralBankMeetingDatesSerializer(CentralBankBaseSerializer):
    """Get Central Bank Meeting Dates Serializer."""

    pass


class StirFuturesPriceIngestionSerializer(serializers.Serializer):
    """Stir Futures Price Ingestion Serializer."""

    date = serializers.DateField()


class EstrPriceIngestionViaPdfSerializer(serializers.Serializer):
    """ESTR Price Ingestion via PDF Serializer."""

    pdf_file = serializers.FileField()
    date = serializers.DateField()


class ListStirFuturesPricesSerializer(CentralBankBaseSerializer):
    """List Stir Futures Prices Serializer."""

    date = serializers.DateField(required=False, allow_null=True)


class BulkUpdateStirFuturesPricesItemSerializer(serializers.Serializer):
    """Bulk Update Stir Futures Prices Item Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()
    maturity = serializers.CharField()
    price = serializers.FloatField()
    logs = serializers.CharField(required=False)


class BulkUpdateStirFuturesPricesSerializer(serializers.ListSerializer):
    """Bulk Update Stir Futures Prices Serializer."""

    child = BulkUpdateStirFuturesPricesItemSerializer()


class CsvBulkUpdateStirFuturesPricesSerializer(serializers.Serializer):
    """Csv Bulk Update Stir Futures Prices Serializer."""

    csv_file = serializers.FileField()


class GetCentralBankProbabilityMatrixSerializer(CentralBankBaseSerializer):
    """Get Central Bank Probability Matrix Serializer."""

    date = serializers.DateField()


class DeleteStirFuturesPricesSerializer(CentralBankBaseSerializer):
    """Delete STIR Futures Prices Serializer."""

    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        """Validate that at least one parameter is provided."""
        central_banks = attrs.get("central_banks")
        if central_banks and not central_banks.strip():
            central_banks = None
        if not any(
            [
                attrs.get("start_date"),
                attrs.get("end_date"),
                central_banks,
            ]
        ):
            raise serializers.ValidationError(
                "At least one of 'start_date', 'end_date', or 'central_banks' must be provided."
            )
        return attrs
