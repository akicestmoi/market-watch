import json
from datetime import datetime
from typing import List, Optional
from unittest.mock import MagicMock

from django.db.models import QuerySet

from core.services import convert_query_to_dictionary_list


def load_json_mock(file_path: str) -> dict:
    """Load JSON mock file and return dictionary."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_file_content(file_path: str) -> bytes:
    """Read file content and return bytes."""
    with open(file_path, "rb") as f:
        return f.read()


def parse_query_for_testing(
    queryset: QuerySet,
    sort_keys: List[str] = [],
    date_format: str = "%Y-%m-%d %H:%M:%S%z",
) -> List[dict]:
    """
    Convert queryset to dictionary list, normalize datetime objects, and sort."""
    result = convert_query_to_dictionary_list(queryset)

    parsed_result = []
    for item in result:
        parsed_item = item.copy()
        for key, value in parsed_item.items():
            if isinstance(value, datetime):
                parsed_item[key] = datetime.strftime(value, date_format)
        parsed_result.append(parsed_item)

    if sort_keys:
        parsed_result.sort(key=lambda x: tuple(x[key] for key in sort_keys))

    return parsed_result


class MockResponse:
    """Mock response object."""

    def __init__(self, status_code: int, content: bytes, text: Optional[str] = None):
        self.mock = MagicMock()
        self.mock.status_code = status_code
        self.mock.content = content
        # If text is not provided, decode content to string
        # Used for mocking HTML responses
        if text is None:
            self.mock.text = content.decode("utf-8")
        else:
            self.mock.text = text

    def __getattr__(self, name: str):
        return getattr(self.mock, name)
