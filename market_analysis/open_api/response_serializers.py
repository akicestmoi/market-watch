"""DRF response serializers for market analysis API outputs."""

from rest_framework import serializers


class RecapResponseSerializer(serializers.Serializer):
    """Persisted daily market analysis recap."""

    id = serializers.IntegerField()
    reporting_date = serializers.DateField()
    title = serializers.CharField()
    main_summary = serializers.CharField()
    us_summary = serializers.CharField()
    eur_summary = serializers.CharField()
    jp_summary = serializers.CharField()
    additional_summary = serializers.CharField()
    source_urls = serializers.JSONField()
    model_name = serializers.CharField()
    prompt_version = serializers.CharField()
    date_added = serializers.DateTimeField()


class ChatResponseSerializer(serializers.Serializer):
    """Chat turn result, including updated message history."""

    answer = serializers.CharField()
    citations = serializers.JSONField()
    missing_information = serializers.JSONField()
    uncertainties = serializers.JSONField()
    messages = serializers.JSONField()
    proposed_recap_title = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_main_summary = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_us_summary = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_eur_summary = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_jp_summary = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_additional_summary = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    proposed_recap_reporting_date = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    cursor_guidelines_prompt = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    recap_updated = serializers.BooleanField(required=False, default=False)


class ArticleCacheResponseSerializer(serializers.Serializer):
    """Redis-cached article analysis digests for a reporting date."""

    reporting_date = serializers.CharField()
    prompt_version = serializers.CharField()
    ttl_seconds = serializers.IntegerField()
    count = serializers.IntegerField()
    items = serializers.JSONField()
    error = serializers.CharField(required=False)
