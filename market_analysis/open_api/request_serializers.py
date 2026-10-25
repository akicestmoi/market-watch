"""DRF request serializers for market analysis API inputs."""

from rest_framework import serializers


class ReportingDateSerializer(serializers.Serializer):
    """Reporting date plus optional force flag for pipeline / generate."""

    reporting_date = serializers.DateField()
    force = serializers.BooleanField(required=False, default=False)


class GetRecapSerializer(serializers.Serializer):
    """Optional filters to fetch a daily recap by date or id."""

    reporting_date = serializers.DateField(required=False)
    id = serializers.IntegerField(required=False, min_value=1)


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
