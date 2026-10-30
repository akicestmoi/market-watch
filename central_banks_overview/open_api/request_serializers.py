"""DRF request serializers for central banks overview API inputs."""

from rest_framework import serializers

from central_banks_overview.models import CentralBankChoices
from core.open_api.fields import CommaSeparatedChoiceField, CommaSeparatedIntegerField


class CentralBankBaseSerializer(serializers.Serializer):
    """Central Bank Base Serializer."""

    central_banks = CommaSeparatedChoiceField(
        choices=CentralBankChoices.choices,
        enum_class=CentralBankChoices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class CentralBankDataIngestionItemSerializer(serializers.Serializer):
    """Central Bank Data Ingestion Item Serializer."""

    central_bank = serializers.ChoiceField(choices=CentralBankChoices.choices)
    date = serializers.DateField()


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

    ids = CommaSeparatedIntegerField(required=False, allow_blank=True, allow_null=True)


class DeleteCentralBankDataSerializer(CentralBankBaseSerializer):
    """Delete Central Bank Data Serializer."""

    ids = CommaSeparatedIntegerField(required=False, allow_blank=True, allow_null=True)
