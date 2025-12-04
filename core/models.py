from typing import List

from django.db import models
from django.db.models.fields.related import ForeignKey


class BaseModel(models.Model):
    """Base Model to be inherited accross entire application."""

    date_added = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def convert_to_dict(
        self,
        remove_foreign_key: bool = False,
        remove_auto_fields: bool = True,
        remove_cache_fields: bool = True,
        remove_specific_fields: List[str] = [],
    ) -> dict:
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
        abstract = True
        ordering = ["-date_added"]
