"""DRF response serializers for market overview API outputs."""

from rest_framework import serializers

from market_overview.models.market_prices import (
    AssetModel,
    HolidayModel,
    MarketPriceModel,
    PriceUpdateLogModel,
)


class AssetNamesResponseSerializerItem(serializers.Serializer):
    """Asset Names Response Serializer Item."""

    short_name = serializers.CharField()
    full_name = serializers.CharField()


class GetAssetNamesResponseSerializer(serializers.ListSerializer):
    """Get Asset Names Response Serializer."""

    child = AssetNamesResponseSerializerItem()


class MarketPriceIngestionResponseSerializer(serializers.Serializer):
    """Market Price Ingestion Response Serializer."""

    message = serializers.CharField()
    asset_not_updated = serializers.ListField(child=serializers.CharField())
    asset_not_updated_holiday = serializers.ListField(child=serializers.CharField())
    date = serializers.DateField()


class BatchPriceIngestionResponseSerializerItem(serializers.Serializer):
    """Batch Price Ingestion Response Serializer Item."""

    short_name = serializers.CharField()
    status = serializers.CharField()
    error = serializers.CharField()
    asset_not_updated = serializers.ListField(child=serializers.CharField())
    asset_not_updated_holiday = serializers.ListField(child=serializers.CharField())


class BatchPriceIngestionResponseSerializer(serializers.Serializer):
    """Batch Price Ingestion Response Serializer."""

    message = serializers.CharField()
    results = serializers.ListField(child=BatchPriceIngestionResponseSerializerItem())


class AssetResponseSerializer(serializers.ModelSerializer):
    """Asset Serializer."""

    class Meta:
        """Asset response serializer metadata."""

        model = AssetModel
        fields = [
            "asset_id",
            "short_name",
            "full_name",
            "asset_class",
            "location",
            "maturity",
            "asset_type",
            "ticker",
            "source",
        ]


class GetAssetWithoutPriceResponseSerializer(serializers.Serializer):
    """Get Asset Without Price Response Serializer."""

    date = serializers.DateField()
    short_name = serializers.CharField()
    full_name = serializers.CharField()
    maturity = serializers.FloatField()
    comment = serializers.CharField()


class MarketPriceResponseSerializer(serializers.ModelSerializer):
    """Market Price Serializer with Asset information."""

    id = serializers.IntegerField(source="pk", read_only=True)
    asset = AssetResponseSerializer(read_only=True)

    class Meta:
        """Market price response serializer metadata."""

        model = MarketPriceModel
        fields = [
            "id",
            "date",
            "price",
            "comment",
            "asset",
        ]


class PriceUpdateLogResponseSerializer(serializers.ModelSerializer):
    """Price Update Log Response Serializer."""

    class Meta:
        """Price update log response serializer metadata."""

        model = PriceUpdateLogModel
        fields = [
            "market_price_id",
            "logs",
        ]


class HolidayResponseSerializer(serializers.ModelSerializer):
    """Holiday Response Serializer."""

    class Meta:
        """Holiday response serializer metadata."""

        model = HolidayModel
        fields = [
            "date",
            "name",
            "location",
        ]


class DeleteAssetResponseSerializer(serializers.Serializer):
    """Delete Asset Response Serializer."""

    message = serializers.CharField()


class DeleteHolidaysResponseSerializer(serializers.Serializer):
    """Delete Holidays Response Serializer."""

    message = serializers.CharField()


class DeleteMarketPricesResponseSerializer(serializers.Serializer):
    """Delete Market Prices Response Serializer."""

    message = serializers.CharField()
    deleted_count = serializers.IntegerField()


class MarkAsHolidayResponseSerializer(serializers.Serializer):
    """Mark As Holiday Response Serializer."""

    message = serializers.CharField()
    updated_count = serializers.IntegerField()
    not_found = serializers.ListField(child=serializers.CharField())


class SectorAnalysisIngestionResultSerializer(serializers.Serializer):
    """One equity-index result from a sector-analysis ingestion run."""

    date = serializers.CharField()
    equity_index = serializers.CharField()
    subsectors_upserted = serializers.IntegerField()
    names_missing_weight = serializers.ListField(child=serializers.CharField())
    names_missing_return = serializers.ListField(child=serializers.CharField())


class IngestSectorAnalysisResponseSerializer(serializers.Serializer):
    """Sector-analysis ingestion response."""

    message = serializers.CharField()
    results = serializers.ListField(child=SectorAnalysisIngestionResultSerializer())


class SubsectorTopMoverResponseSerializer(serializers.Serializer):
    """One company among the top contributors inside a subsector day."""

    company = serializers.CharField()
    ticker = serializers.CharField()
    weight = serializers.FloatField()
    daily_return = serializers.FloatField()
    contribution = serializers.FloatField()


class SubsectorDailyMoveResponseSerializer(serializers.Serializer):
    """One stored subsector day move from the sector-analysis table."""

    date = serializers.CharField()
    equity_index = serializers.CharField()
    sector = serializers.CharField()
    subsector = serializers.CharField()
    weight = serializers.FloatField()
    daily_return = serializers.FloatField()
    contribution = serializers.FloatField()
    top_movers = SubsectorTopMoverResponseSerializer(many=True)


class EarningsIngestionResultSerializer(serializers.Serializer):
    """Summary of one earnings watchlist ingest or refresh run for one index."""

    equity_index = serializers.CharField()
    companies_updated = serializers.IntegerField()
    tickers_failed = serializers.ListField(child=serializers.CharField())
    as_of = serializers.CharField(required=False)


class EarningsWatchlistRunResponseSerializer(serializers.Serializer):
    """Shared response for earnings ingest (update, weights, roll) and refresh."""

    message = serializers.CharField()
    as_of = serializers.CharField()
    earnings_results = EarningsIngestionResultSerializer(many=True)
    weight_results = EarningsIngestionResultSerializer(many=True)
    tickers_failed = serializers.ListField(child=serializers.CharField())


class UpcomingEarningsInformationResponseSerializer(serializers.Serializer):
    """Stored upcoming_* fields for one watchlist company."""

    announcement_datetime = serializers.CharField(allow_null=True)
    reporting_period_end = serializers.CharField(allow_null=True)
    eps_expected = serializers.FloatField(allow_null=True)
    revenue_expected = serializers.FloatField(allow_null=True)


class ReportedEarningsInformationResponseSerializer(serializers.Serializer):
    """Stored current_* or previous_* fields for one watchlist company."""

    reporting_period_end = serializers.CharField(allow_null=True)
    eps = serializers.FloatField(allow_null=True)
    eps_expected = serializers.FloatField(allow_null=True)
    revenue_expected = serializers.FloatField(allow_null=True)
    revenue = serializers.FloatField(allow_null=True)
    operating_income = serializers.FloatField(allow_null=True)
    gross_profit = serializers.FloatField(allow_null=True)
    ebitda = serializers.FloatField(allow_null=True)


class EarningsWatchlistCompanyResponseSerializer(serializers.Serializer):
    """One stored earnings watchlist company in GET responses."""

    company = serializers.CharField()
    ticker = serializers.CharField()
    equity_index = serializers.CharField()
    weight_pct = serializers.FloatField(allow_null=True)
    upcoming = UpcomingEarningsInformationResponseSerializer()
    current = ReportedEarningsInformationResponseSerializer()
    previous = ReportedEarningsInformationResponseSerializer()


class GetEarningsWatchlistResponseSerializer(serializers.Serializer):
    """Stored earnings watchlist companies for one region."""

    location = serializers.CharField()
    companies = EarningsWatchlistCompanyResponseSerializer(many=True)


class GetSectorAnalysisResponseSerializer(serializers.Serializer):
    """Stored subsector day moves for one region and trading day."""

    location = serializers.CharField()
    date = serializers.CharField()
    equity_index = serializers.CharField()
    subsectors = SubsectorDailyMoveResponseSerializer(many=True)
