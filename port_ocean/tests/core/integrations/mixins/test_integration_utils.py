from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.mixins.utils import (
    extract_jq_deletion_path_revised,
    handle_items_to_parse,
)

class TestExtractJqDeletionPathRevised:
    """Tests for extract_jq_deletion_path_revised function."""

    def test_simple_path(self) -> None:
        """Test extraction of simple path like .key."""
        result = extract_jq_deletion_path_revised(".file.content")
        assert result == ".file.content"

    def test_simple_single_key(self) -> None:
        """Test extraction of single key path."""
        result = extract_jq_deletion_path_revised(".key")
        assert result == ".key"

    def test_nested_path(self) -> None:
        """Test extraction of nested path."""
        result = extract_jq_deletion_path_revised(".file.content.raw")
        assert result == ".file.content.raw"

    def test_path_with_parentheses(self) -> None:
        """Test extraction with surrounding parentheses."""
        result = extract_jq_deletion_path_revised("(.file.content)")
        assert result == ".file.content"

    def test_path_with_pipe_segments(self) -> None:
        """Test extraction from pipe-separated expression."""
        result = extract_jq_deletion_path_revised(". as $all | .file.content")
        assert result == ".file.content"

    def test_path_with_variable_assignment_ignored(self) -> None:
        """Test that variable assignment segments are ignored."""
        result = extract_jq_deletion_path_revised(". as $root | .file.content")
        assert result == ".file.content"

    def test_path_with_variable_access_ignored(self) -> None:
        """Test that variable access like $items is ignored."""
        result = extract_jq_deletion_path_revised("$items | .file.content")
        assert result == ".file.content"

    def test_identity_operator_ignored(self) -> None:
        """Test that identity operator '.' is ignored."""
        result = extract_jq_deletion_path_revised(". | .file.content")
        assert result == ".file.content"

    def test_path_with_fallback_operator(self) -> None:
        """Test path extraction with fallback operator (//)."""
        result = extract_jq_deletion_path_revised(".file.content // {}")
        assert result == ".file.content"

    def test_path_with_fallback_to_null(self) -> None:
        """Test path extraction with fallback to null."""
        result = extract_jq_deletion_path_revised(".file.content // null")
        assert result == ".file.content"

    def test_path_with_fallback_to_empty_array(self) -> None:
        """Test path extraction with fallback to empty array."""
        result = extract_jq_deletion_path_revised(".file.content // []")
        assert result == ".file.content"

    def test_path_with_fallback_to_object(self) -> None:
        """Test path extraction with fallback to object."""
        result = extract_jq_deletion_path_revised(".file.content // {}")
        assert result == ".file.content"

    def test_path_with_bracketed_accessor(self) -> None:
        """Test path extraction with array index accessor."""
        result = extract_jq_deletion_path_revised(".[0].key")
        assert result == ".[0].key"

    def test_path_with_multiple_bracketed_accessors(self) -> None:
        """Test path extraction with multiple array index accessors."""
        result = extract_jq_deletion_path_revised(".[0].[1].key")
        assert result == ".[0].[1].key"

    def test_path_with_mixed_accessors(self) -> None:
        """Test path extraction with mixed key and bracket accessors."""
        result = extract_jq_deletion_path_revised(".file[0].content")
        assert result == ".file[0].content"

    def test_path_with_mixed_accessors_with_dots(self) -> None:
        """Test path extraction with mixed key and bracket accessors with dots."""
        result = extract_jq_deletion_path_revised(".file.[0].content")
        assert result == ".file.[0].content"

    def test_complex_pipe_expression(self) -> None:
        """Test extraction from complex pipe expression."""
        result = extract_jq_deletion_path_revised(
            ". as $all | ($all | .file.content) as $items | $items"
        )
        assert result == ".file.content"

    def test_path_in_parentheses_with_pipes(self) -> None:
        """Test path extraction from parenthesized expression with pipes."""
        result = extract_jq_deletion_path_revised("(. as $all | .file.content)")
        assert result == ".file.content"

    def test_no_path_returns_none(self) -> None:
        """Test that expression without path returns None."""
        result = extract_jq_deletion_path_revised("$items")
        assert result is None

    def test_only_identity_returns_none(self) -> None:
        """Test that expression with only identity operator returns None."""
        result = extract_jq_deletion_path_revised(".")
        assert result is None

    def test_only_variable_returns_none(self) -> None:
        """Test that expression with only variable returns None."""
        result = extract_jq_deletion_path_revised("$items")
        assert result is None

    def test_only_variable_assignment_returns_none(self) -> None:
        """Test that expression with only variable assignment returns None."""
        result = extract_jq_deletion_path_revised(". as $root")
        assert result is None

    def test_malformed_parentheses_returns_none(self) -> None:
        """Test that malformed parentheses return None."""
        result = extract_jq_deletion_path_revised("(.file.content")
        assert result is None

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly handled."""
        result = extract_jq_deletion_path_revised("  .file.content  ")
        assert result == ".file.content"

    def test_path_with_underscores(self) -> None:
        """Test path extraction with underscores in keys."""
        result = extract_jq_deletion_path_revised(".file_content.raw_data")
        assert result == ".file_content.raw_data"

    def test_path_with_numbers_in_keys(self) -> None:
        """Test path extraction with numbers in keys."""
        result = extract_jq_deletion_path_revised(".file2.content3")
        assert result == ".file2.content3"

    def test_deeply_nested_path(self) -> None:
        """Test extraction of deeply nested path."""
        result = extract_jq_deletion_path_revised(".a.b.c.d.e.f")
        assert result == ".a.b.c.d.e.f"

    def test_path_with_fallback_in_pipe(self) -> None:
        """Test path extraction with fallback in pipe expression."""
        result = extract_jq_deletion_path_revised(". as $all | .file.content // {}")
        assert result == ".file.content"

    def test_multiple_paths_returns_first(self) -> None:
        """Test that first valid path is returned when multiple exist."""
        result = extract_jq_deletion_path_revised(".first.path | .second.path")
        assert result == ".first.path"

    def test_path_with_complex_bracket_expression(self) -> None:
        """Test path extraction with complex bracket expression."""
        result = extract_jq_deletion_path_revised(".[\"key\"].value")
        assert result == ".[\"key\"].value"

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        result = extract_jq_deletion_path_revised("")
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string returns None."""
        result = extract_jq_deletion_path_revised("   ")
        assert result is None

    def test_real_world_file_content_path(self) -> None:
        """Test real-world scenario: file.content path."""
        result = extract_jq_deletion_path_revised(".file.content.raw")
        assert result == ".file.content.raw"

    def test_real_world_with_variable_and_fallback(self) -> None:
        """Test real-world scenario with variable and fallback."""
        result = extract_jq_deletion_path_revised(
            ". as $all | ($all | .file.content.raw) // {}"
        )
        assert result == ".file.content.raw"


class TestHandleItemsToParse:
    """Tests for handle_items_to_parse function with items_to_parse_top_level_transform flag.

    Uses the real JQEntityProcessor with actual jq execution.
    """

    @pytest.fixture
    def resource_config_with_transform(self) -> ResourceConfig:
        """Create a resource config with items_to_parse_top_level_transform=True (default)."""
        return ResourceConfig(
            kind="test-kind",
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                ),
                itemsToParse=".items",
                itemsToParseName="item",
                itemsToParseTopLevelTransform=True,
            ),
        )

    @pytest.fixture
    def resource_config_no_transform(self) -> ResourceConfig:
        """Create a resource config with items_to_parse_top_level_transform=False."""
        return ResourceConfig(
            kind="test-kind",
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                ),
                itemsToParse=".items",
                itemsToParseName="item",
                itemsToParseTopLevelTransform=False,
            ),
        )

    @pytest.mark.asyncio
    async def test_items_to_parse_top_level_transform_true_deletes_items_path(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_with_transform: ResourceConfig,
    ) -> None:
        """Test that when items_to_parse_top_level_transform is True, the items path is deleted from the item."""
        raw_data = [
            {
                "id": "1",
                "name": "test-parent",
                "metadata": {"key": "value"},
                "items": [{"sub_id": "a"}, {"sub_id": "b"}],
            }
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_with_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                batches.append(batch)

            assert len(batches) == 1
            assert len(batches[0]) == 2

            # Each merged item should NOT have 'items' key (deleted by jq)
            for merged_item in batches[0]:
                assert "items" not in merged_item
                assert "id" in merged_item
                assert merged_item["id"] == "1"
                assert "name" in merged_item
                assert "metadata" in merged_item
                assert "item" in merged_item

    @pytest.mark.asyncio
    async def test_items_to_parse_top_level_transform_false_preserves_items_path(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_no_transform: ResourceConfig,
    ) -> None:
        """Test that when items_to_parse_top_level_transform is False, the items path is preserved."""
        raw_data = [
            {
                "id": "1",
                "name": "test-parent",
                "metadata": {"key": "value"},
                "items": [{"sub_id": "a"}, {"sub_id": "b"}],
            }
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_no_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                batches.append(batch)

            assert len(batches) == 1
            assert len(batches[0]) == 2

            # Each merged item SHOULD have 'items' key (not deleted)
            for merged_item in batches[0]:
                assert "items" in merged_item
                assert merged_item["items"] == [{"sub_id": "a"}, {"sub_id": "b"}]
                assert "id" in merged_item
                assert "name" in merged_item
                assert "metadata" in merged_item
                assert "item" in merged_item

    @pytest.mark.asyncio
    async def test_items_to_parse_top_level_transform_default_is_true(self) -> None:
        """Test that items_to_parse_top_level_transform defaults to True."""
        resource_config = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                ),
                itemsToParse=".items",
            ),
        )
        assert resource_config.port.items_to_parse_top_level_transform is True

    @pytest.mark.asyncio
    async def test_items_to_parse_with_nested_path_and_transform(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_with_transform: ResourceConfig,
    ) -> None:
        """Test items_to_parse with nested path when transform is True."""
        raw_data = [
            {
                "id": "1",
                "name": "test",
                "data": {"nested": {"items": [{"sub_id": "a"}, {"sub_id": "b"}]}},
            }
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_with_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(
                raw_data, "item", ".data.nested.items"
            ):
                batches.append(batch)

            assert len(batches) == 1
            assert len(batches[0]) == 2

            # Verify the nested path was deleted
            for merged_item in batches[0]:
                assert "item" in merged_item
                assert merged_item["id"] == "1"
                # The nested items should be deleted
                assert (
                    merged_item.get("data", {}).get("nested", {}).get("items") is None
                )

    @pytest.mark.asyncio
    async def test_items_to_parse_with_multiple_parents(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_with_transform: ResourceConfig,
    ) -> None:
        """Test handling multiple parent items with items_to_parse_top_level_transform."""
        raw_data = [
            {"id": "1", "items": [{"sub_id": "a"}]},
            {"id": "2", "items": [{"sub_id": "b"}, {"sub_id": "c"}]},
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_with_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            all_items: list[dict[str, Any]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                all_items.extend(batch)

            assert len(all_items) == 3
            # Verify parent data is correctly associated
            assert all_items[0]["id"] == "1"
            assert all_items[0]["item"]["sub_id"] == "a"
            assert all_items[1]["id"] == "2"
            assert all_items[1]["item"]["sub_id"] == "b"
            assert all_items[2]["id"] == "2"
            assert all_items[2]["item"]["sub_id"] == "c"

    @pytest.mark.asyncio
    async def test_items_to_parse_skips_non_list_data(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_with_transform: ResourceConfig,
    ) -> None:
        """Test that non-list items_to_parse data is skipped with a warning."""
        raw_data = [
            {"id": "1", "items": "not-a-list"},
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_with_transform),
            ),
            patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger,
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                batches.append(batch)

            # Should have no batches since item was skipped
            assert len(batches) == 0
            # Warning should have been logged
            mock_logger.warning.assert_called_once()
            assert "Expected list" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_items_to_parse_verifies_actual_jq_deletion(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_with_transform: ResourceConfig,
    ) -> None:
        """Test that the actual jq del() expression works correctly."""
        raw_data = [
            {
                "id": "1",
                "keep_this": "should stay",
                "items": [{"sub_id": "a"}],
                "also_keep": 123,
            }
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_with_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                batches.append(batch)

            assert len(batches) == 1
            merged_item = batches[0][0]

            # Verify items was deleted but other fields remain
            assert "items" not in merged_item
            assert merged_item["id"] == "1"
            assert merged_item["keep_this"] == "should stay"
            assert merged_item["also_keep"] == 123
            assert merged_item["item"] == {"sub_id": "a"}

    @pytest.mark.asyncio
    async def test_items_to_parse_no_transform_preserves_all_fields(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
        resource_config_no_transform: ResourceConfig,
    ) -> None:
        """Test that with transform=False, all original fields are preserved including items."""
        raw_data = [
            {
                "id": "1",
                "keep_this": "should stay",
                "items": [{"sub_id": "a"}],
                "also_keep": 123,
            }
        ]

        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean_context,
            patch(
                "port_ocean.core.integrations.mixins.utils.event",
                SimpleNamespace(resource_config=resource_config_no_transform),
            ),
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items"):
                batches.append(batch)

            assert len(batches) == 1
            merged_item = batches[0][0]

            # Verify all fields remain including items
            assert merged_item["items"] == [{"sub_id": "a"}]
            assert merged_item["id"] == "1"
            assert merged_item["keep_this"] == "should stay"
            assert merged_item["also_keep"] == 123
            assert merged_item["item"] == {"sub_id": "a"}
