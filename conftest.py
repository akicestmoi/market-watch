"""Root pytest hooks shared across all Django apps."""

import pytest
from django.urls import get_resolver


@pytest.fixture(scope="session", autouse=True)
def preload_django_urlconf():
    """Import ROOT_URLCONF before any freezegun patch.

    Loading URLConf under ``@freeze_time`` can import ``pydantic_ai``, whose
    ``TypeAdapter(datetime)`` then sees freezegun's ``FakeDatetime`` and fails.
    Warm the resolver once with real ``datetime`` for the whole suite.
    """
    get_resolver().urlconf_module
