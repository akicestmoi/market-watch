import json
from typing import Optional
from unittest.mock import MagicMock


def load_json_mock(file_path: str) -> dict:
    """Load JSON mock file and return dictionary."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_file_content(file_path: str) -> bytes:
    """Read file content and return bytes."""
    with open(file_path, "rb") as f:
        return f.read()


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
