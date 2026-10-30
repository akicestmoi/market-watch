"""Shared base models used by domain apps."""

from collections.abc import Sequence
from typing import TypeVar

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.enums import Choices
from django.db.models.fields.related import ForeignKey
from rest_framework.exceptions import NotFound

ChoiceT = TypeVar("ChoiceT", bound=Choices)


class BaseManager(models.Manager):
    """Default manager for BaseModel subclasses."""

    def get(self, *args, **kwargs):
        """Get a row, raising DRF NotFound when it does not exist."""
        try:
            return super().get(*args, **kwargs)
        except ObjectDoesNotExist:
            raise NotFound(detail=f"No {self.model.__name__} found matching {kwargs}")


def get_choice_from_label(choices: type[ChoiceT], label: str) -> ChoiceT:
    """Return the member of ``choices`` whose display label matches ``label``."""
    for choice in choices:
        if str(choice.label) == label:
            return choice
    available = [str(member.label) for member in choices]
    raise ValueError(
        f"Choice does not exist for label {label!r}, available labels: {available}"
    )


def get_choice_labels(choices: type[ChoiceT]) -> list[str]:
    """Display labels in ``ordered()`` order when defined, else declaration order."""
    ordered_attr = getattr(choices, "ordered", None)
    if callable(ordered_attr):
        ordered_members = ordered_attr()
        if isinstance(ordered_members, Sequence) and not isinstance(
            ordered_members, (str, bytes)
        ):
            return [
                str(item.label) for item in ordered_members if isinstance(item, choices)
            ]
    return [str(choice.label) for choice in choices]


class BaseModel(models.Model):
    """Base Model to be inherited accross entire application."""

    date_added = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    objects = BaseManager()

    class Meta:
        """Base model metadata."""

        abstract = True

    def convert_to_dict(
        self,
        remove_foreign_key: bool = False,
        remove_auto_fields: bool = True,
        remove_cache_fields: bool = True,
        remove_specific_fields: list[str] = [],
    ) -> dict:  # Polymorphic model serializer until per-model TypedDicts exist.
        """Convert Model to Dictionary."""
        auto_fields = ["id", "date_added", "last_modified"]
        cache_fields = ["_prefetched_objects_cache", "_state"]
        fields_to_remove = []

        if remove_cache_fields:
            fields_to_remove.extend(cache_fields)
        if remove_auto_fields:
            fields_to_remove.extend(auto_fields)
        if remove_foreign_key:
            foreign_key_list = [
                field.name
                for field in self._meta.get_fields()
                if isinstance(field, ForeignKey)
            ]
            fields_to_remove.extend(
                [f"{foreign_key}_id" for foreign_key in foreign_key_list]
            )
        if remove_specific_fields:
            fields_to_remove.extend(remove_specific_fields)

        model_as_dict = {
            key: value
            for key, value in self.__dict__.items()
            if key not in fields_to_remove
        }
        return model_as_dict


class BaseLogModel(BaseModel):
    """Base Log Model to keep log of changes."""

    logs = models.TextField()

    class Meta:
        """Base log model metadata (newest first)."""

        abstract = True
        ordering = ["-date_added"]
