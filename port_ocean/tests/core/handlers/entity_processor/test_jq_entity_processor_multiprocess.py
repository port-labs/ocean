"""Tests for the multiprocess JQ entity processing functions.

These tests cover the module-level synchronous functions that are designed
to run in separate processes for parallel JQ processing.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
    MappedEntity,
    _calculate_entity,
)
import port_ocean.core.handlers.entity_processor.jq_entity_processor as jq_module


class TestCalculateEntity:
    """Test the _calculate_entity function for entity calculation from globals."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            # Set up a real JQEntityProcessor so _get_mapped_entity works correctly
            mock_context = MagicMock()
            entity_processor = JQEntityProcessor(mock_context)
            mock_ocean.integration.entity_processor = entity_processor
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_calculate_entity_from_globals(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity using global batch data."""
        # Set up globals
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "bar"}
        assert entities[0].did_entity_pass_selector is True
        assert len(errors) == 0

    def test_calculate_entity_with_failed_selector(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity when selector fails."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "false"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {}
        assert entities[0].did_entity_pass_selector is False
        assert len(errors) == 0

    def test_calculate_entity_multiple_items(self, setup_mock_ocean: Any) -> None:
        """Test calculating entities from multiple items."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [
            {"id": "1", "name": "first"},
            {"id": "2", "name": "second"},
            {"id": "3", "name": "third"},
        ]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {
            "identifier": ".id",
            "title": ".name",
        }
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Calculate each entity separately (as would happen in multiprocess)
        results = [_calculate_entity(i) for i in range(3)]

        assert len(results) == 3
        assert results[0][0][0].entity == {"identifier": "1", "title": "first"}
        assert results[1][0][0].entity == {"identifier": "2", "title": "second"}
        assert results[2][0][0].entity == {"identifier": "3", "title": "third"}

    def test_calculate_entity_with_parse_all(self, setup_mock_ocean: Any) -> None:
        """Test calculating entity with parse_all=True."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [{"foo": "bar"}]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {"identifier": ".foo"}
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "false"  # Would normally skip
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = True

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity == {"identifier": "bar"}
        # Entity should still be mapped even though selector is false
        assert entities[0].did_entity_pass_selector is False
        assert len(errors) == 0

    def test_calculate_entity_with_complex_selector(
        self, setup_mock_ocean: Any
    ) -> None:
        """Test calculating entity with complex selector query."""
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = [
            {"status": "active", "type": "service"},
            {"status": "inactive", "type": "service"},
        ]
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = {
            "identifier": ".type",
            "properties": {"status": ".status"},
        }
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = '.status == "active"'
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities_0, _ = _calculate_entity(0)
        entities_1, _ = _calculate_entity(1)

        # First entity should pass selector
        assert entities_0[0].did_entity_pass_selector is True
        assert entities_0[0].entity == {
            "identifier": "service",
            "properties": {"status": "active"},
        }

        # Second entity should fail selector
        assert entities_1[0].did_entity_pass_selector is False
        assert entities_1[0].entity == {}


class TestMappedEntity:
    """Test the MappedEntity dataclass."""

    def test_default_values(self) -> None:
        """Test MappedEntity default values."""
        entity = MappedEntity()
        assert entity.entity == {}
        assert entity.did_entity_pass_selector is False
        assert entity.misconfigurations == {}

    def test_custom_values(self) -> None:
        """Test MappedEntity with custom values."""
        entity = MappedEntity(
            entity={"id": "123"},
            did_entity_pass_selector=True,
            misconfigurations={"field": ".missing"},
        )
        assert entity.entity == {"id": "123"}
        assert entity.did_entity_pass_selector is True
        assert entity.misconfigurations == {"field": ".missing"}


class TestIntegration:
    """Integration tests for the multiprocess JQ processing functions."""

    @pytest.fixture(autouse=True)
    def setup_mock_ocean(self) -> Any:
        """Set up mock ocean config."""
        with patch(
            "port_ocean.core.handlers.entity_processor.jq_entity_processor.ocean"
        ) as mock_ocean:
            mock_ocean.config = MagicMock()
            mock_ocean.config.allow_environment_variables_jq_access = True
            # Set up a real JQEntityProcessor so _get_mapped_entity works correctly
            mock_context = MagicMock()
            entity_processor = JQEntityProcessor(mock_context)
            mock_ocean.integration.entity_processor = entity_processor
            jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()
            yield mock_ocean

    def test_full_entity_processing_flow(self, setup_mock_ocean: Any) -> None:
        """Test the full entity processing flow from raw data to mapped entity."""
        # Simulate the flow that happens in multiprocess
        raw_data = [
            {
                "id": "service-1",
                "name": "My Service",
                "type": "microservice",
                "metadata": {"owner": "team-a", "tier": "critical"},
            },
            {
                "id": "service-2",
                "name": "Another Service",
                "type": "monolith",
                "metadata": {"owner": "team-b", "tier": "standard"},
            },
        ]

        mappings = {
            "identifier": ".id",
            "title": ".name",
            "blueprint": '"service"',
            "properties": {
                "type": ".type",
                "owner": ".metadata.owner",
                "tier": ".metadata.tier",
            },
        }

        selector = '.metadata.tier == "critical"'

        # Set up globals
        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = selector
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Process entities
        results = [_calculate_entity(i) for i in range(len(raw_data))]

        # First entity should pass (tier == critical)
        assert results[0][0][0].did_entity_pass_selector is True
        assert results[0][0][0].entity["identifier"] == "service-1"
        assert results[0][0][0].entity["title"] == "My Service"
        assert results[0][0][0].entity["properties"]["tier"] == "critical"

        # Second entity should fail (tier != critical)
        assert results[1][0][0].did_entity_pass_selector is False
        assert results[1][0][0].entity == {}

    def test_processing_with_misconfigurations(self, setup_mock_ocean: Any) -> None:
        """Test processing that results in misconfigurations."""
        raw_data = [
            {
                "id": "123",
                "name": "Test",
                # missing 'url' field
            }
        ]

        mappings = {
            "identifier": ".id",
            "title": ".name",
            "properties": {
                "url": ".url",  # Will be None
                "description": ".description",  # Will also be None
            },
        }

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert len(entities) == 1
        assert entities[0].entity["identifier"] == "123"
        assert entities[0].entity["title"] == "Test"
        assert entities[0].entity["properties"]["url"] is None
        assert entities[0].entity["properties"]["description"] is None
        # Should have misconfigurations for the missing fields
        assert "url" in entities[0].misconfigurations
        assert "description" in entities[0].misconfigurations

    def test_processing_with_array_data(self, setup_mock_ocean: Any) -> None:
        """Test processing data that contains arrays."""
        raw_data = [
            {
                "id": "repo-1",
                "tags": ["python", "backend", "api"],
                "contributors": [
                    {"name": "Alice", "role": "owner"},
                    {"name": "Bob", "role": "contributor"},
                ],
            }
        ]

        mappings = {
            "identifier": ".id",
            "properties": {
                "tags": ".tags",
                "owner": '.contributors[] | select(.role == "owner") | .name',
            },
        }

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        entities, errors = _calculate_entity(0)

        assert entities[0].entity["identifier"] == "repo-1"
        assert entities[0].entity["properties"]["tags"] == ["python", "backend", "api"]
        assert entities[0].entity["properties"]["owner"] == "Alice"

    def test_caching_improves_performance(self, setup_mock_ocean: Any) -> None:
        """Test that pattern caching works across multiple entities."""
        raw_data = [{"id": str(i), "value": i} for i in range(100)]

        mappings = {"identifier": ".id", "count": ".value"}

        jq_module._MULTIPROCESS_JQ_BATCH_DATA = raw_data
        jq_module._MULTIPROCESS_JQ_BATCH_MAPPINGS = mappings
        jq_module._MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = "true"
        jq_module._MULTIPROCESS_JQ_BATCH_PARSE_ALL = False

        # Clear cache to start fresh
        jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS.clear()

        # Process all entities
        for i in range(len(raw_data)):
            _calculate_entity(i)

        # Cache should have the patterns compiled once
        # There should be limited patterns (the unique ones used)
        assert len(jq_module._MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS) <= 3
