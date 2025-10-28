import logging
from typing import List, Type, TypeVar

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from .models import BaseLogModel, BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
L = TypeVar("L", bound=BaseLogModel)


def get(model: Type[T], *args, **kwargs) -> T:
    """Get entity from database."""
    try:
        return model.objects.get(*args, **kwargs)
    except ObjectDoesNotExist:
        raise NotFound(detail=f"No {model.__name__} found matching {kwargs}")


def update_with_logs(
    model_to_update: T,
    log_model: Type[L],
    updates: dict,
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs in a related log table."""
    update_logs = updates.pop("logs", None)
    has_changes = False
    is_none_value_override = False

    for field, new_value in updates.items():
        old_value = getattr(model_to_update, field, None)
        if old_value != new_value:
            should_update = enable_none_updates or new_value is not None
            if should_update:
                setattr(model_to_update, field, new_value)
                has_changes = True
                is_none_value_override = new_value and not old_value

    if has_changes:
        model_to_update.save()

        if update_logs and is_none_value_override:
            fk_field = getattr(log_model, "fk_name", None)
            log_kwargs = {fk_field: model_to_update, "logs": update_logs}
            log_model.objects.create(**log_kwargs)

    return model_to_update


def upsert_with_logs(
    model: Type[T],
    log_model: Type[L],
    lookup_kwargs: dict,
    updates: dict,
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs if exists, or create entity in database."""
    try:
        model_to_update = model.objects.get(**lookup_kwargs)
        return update_with_logs(
            model_to_update, log_model, updates, enable_none_updates
        )
    except ObjectDoesNotExist:
        create_data = {
            **lookup_kwargs,
            **{k: v for k, v in updates.items() if k != "logs"},
        }
        return model.objects.create(**create_data)


def convert_query_to_dictionary_list(queryset: QuerySet) -> List[dict]:
    """Convert a query into a List of Dictionary."""
    return [object.convert_to_dict() for object in queryset]
