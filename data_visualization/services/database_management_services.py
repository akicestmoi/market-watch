import re
from typing import List, Protocol, TypedDict

from django.apps import apps
from django.db import connection
from django.db.backends.utils import CursorWrapper


class DatabaseTableInfo(TypedDict):
    """Information about a database table."""

    name: str
    display_name: str
    count: int
    size: str
    size_bytes: int


class ModelWithName(Protocol):
    """Protocol for objects that have a __name__ attribute."""

    __name__: str


def _format_model_name(model: ModelWithName) -> str:
    """Format model class name for display.

    Uses the actual model class name (e.g., CentralBankDataModel)
    to ensure correct spacing based on camelCase.
    Example: CentralBankDataModel -> "Central Bank Data"
    """
    model_name = model.__name__

    # Remove "Model" suffix (case-sensitive, as model names are always PascalCase)
    if model_name.endswith("Model"):
        model_name = model_name[:-5]

    # Split camelCase: insert space before capital letters
    # that follows a lowercase letter or digit
    formatted = re.sub(r"(?<!^)(?=[A-Z])", " ", model_name)

    # Split by spaces and capitalize each word
    words = formatted.split()
    capitalized_words = [word.capitalize() for word in words]

    return " ".join(capitalized_words)


def _format_table_size(size_bytes: int) -> str:
    """Format table size in bytes."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{int(size_bytes / 1024)} kB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{int(size_bytes / (1024 * 1024))} MB"
    elif size_bytes < 1024 * 1024 * 1024 * 1024:
        return f"{int(size_bytes / (1024 * 1024 * 1024))} GB"
    else:
        return f"{int(size_bytes / (1024 * 1024 * 1024 * 1024))} TB"


def _get_table_size(cursor: CursorWrapper, table_name: str) -> int:
    """Get table size."""
    try:
        cursor.execute(
            """
            SELECT pg_size_pretty(pg_total_relation_size(%s)), pg_total_relation_size(%s)
            """,
            [table_name, table_name],
        )
        result = cursor.fetchone()
        return result[1] if len(result) > 0 and result[1] else 0
    except Exception:
        return 0


def get_database_information() -> List[DatabaseTableInfo]:
    """Get information about all database tables."""
    tables_info = []
    admin_total_count = 0
    admin_total_size_bytes = 0

    all_models = apps.get_models()
    with connection.cursor() as cursor:
        for model in all_models:
            # Skip if model doesn't have a database table
            if not hasattr(model, "_meta") or not model._meta.db_table:
                continue

            table_name = model._meta.db_table
            count = model.objects.count()

            is_admin = (
                table_name.startswith("auth_")
                or table_name.startswith("django_")
                or table_name.startswith("admin_")
            )
            size_bytes = _get_table_size(cursor, table_name)

            if is_admin:
                admin_total_count += count
                admin_total_size_bytes += size_bytes
            else:
                display_name = _format_model_name(model)
                tables_info.append(
                    DatabaseTableInfo(
                        name=table_name,
                        display_name=display_name,
                        count=count,
                        size=_format_table_size(size_bytes),
                        size_bytes=size_bytes,
                    )
                )

    tables_info.sort(key=lambda x: x["size_bytes"], reverse=True)

    if admin_total_count > 0 or admin_total_size_bytes > 0:
        tables_info.append(
            DatabaseTableInfo(
                name="admin",
                display_name="Admin",
                count=admin_total_count,
                size=_format_table_size(admin_total_size_bytes),
                size_bytes=admin_total_size_bytes,
            )
        )

    return tables_info
