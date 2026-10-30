"""Tests for shared core models and managers."""

import pytest
from django.test import TestCase
from rest_framework.exceptions import NotFound

from market_overview.models import AssetClassChoices, AssetModel, AssetTypeChoices


class TestBaseManagerGet(TestCase):
    """Test cases for BaseManager.get NotFound mapping."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class=AssetClassChoices.STOCKS,
            asset_type=AssetTypeChoices.EQUITY_INDEX,
        )

    def test_get_success(self):
        """
        GIVEN an existing model instance
        WHEN objects.get is called with valid lookup parameters
        THEN the instance should be returned
        """
        result = AssetModel.objects.get(short_name="TEST")

        assert result == self.asset
        assert result.short_name == "TEST"

    def test_get_not_found(self):
        """
        GIVEN a non-existent model instance
        WHEN objects.get is called with invalid lookup parameters
        THEN a NotFound exception should be raised
        """
        with pytest.raises(NotFound) as exc_info:
            AssetModel.objects.get(short_name="NONEXISTENT")

        assert "No AssetModel found matching" in str(exc_info.value.detail)
        assert "NONEXISTENT" in str(exc_info.value.detail)
