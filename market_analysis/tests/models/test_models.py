"""Tests for market_analysis models."""

from datetime import date

import pytest
from django.db import IntegrityError
from django.test import TestCase

from market_analysis.models import DailyRecapModel


def _recap_kwargs(**overrides):
    """Build DailyRecapModel create kwargs with optional overrides."""
    base = {
        "reporting_date": date(2024, 1, 2),
        "title": "t",
        "main_summary": "main",
        "us_summary": "us",
        "eur_summary": "eur",
        "jp_summary": "jp",
        "additional_summary": "extra",
        "source_urls": [],
        "model_name": "gpt-6-luna",
        "prompt_version": "market_analysis.v1",
    }
    base.update(overrides)
    return base


class RecapUniquenessTests(TestCase):
    """Tests for DailyRecap uniqueness constraints."""

    def test_one_recap_per_reporting_date(self):
        """
        GIVEN a DailyRecap already exists for a reporting date
        WHEN another DailyRecap is created for the same date
        THEN an IntegrityError is raised
        """
        DailyRecapModel.objects.create(**_recap_kwargs())
        with pytest.raises(IntegrityError):
            DailyRecapModel.objects.create(
                **_recap_kwargs(title="t2", main_summary="body2")
            )

    def test_update_or_create_overwrites_same_date(self):
        """
        GIVEN a DailyRecap already exists for a reporting date
        WHEN update_or_create is called for the same date with new fields
        THEN the existing row is updated and only one row remains
        """
        DailyRecapModel.objects.create(
            **_recap_kwargs(title="old", main_summary="old body")
        )
        recap, created = DailyRecapModel.objects.update_or_create(
            reporting_date=date(2024, 1, 2),
            defaults={
                "title": "new",
                "main_summary": "new body",
                "us_summary": "us new",
                "eur_summary": "eur new",
                "jp_summary": "jp new",
                "additional_summary": "extra new",
                "source_urls": ["https://example.com"],
                "model_name": "gpt-6-luna",
                "prompt_version": "market_analysis.v1",
            },
        )
        assert created is False
        assert recap.title == "new"
        assert recap.main_summary == "new body"
        assert (
            DailyRecapModel.objects.filter(reporting_date=date(2024, 1, 2)).count() == 1
        )
