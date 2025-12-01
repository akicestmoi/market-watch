from django.db import models
from django.db.models.fields.related import ForeignKey


class BaseModel(models.Model):
    """Base Model to be inherited accross entire application."""

    date_added = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def convert_to_dict(
        self, remove_foreign_key: bool = False, remove_auto_fields: bool = True
    ) -> dict:
        """Convert Model to Dictionary."""
        auto_fields = ["id", "date_added", "last_modified"]
        model_as_dict = {
            key: value
            for key, value in self.__dict__.items()
            if key != "_state" and not (remove_auto_fields and key in auto_fields)
        }
        if remove_foreign_key:
            foreign_key_list = [
                field.name
                for field in self._meta.get_fields()
                if isinstance(field, ForeignKey)
            ]
            for foreign_key in foreign_key_list:
                if f"{foreign_key}_id" in model_as_dict.keys():
                    model_as_dict.pop(f"{foreign_key}_id")
        return model_as_dict


class BaseLogModel(BaseModel):
    """Base Log Model to keep log of changes."""

    logs = models.TextField()

    class Meta:
        abstract = True
        ordering = ["-date_added"]
