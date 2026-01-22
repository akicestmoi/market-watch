from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from data_visualization.services.database_management_services import (
    _format_model_name,
    _format_table_size,
    get_database_information,
)
from market_overview.models import AssetModel, MarketPriceModel


class TestDatabaseManagementServices(TestCase):
    """Test cases for database management services functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.asset = AssetModel.objects.create(
            short_name="TEST",
            full_name="Test Asset",
            asset_id=1,
            asset_class="STOCKS",
            asset_type="EQUITY_INDEX",
        )
        MarketPriceModel.objects.create(
            asset=self.asset,
            date="2024-01-15",
            price=100.0,
        )

    def test_format_simple_model_name(self):
        """
        GIVEN a simple model name with Model suffix
        WHEN _format_model_name is called
        THEN it should remove Model and format correctly
        """
        mock_model = Mock()
        mock_model.__name__ = "AssetModel"

        result = _format_model_name(mock_model)

        assert result == "Asset"

    def test_format_camelcase_model_name(self):
        """
        GIVEN a camelCase model name
        WHEN _format_model_name is called
        THEN it should split and capitalize correctly
        """
        mock_model = Mock()
        mock_model.__name__ = "CentralBankDataModel"

        result = _format_model_name(mock_model)

        assert result == "Central Bank Data"

    def test_format_complex_model_name(self):
        """
        GIVEN a complex camelCase model name
        WHEN _format_model_name is called
        THEN it should format correctly
        """
        mock_model = Mock()
        mock_model.__name__ = "EconomicIndicatorInformationModel"

        result = _format_model_name(mock_model)

        assert result == "Economic Indicator Information"

    def test_format_model_name_without_model_suffix(self):
        """
        GIVEN a model name without Model suffix
        WHEN _format_model_name is called
        THEN it should still format correctly
        """
        mock_model = Mock()
        mock_model.__name__ = "SomeClass"

        result = _format_model_name(mock_model)

        assert result == "Some Class"

    def test_format_single_word_model(self):
        """
        GIVEN a single word model name that is just "Model"
        WHEN _format_model_name is called
        THEN it should return empty string
        """
        mock_model = Mock()
        mock_model.__name__ = "Model"

        result = _format_model_name(mock_model)

        assert result == ""

    def test_format_model_name_with_acronyms(self):
        """
        GIVEN a model name with acronyms
        WHEN _format_model_name is called
        THEN it should split correctly
        """
        mock_model = Mock()
        mock_model.__name__ = "APIKeyModel"

        result = _format_model_name(mock_model)

        assert result == "A P I Key"

    def test_format_real_model_name(self):
        """
        GIVEN a real model class
        WHEN _format_model_name is called
        THEN it should format correctly
        """
        result = _format_model_name(AssetModel)

        assert result == "Asset"

    def test_format_market_price_model(self):
        """
        GIVEN MarketPriceModel class
        WHEN _format_model_name is called
        THEN it should format correctly
        """
        result = _format_model_name(MarketPriceModel)

        assert result == "Market Price"

    def test_format_size_bytes(self):
        """
        GIVEN size in bytes
        WHEN _format_table_size is called
        THEN it should return bytes size in the correct format
        """
        assert _format_table_size(0) == "0 bytes"
        assert _format_table_size(512) == "512 bytes"
        assert _format_table_size(1023) == "1023 bytes"
        assert _format_table_size(1024) == "1 kB"
        assert _format_table_size(512 * 1024) == "512 kB"
        assert _format_table_size(1024 * 1024 - 1) == "1023 kB"
        assert _format_table_size(1024 * 1024) == "1 MB"
        assert _format_table_size(512 * 1024 * 1024) == "512 MB"
        assert _format_table_size(1024 * 1024 * 1024) == "1 GB"
        assert _format_table_size(5 * 1024 * 1024 * 1024) == "5 GB"
        assert _format_table_size(1024 * 1024 * 1024 * 1024) == "1 TB"
        assert _format_table_size(2 * 1024 * 1024 * 1024 * 1024) == "2 TB"

    @patch("data_visualization.services.database_management_services.apps")
    @patch("data_visualization.services.database_management_services.connection")
    def test_get_database_information(self, mock_connection, mock_apps):
        """
        GIVEN database tables
        WHEN get_database_information is called
        THEN it should return formatted table information
        """
        mock_asset_model = Mock()
        mock_asset_model._meta.db_table = "market_overview_assetmodel"
        mock_asset_model.__name__ = "AssetModel"
        mock_asset_model.objects.count.return_value = 5

        mock_price_model = Mock()
        mock_price_model._meta.db_table = "market_overview_marketpricemodel"
        mock_price_model.__name__ = "MarketPriceModel"
        mock_price_model.objects.count.return_value = 10

        mock_auth_user = Mock()
        mock_auth_user._meta.db_table = "auth_user"
        mock_auth_user.__name__ = "User"
        mock_auth_user.objects.count.return_value = 3

        mock_django_session = Mock()
        mock_django_session._meta.db_table = "django_session"
        mock_django_session.__name__ = "Session"
        mock_django_session.objects.count.return_value = 2

        mock_apps.get_models.return_value = [
            mock_asset_model,
            mock_price_model,
            mock_auth_user,
            mock_django_session,
        ]

        # Mock cursor and PostgreSQL queries
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_connection.cursor.return_value = mock_cursor

        # Mock size queries
        def side_effect(_, params):
            if params[0] == "market_overview_assetmodel":
                mock_cursor.fetchone.return_value = ("512 kB", 524288)
            elif params[0] == "market_overview_marketpricemodel":
                mock_cursor.fetchone.return_value = ("1 MB", 1048576)
            elif params[0] == "auth_user":
                mock_cursor.fetchone.return_value = ("256 kB", 262144)
            elif params[0] == "django_session":
                mock_cursor.fetchone.return_value = ("128 kB", 131072)

        mock_cursor.execute.side_effect = side_effect

        result = get_database_information()
        assert result == [
            {
                "name": "market_overview_marketpricemodel",  # Largest table first
                "display_name": "Market Price",
                "count": 10,
                "size": "1 MB",
                "size_bytes": 1048576,
            },
            {
                "name": "market_overview_assetmodel",  # Second largest table
                "display_name": "Asset",
                "count": 5,
                "size": "512 kB",
                "size_bytes": 524288,
            },
            {
                "name": "admin",  # Admin at the bottom
                "display_name": "Admin",
                "count": 5,  # 3 + 2
                "size": "384 kB",  # 393216 / 1024 = 384
                "size_bytes": 393216,  # 262144 + 131072
            },
        ]

    @patch("data_visualization.services.database_management_services.apps")
    @patch("data_visualization.services.database_management_services.connection")
    def test_get_database_information_handles_size_query_exception(
        self, mock_connection, mock_apps
    ):
        """
        GIVEN a table that raises an exception on size query
        WHEN get_database_information is called
        THEN it should handle gracefully with 0 size
        """
        mock_model = Mock()
        mock_model._meta.db_table = "test_table"
        mock_model.__name__ = "TestModel"
        mock_model.objects.count.return_value = 1

        mock_apps.get_models.return_value = [mock_model]

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_connection.cursor.return_value = mock_cursor

        # Simulate exception on size query
        mock_cursor.execute.side_effect = Exception("Database error")

        result = get_database_information()
        assert result == [
            {
                "name": "test_table",
                "display_name": "Test",
                "count": 1,
                "size": "0 bytes",
                "size_bytes": 0,
            }
        ]

    @patch("data_visualization.services.database_management_services.apps")
    @patch("data_visualization.services.database_management_services.connection")
    def test_get_database_information_empty_models(self, mock_connection, mock_apps):
        """
        GIVEN no models
        WHEN get_database_information is called
        THEN empty list is returned
        """
        mock_apps.get_models.return_value = []

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_connection.cursor.return_value = mock_cursor

        result = get_database_information()

        assert result == []

    @patch("data_visualization.services.database_management_services.apps")
    @patch("data_visualization.services.database_management_services.connection")
    def test_get_database_information_null_fetchone_result(
        self, mock_connection, mock_apps
    ):
        """
        GIVEN a table where fetchone returns None for size
        WHEN get_database_information is called
        THEN it should handle gracefully with 0 size
        """
        mock_model = Mock()
        mock_model._meta.db_table = "test_table"
        mock_model.__name__ = "TestModel"
        mock_model.objects.count.return_value = 1

        mock_apps.get_models.return_value = [mock_model]

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_connection.cursor.return_value = mock_cursor

        mock_cursor.execute.side_effect = lambda _, __: setattr(
            mock_cursor, "fetchone", Mock(return_value=(None, None))
        )

        result = get_database_information()
        assert result == [
            {
                "name": "test_table",
                "display_name": "Test",
                "count": 1,
                "size": "0 bytes",
                "size_bytes": 0,
            }
        ]
