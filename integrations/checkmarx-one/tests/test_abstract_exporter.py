import pytest
from abc import ABC
from unittest.mock import MagicMock

from checkmarx_one.core.exporters.abstract_exporter import AbstractCheckmarxExporter
from client import CheckmarxClient


class TestAbstractCheckmarxExporter:
    def test_is_abstract_base_class(self):
        """Test that AbstractCheckmarxExporter is an abstract base class."""
        assert issubclass(AbstractCheckmarxExporter, ABC)

        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            AbstractCheckmarxExporter(MagicMock())

    def test_constructor_stores_client(self):
        """Test that constructor properly stores the client."""
        # Create a concrete implementation for testing
        class ConcreteExporter(AbstractCheckmarxExporter):
            async def get_resource(self, options):
                return {}

            def get_paginated_resources(self, options=None):
                async def mock_generator():
                    yield []
                return mock_generator()

        mock_client = MagicMock(spec=CheckmarxClient)
        exporter = ConcreteExporter(mock_client)

        assert exporter.client is mock_client

    def test_has_required_abstract_methods(self):
        """Test that abstract class has required abstract methods."""
        abstract_methods = AbstractCheckmarxExporter.__abstractmethods__

        assert "get_resource" in abstract_methods
        assert "get_paginated_resources" in abstract_methods
        assert len(abstract_methods) == 2

    def test_concrete_implementation_must_implement_abstract_methods(self):
        """Test that concrete implementations must implement all abstract methods."""
        # Class missing get_resource
        class IncompleteExporter1(AbstractCheckmarxExporter):
            def get_paginated_resources(self, options=None):
                pass

        with pytest.raises(TypeError):
            IncompleteExporter1(MagicMock())

        # Class missing get_paginated_resources
        class IncompleteExporter2(AbstractCheckmarxExporter):
            async def get_resource(self, options):
                pass

        with pytest.raises(TypeError):
            IncompleteExporter2(MagicMock())

    def test_concrete_implementation_can_be_instantiated(self):
        """Test that properly implemented concrete class can be instantiated."""
        class CompleteExporter(AbstractCheckmarxExporter):
            async def get_resource(self, options):
                return {"id": "test"}

            def get_paginated_resources(self, options=None):
                async def mock_generator():
                    yield [{"id": "test"}]
                return mock_generator()

        mock_client = MagicMock(spec=CheckmarxClient)
        exporter = CompleteExporter(mock_client)

        assert isinstance(exporter, AbstractCheckmarxExporter)
        assert exporter.client is mock_client

    def test_generic_type_annotations(self):
        """Test that abstract methods have proper generic type annotations."""
        # Check that get_resource has generic type annotation
        get_resource_annotations = AbstractCheckmarxExporter.get_resource.__annotations__
        assert 'options' in get_resource_annotations

        # Check that get_paginated_resources has generic type annotation
        get_paginated_annotations = AbstractCheckmarxExporter.get_paginated_resources.__annotations__
        assert 'options' in get_paginated_annotations

    def test_method_signatures(self):
        """Test that abstract methods have correct signatures."""
        import inspect

        # Test get_resource signature
        get_resource_sig = inspect.signature(AbstractCheckmarxExporter.get_resource)
        params = list(get_resource_sig.parameters.keys())
        assert params == ['self', 'options']

        # Test get_paginated_resources signature
        get_paginated_sig = inspect.signature(AbstractCheckmarxExporter.get_paginated_resources)
        params = list(get_paginated_sig.parameters.keys())
        assert params == ['self', 'options']

        # Test that options has default value None
        options_param = get_paginated_sig.parameters['options']
        assert options_param.default is None

    def test_inheritance_hierarchy(self):
        """Test the inheritance hierarchy."""
        assert AbstractCheckmarxExporter.__bases__ == (ABC,)
        assert hasattr(AbstractCheckmarxExporter, '__abstractmethods__')

    def test_docstring_exists(self):
        """Test that the abstract class has a docstring."""
        assert AbstractCheckmarxExporter.__doc__ == "Abstract base class for Checkmarx One resource exporters."

    def test_abstract_method_docstrings(self):
        """Test that abstract methods have docstrings."""
        assert AbstractCheckmarxExporter.get_resource.__doc__ == "Get a single resource by its identifier."
        assert AbstractCheckmarxExporter.get_paginated_resources.__doc__ == "Get paginated resources yielding batches."
