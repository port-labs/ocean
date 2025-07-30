import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from base_client import BaseCheckmarxClient


class TestAbstractCheckmarxExporter:
    """Test cases for AbstractCheckmarxExporter."""

    @pytest.fixture
    def mock_base_client(self) -> MagicMock:
        """Create a mock BaseCheckmarxClient for testing."""
        return MagicMock(spec=BaseCheckmarxClient)

    @pytest.fixture
    def concrete_exporter(self, mock_base_client: MagicMock) -> AbstractCheckmarxExporter:
        """Create a concrete implementation of AbstractCheckmarxExporter for testing."""
        class ConcreteExporter(AbstractCheckmarxExporter):
            """Concrete implementation for testing."""
            pass

        return ConcreteExporter(mock_base_client)

    def test_init_with_client(self, mock_base_client: MagicMock) -> None:
        """Test that exporter is initialized with the provided client."""
        exporter = AbstractCheckmarxExporter.__new__(AbstractCheckmarxExporter)
        exporter.__init__(mock_base_client)

        assert exporter.client == mock_base_client

    def test_client_attribute_access(self, concrete_exporter: AbstractCheckmarxExporter, mock_base_client: MagicMock) -> None:
        """Test that the client attribute can be accessed."""
        assert concrete_exporter.client == mock_base_client

    def test_client_attribute_type(self, concrete_exporter: AbstractCheckmarxExporter) -> None:
        """Test that the client attribute is of the correct type."""
        assert isinstance(concrete_exporter.client, BaseCheckmarxClient)

    def test_exporter_is_abstract(self) -> None:
        """Test that AbstractCheckmarxExporter can be instantiated since it has no abstract methods."""
        # The class is not actually abstract since it has no abstract methods
        exporter = AbstractCheckmarxExporter(MagicMock(spec=BaseCheckmarxClient))
        assert exporter is not None
        assert hasattr(exporter, 'client')

    def test_exporter_inheritance(self, mock_base_client: MagicMock) -> None:
        """Test that concrete implementations properly inherit from the abstract class."""
        class TestExporter(AbstractCheckmarxExporter):
            """Test implementation."""
            pass

        exporter = TestExporter(mock_base_client)
        assert isinstance(exporter, AbstractCheckmarxExporter)

    def test_client_method_access(self, concrete_exporter: AbstractCheckmarxExporter, mock_base_client: MagicMock) -> None:
        """Test that methods can be called on the client through the exporter."""
        # Mock a method on the client
        mock_base_client.some_method = MagicMock(return_value="test_result")

        # Access through exporter
        result = concrete_exporter.client.some_method()
        assert result == "test_result"
        mock_base_client.some_method.assert_called_once()

    def test_exporter_with_different_client_types(self) -> None:
        """Test that exporter works with different client configurations."""
        class TestExporter(AbstractCheckmarxExporter):
            """Test implementation."""
            pass

        # Test with different mock configurations
        mock_client_1 = MagicMock(spec=BaseCheckmarxClient)
        mock_client_2 = MagicMock(spec=BaseCheckmarxClient)

        exporter_1 = TestExporter(mock_client_1)
        exporter_2 = TestExporter(mock_client_2)

        assert exporter_1.client == mock_client_1
        assert exporter_2.client == mock_client_2
        assert exporter_1.client != exporter_2.client

    def test_exporter_client_immutability(self, concrete_exporter: AbstractCheckmarxExporter, mock_base_client: MagicMock) -> None:
        """Test that the client reference cannot be changed after initialization."""
        original_client = concrete_exporter.client

        # Attempt to change the client (this should not affect the original)
        new_client = MagicMock(spec=BaseCheckmarxClient)
        concrete_exporter.client = new_client

        # The client should now be the new one
        assert concrete_exporter.client == new_client
        assert concrete_exporter.client != original_client

    def test_exporter_with_none_client(self) -> None:
        """Test that exporter raises appropriate error with None client."""
        class TestExporter(AbstractCheckmarxExporter):
            """Test implementation."""
            pass

        # This should work as the client is just stored as an attribute
        exporter = TestExporter(None)
        assert exporter.client is None

    def test_exporter_docstring(self) -> None:
        """Test that the abstract exporter has proper documentation."""
        assert AbstractCheckmarxExporter.__doc__ is not None
        assert "Abstract base class for Checkmarx One resource exporters" in AbstractCheckmarxExporter.__doc__
