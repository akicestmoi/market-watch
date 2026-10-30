"""Tests for sector analysis visualization views."""

from django.test import Client, TestCase

from core.testing import read_file_content

_EXPECTED_HTML = read_file_content(
    "data_visualization/tests/mock_web_data/sector_analysis/placeholder.html"
)


class TestSectorAnalysisView(TestCase):
    """Test cases for sector_analysis_view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.base_url = "/sector-analysis/"

    def test_sector_analysis_view_success(self):
        """
        GIVEN the sector analysis page
        WHEN accessing the view
        THEN the blank placeholder page renders successfully
        """
        response = self.client.get(self.base_url)
        assert response.status_code == 200
        assert response.content == _EXPECTED_HTML
