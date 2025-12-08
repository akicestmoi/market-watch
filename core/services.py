import logging
from typing import List, Optional, Type, TypeVar

import requests
from bs4 import BeautifulSoup
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
    logging_on_fields: List[str] = [],
    none_skip_fields: List[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs in a related log table."""
    if not none_skip_fields and not enable_none_updates:
        raise ValueError("Need to specify fields to skip or enable none updates.")

    if none_skip_fields:
        model_fields = [field.name for field in model_to_update._meta.get_fields()]
        if not all(field in model_fields for field in none_skip_fields):
            raise ValueError(f"Fields to skip must be in model: {model_fields}")

    update_logs = updates.pop("logs", "")
    has_changes = False

    for field in none_skip_fields:
        if field in updates:
            existing_value = getattr(model_to_update, field, None)
            new_value = updates[field]
            if existing_value is not None and new_value is None:
                return model_to_update

    for field, new_value in updates.items():
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
    model: Type[T],
    log_model: Type[L],
    lookup_kwargs: dict,
    updates: dict,
    logging_on_fields: List[str] = [],
    none_skip_fields: List[str] = [],
    enable_none_updates: bool = False,
) -> T:
    """Update entity and create logs if exists, or create entity in database."""
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
    except ObjectDoesNotExist:
        create_data = {
            **lookup_kwargs,
            **{k: v for k, v in updates.items() if k != "logs"},
        }
        return model.objects.create(**create_data)


def convert_query_to_dictionary_list(
    queryset: QuerySet,
    remove_foreign_key: bool = False,
    remove_auto_fields: bool = True,
    remove_cache_fields: bool = True,
    remove_specific_fields: List[str] = [],
) -> List[dict]:
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


def fetch_html(url: str) -> Optional[BeautifulSoup]:
    """Fetch and parse HTML from a URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code >= 400:
            logger.warning(f"Error fetching {url}: HTTP {response.status_code}")
            return
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return
