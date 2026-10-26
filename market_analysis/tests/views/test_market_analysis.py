"""Tests for market_analysis_views (daily recap GET API)."""

from datetime import date

from django.test import Client, TestCase

from market_analysis.models import DailyRecapModel


class GetDailyRecapViewTests(TestCase):
    """Tests for the daily recap GET API."""

    def setUp(self):
        """Create a sample DailyRecap for view tests."""
        self.client = Client()
        DailyRecapModel.objects.create(
            reporting_date=date(2024, 1, 2),
            title="2 January 2024: Quiet session",
            main_summary="Worldwide quiet session.",
            us_summary="- Stocks: US mixed.\n- Uncertainties: None.",
            eur_summary="- Rates: EUR yields steady.\n- Uncertainties: None.",
            jp_summary="- Stocks: Nikkei soft.\n- Uncertainties: None.",
            additional_summary="- Commodities: Oil soft.\n- Uncertainties: None.",
            source_urls=["https://example.com/a"],
            model_name="gpt-6-luna",
            prompt_version="market_analysis.v1",
        )

    def test_get_latest_recap(self):
        """
        GIVEN a DailyRecap stored in the database
        WHEN GET /analysis/recap is called without filters
        THEN the latest recap is returned with title and zone summaries
        """
        response = self.client.get("/analysis/recap")
        assert response.status_code == 200
        data = response.json()
        assert data["title"].startswith("2 January 2024")
        assert data["main_summary"].startswith("Worldwide")
        assert "US mixed" in data["us_summary"]
        assert data["reporting_date"] == "2024-01-02"

    def test_get_recap_by_date(self):
        """
        GIVEN a DailyRecap for a specific reporting date
        WHEN GET /analysis/recap is called with that reporting_date
        THEN the matching recap is returned
        """
        response = self.client.get("/analysis/recap", {"reporting_date": "2024-01-02"})
        assert response.status_code == 200
        assert response.json()["title"].startswith("2 January 2024")

    def test_get_recap_not_found(self):
        """
        GIVEN no DailyRecap for a future reporting date
        WHEN GET /analysis/recap is called with that date
        THEN a 404 response is returned
        """
        response = self.client.get("/analysis/recap", {"reporting_date": "2099-01-01"})
        assert response.status_code == 404
