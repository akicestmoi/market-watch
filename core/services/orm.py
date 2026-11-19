"""Shared ORM helpers: logged updates, upserts, and queryset dict conversion."""

from typing import TypeVar

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound

from core.models import BaseLogModel, BaseModel

T = TypeVar("T", bound=BaseModel)
L = TypeVar("L", bound=BaseLogModel)


def update_with_logs(
    model_to_update: T,
    log_model: type[L],
    # Usage of dict: field keys vary by model (abstract helper).
    updates: dict,
    logging_on_fields: list[str] = [],
    none_skip_fields: list[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs in a related log table."""
    if not none_skip_fields and not enable_none_updates:
        raise ValueError("Need to specify fields to skip or enable none updates.")

    if none_skip_fields:
        model_fields = [field.name for field in model_to_update._meta.get_fields()]
        if not all(field in model_fields for field in none_skip_fields):
            raise ValueError(f"Fields to skip must be in model: {model_fields}")

    update_logs = updates.get("logs") or ""
    has_changes = False
    field_updates = [(key, value) for key, value in updates.items() if key != "logs"]

    for field, new_value in field_updates:
        if field in none_skip_fields:
            existing_value = getattr(model_to_update, field, None)
            if existing_value is not None and new_value is None:
                return model_to_update

    for field, new_value in field_updates:
        old_value = getattr(model_to_update, field, None)
        if old_value != new_value:
            if enable_none_updates or new_value is not None:
                setattr(model_to_update, field, new_value)
                has_changes = True
                if field in logging_on_fields:
                    update_logs += f" Updated {field} from {old_value} to {new_value}."

    if has_changes:
        model_to_update.save()
        fk_field = getattr(log_model, "fk_name", None)
        log_kwargs = {fk_field: model_to_update, "logs": update_logs}
        log_model.objects.create(**log_kwargs)

    return model_to_update


def upsert_with_logs(
    model: type[T],
    log_model: type[L],
    # Usage of dict: lookup keys vary by model (abstract helper).
    lookup_kwargs: dict,
    # Usage of dict: field keys vary by model (abstract helper).
    updates: dict,
    logging_on_fields: list[str] = [],
    none_skip_fields: list[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs if exists, or create entity in database.

    Concurrent creates are safe when the model has a matching uniqueness
    constraint on 'lookup_kwargs': a lost race raises IntegrityError and
    returns the row already written by the other process.
    """
    try:
        model_to_update = model.objects.get(**lookup_kwargs)
        return update_with_logs(
            model_to_update=model_to_update,
            log_model=log_model,
            updates=updates,
            logging_on_fields=logging_on_fields,
            none_skip_fields=none_skip_fields,
            enable_none_updates=enable_none_updates,
        )
    except NotFound:
        # BaseManager.get maps a missing row to DRF NotFound.
        create_data = {
            **lookup_kwargs,
            **{k: v for k, v in updates.items() if k != "logs"},
        }
        try:
            with transaction.atomic():
                return model.objects.create(**create_data)
        except IntegrityError:
            # Another process won the insert — leave their row unchanged.
            return model.objects.get(**lookup_kwargs)


def convert_query_to_dictionary_list(
    queryset: QuerySet,
    remove_foreign_key: bool = False,
    remove_auto_fields: bool = True,
    remove_cache_fields: bool = True,
    remove_specific_fields: list[str] = [],
) -> list[
    dict
]:  # Usage of dict: wraps convert_to_dict until per-model TypedDicts exist.
    """Convert a query into a List of Dictionary."""
    return [
        object.convert_to_dict(
            remove_foreign_key,
            remove_auto_fields,
            remove_cache_fields,
            remove_specific_fields,
        )
        for object in queryset
    ]
