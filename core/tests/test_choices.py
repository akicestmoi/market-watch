"""Tests for shared TextChoices label helpers on core.models."""

from django.test import SimpleTestCase

from central_banks_overview.models import CentralBankChoices
from core.models import get_choice_from_label, get_choice_labels
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
)
from market_overview.models import AssetClassChoices, LocationChoices


class TestChoiceLabelHelpers(SimpleTestCase):
    """Tests for get_choice_from_label / get_choice_labels and Choices wrappers."""

    def test_choice_from_label_resolves_members(self):
        """
        GIVEN display labels for several Choices enums
        WHEN get_choice_from_label (or Choices.from_label) is called
        THEN the matching members are returned
        """
        assert (
            get_choice_from_label(LocationChoices, "United States")
            == LocationChoices.US
        )
        assert LocationChoices.from_label("Germany") == LocationChoices.DE
        assert (
            EconomicDataLocationChoices.from_label("France")
            == EconomicDataLocationChoices.FR
        )
        assert AssetClassChoices.from_label("Stocks") == AssetClassChoices.STOCKS
        assert AssetClassChoices.from_label("Interest Rates") == AssetClassChoices.RATES
        assert (
            EconomicDataCategoryChoices.from_label("Growth")
            == EconomicDataCategoryChoices.GROWTH
        )
        assert (
            CentralBankChoices.from_label("Federal Reserve (FRB)")
            == CentralBankChoices.FRB
        )

    def test_choice_from_label_unknown_raises(self):
        """
        GIVEN a label that is not a choice display label
        WHEN get_choice_from_label is called
        THEN ValueError is raised
        """
        with self.assertRaises(ValueError):
            get_choice_from_label(LocationChoices, "Atlantis")

    def test_choice_labels_respects_ordered(self):
        """
        GIVEN Choices with an ordered() classmethod
        WHEN get_choice_labels / get_labels is called
        THEN labels follow that order
        """
        assert get_choice_labels(EconomicDataLocationChoices) == [
            "United States",
            "Europe",
            "France",
            "Japan",
            "Germany",
            "Spain",
            "Italy",
        ]
        assert LocationChoices.get_labels() == [
            "United States",
            "Europe",
            "Germany",
            "France",
            "Japan",
        ]
        assert CentralBankChoices.get_labels() == [
            "Federal Reserve (FRB)",
            "European Central Bank (ECB)",
            "Bank of Japan (BOJ)",
        ]
