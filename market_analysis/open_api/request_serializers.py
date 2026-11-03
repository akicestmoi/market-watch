"""DRF request serializers for market analysis API inputs."""

from rest_framework import serializers

from market_analysis.models import ArticleRegionChoices, NewsSourceChoices


class ReportingDateSerializer(serializers.Serializer):
    """Reporting date plus optional force flag for pipeline / generate."""

    reporting_date = serializers.DateField()
    force = serializers.BooleanField(required=False, default=False)


class GetRecapSerializer(serializers.Serializer):
    """Optional reporting date to fetch a daily recap (latest when omitted)."""

    reporting_date = serializers.DateField(required=False)


class ChatMessageSerializer(serializers.Serializer):
    """One prior chat turn (user or assistant)."""

    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=8000)


class ChatAskSerializer(serializers.Serializer):
    """Chat ask body: current question and optional prior messages."""

    question = serializers.CharField(max_length=4000)
    messages = ChatMessageSerializer(many=True, required=False, default=list)


class GetArticleCacheSerializer(serializers.Serializer):
    """Filters to inspect Redis-cached article analyses for a reporting date."""

    reporting_date = serializers.DateField()
    source_url = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )


class ExtractArticleSerializer(serializers.Serializer):
    """Query params to scrape catalog news wraps for a reporting date."""

    reporting_date = serializers.DateField()
    source = serializers.ChoiceField(
        choices=NewsSourceChoices.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
        help_text="Optional catalog source. Omit to scrape every configured source.",
    )
    region = serializers.ChoiceField(
        choices=ArticleRegionChoices.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
        help_text=(
            "Optional catalog region. Omit for every region; with a source, "
            "limits multi-region scrapers (e.g. Boursorama FR vs EU)."
        ),
    )

    def validate_source(self, value: str | None) -> str | None:
        """Treat blank query values as no source filter."""
        return value or None

    def validate_region(self, value: str | None) -> str | None:
        """Treat blank query values as no region filter."""
        return value or None
