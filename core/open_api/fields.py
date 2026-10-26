"""Shared DRF request serializer fields used across apps."""

from collections.abc import Sequence

from rest_framework import serializers


class CommaSeparatedChoiceField(serializers.CharField):
    """CSV query value; each token validated via ``ChoiceField``.

    Pass ``enum_class`` (e.g. a Django ``TextChoices``) to wrap each validated
    value as that enum member; otherwise raw choice values are returned.
    """

    def __init__(
        self,
        choices: Sequence,
        *,
        enum_class: type | None = None,
        **kwargs,
    ):
        """Initialize with ``ChoiceField``-compatible ``choices``."""
        self.choice_field = serializers.ChoiceField(choices=choices)
        self.enum_class = enum_class
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        """Split on commas and validate each token against ``choices``."""
        value = super().to_internal_value(data)
        if not value or not str(value).strip():
            return None
        items = []
        for token in str(value).split(","):
            token = token.strip()
            if not token:
                continue
            validated = self.choice_field.to_internal_value(token)
            if self.enum_class is not None:
                validated = self.enum_class(validated)
            items.append(validated)
        return items or None


class CommaSeparatedIntegerField(serializers.CharField):
    """CSV of integers (e.g. ids or month numbers)."""

    def __init__(
        self,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        **kwargs,
    ):
        """Initialize with optional min/max bounds per token."""
        self.min_value = min_value
        self.max_value = max_value
        self.integer_field = serializers.IntegerField()
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> list[int] | None:
        """Split on commas and validate each token as an integer."""
        value = super().to_internal_value(data)
        if not value or not str(value).strip():
            return None
        items: list[int] = []
        for token in str(value).split(","):
            token = token.strip()
            if not token:
                continue
            number = self.integer_field.to_internal_value(token)
            if not isinstance(number, int):
                raise serializers.ValidationError("A valid integer is required.")
            if self.min_value is not None and number < self.min_value:
                raise serializers.ValidationError(
                    f"Ensure this value is greater than or equal to {self.min_value}."
                )
            if self.max_value is not None and number > self.max_value:
                raise serializers.ValidationError(
                    f"Ensure this value is less than or equal to {self.max_value}."
                )
            items.append(number)
        return items or None
