from typing import Any
from unittest.mock import AsyncMock, patch

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
from port_ocean.core.models import IntegrationFeatureFlag, ProcessingMode
from port_ocean.core.integrations.mixins.utils import (
    build_lakehouse_data_entry,
    collect_export_env_variables,
    extract_jq_deletion_path_revised,
    handle_items_to_parse,
    is_dsp_mode_enabled,
    is_lakehouse_data_enabled,
    is_redis_live_events_enabled,
    resync_function_wrapper,
    resync_generator_wrapper,
    selector_hash_from_query,
    selector_hash_from_resource,
    selector_query_from_resource,
)
from port_ocean.core.models import LakehouseOperation

class TestCollectExportEnvVariables:
    def test_returns_none_for_empty_list(self) -> None:
        assert collect_export_env_variables([]) is None

    def test_collects_requested_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOO", "bar")
        monkeypatch.delenv("MISSING", raising=False)

        assert collect_export_env_variables(["FOO", "MISSING"]) == {
            "FOO": "bar",
            "MISSING": None,
        }


class TestBuildLakehouseDataEntry:
    def test_includes_environment_data_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOO", "bar")

        entry = build_lakehouse_data_entry(
            items=[{"id": "1"}],
            metadata={
                "operation": LakehouseOperation.UPSERT,
                "resource_index": 0,
                "extraction_timestamp": 123,
            },
            export_env_variables=["FOO"],
        )

        assert entry["environment_data"] == {"FOO": "bar"}

    def test_omits_environment_data_when_not_configured(self) -> None:
        entry = build_lakehouse_data_entry(
            items=[{"id": "1"}],
            metadata={
                "operation": LakehouseOperation.UPSERT,
                "resource_index": 0,
                "extraction_timestamp": 123,
            },
            export_env_variables=[],
        )

        assert "environment_data" not in entry


class TestSelectorHashHelpers:
    def test_selector_query_from_resource_returns_trimmed_query(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="  .foo | .bar  "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_query_from_resource(resource) == ".foo | .bar"

    def test_selector_query_from_resource_returns_none_for_whitespace(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="   "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_query_from_resource(resource) is None

    def test_selector_hash_from_query_uses_sha256_hex(self) -> None:
        assert (
            selector_hash_from_query(".foo")
            == "013b54afaf52ac0983a4ac123b01e809ab7ac8862e67a50f09fcce1293d265c3"
        )

    def test_selector_hash_from_resource_returns_hash_for_trimmed_query(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="  .foo  "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert (
            selector_hash_from_resource(resource)
            == "013b54afaf52ac0983a4ac123b01e809ab7ac8862e67a50f09fcce1293d265c3"
        )

    def test_selector_hash_from_resource_returns_none_for_empty_query(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=" "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_hash_from_resource(resource) is None


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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", True):
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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", False):
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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(
                raw_data, "item", ".data.nested.items", True
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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            all_items: list[dict[str, Any]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", True):
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
            patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger,
        ):
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", True):
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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", True):
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

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor

            batches: list[list[dict[str, Any]]] = []
            async for batch in handle_items_to_parse(raw_data, "item", ".items", False):
                batches.append(batch)

            assert len(batches) == 1
            merged_item = batches[0][0]

            # Verify all fields remain including items
            assert merged_item["items"] == [{"sub_id": "a"}]
            assert merged_item["id"] == "1"
            assert merged_item["keep_this"] == "should stay"
            assert merged_item["also_keep"] == 123
            assert merged_item["item"] == {"sub_id": "a"}


class TestResyncGeneratorWrapperDoesNotMutateYieldedBatches:
    """Regression test: resync_generator_wrapper must not mutate the lists
    yielded by integration generators.

    When itemsToParse is enabled, handle_items_to_parse iterates over the
    result list. The original list reference from the integration's generator
    must remain intact so the generator can still inspect it (e.g. read
    len(items) for pagination decisions) after yielding.
    """

    @pytest.mark.asyncio
    async def test_items_to_parse_does_not_mutate_original_list(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
    ) -> None:
        """Verify that the list yielded by the integration generator is not
        mutated after handle_items_to_parse processes it."""
        # The list that the integration generator yields
        original_batch = [
            {"id": "1", "items": [{"sub_id": "a"}]},
            {"id": "2", "items": [{"sub_id": "b"}]},
        ]
        original_length = len(original_batch)

        async def fake_generator(kind: str) -> Any:
            yield original_batch

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor
            mock_ocean_context.metrics = mock_context.app.metrics

            async for _batch in resync_generator_wrapper(
                fake_generator,
                "test-kind",
                items_to_parse_name="item",
                items_to_parse=".items",
            ):
                pass

            # The original list must NOT have been mutated
            assert len(original_batch) == original_length

    @pytest.mark.asyncio
    async def test_items_to_parse_sends_examples_before_expansion(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
    ) -> None:
        original_batch = [
            {
                "id": "1",
                "keep_this": "should stay",
                "items": [{"sub_id": "a"}, {"sub_id": "b"}],
            }
        ]

        async def fake_generator(kind: str) -> Any:
            yield original_batch

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor
            mock_ocean_context.metrics = mock_context.app.metrics
            mock_ocean_context.port_client.ingest_integration_kind_examples = AsyncMock()

            expanded_batches = [
                batch
                async for batch in resync_generator_wrapper(
                    fake_generator,
                    "test-kind",
                    items_to_parse_name="item",
                    items_to_parse=".items",
                    send_raw_data_examples_amount=1,
                )
            ]

            mock_ocean_context.port_client.ingest_integration_kind_examples.assert_awaited_once_with(
                "test-kind",
                [
                    {
                        "id": "1",
                        "keep_this": "should stay",
                        "items": [{"sub_id": "a"}, {"sub_id": "b"}],
                    }
                ],
                should_log=False,
            )
            assert expanded_batches == [
                [
                    {"id": "1", "keep_this": "should stay", "item": {"sub_id": "a"}},
                    {"id": "1", "keep_this": "should stay", "item": {"sub_id": "b"}},
                ]
            ]

    @pytest.mark.asyncio
    async def test_resync_function_wrapper_sends_examples_before_parsing(
        self,
    ) -> None:
        raw_results = [{"id": "1"}, {"id": "2"}]

        async def fake_resync(kind: str) -> list[dict[str, Any]]:
            return raw_results

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.port_client.ingest_integration_kind_examples = AsyncMock()

            result = await resync_function_wrapper(
                fake_resync,
                "test-kind",
                send_raw_data_examples_amount=1,
            )

            assert result == raw_results
            mock_ocean_context.port_client.ingest_integration_kind_examples.assert_awaited_once_with(
                "test-kind", [{"id": "1"}], should_log=False
            )

    @pytest.mark.asyncio
    async def test_resync_generator_wrapper_sends_examples_without_items_to_parse(
        self,
    ) -> None:
        raw_results = [{"id": "1"}, {"id": "2"}]

        async def fake_generator(kind: str) -> Any:
            yield raw_results

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.port_client.ingest_integration_kind_examples = AsyncMock()

            batches = [
                batch
                async for batch in resync_generator_wrapper(
                    fake_generator,
                    "test-kind",
                    items_to_parse_name="item",
                    send_raw_data_examples_amount=1,
                )
            ]

            assert batches == [raw_results]
            mock_ocean_context.port_client.ingest_integration_kind_examples.assert_awaited_once_with(
                "test-kind", [{"id": "1"}], should_log=False
            )

    @pytest.mark.asyncio
    async def test_items_to_parse_retries_examples_on_later_batch_after_failure(
        self,
        mock_context: PortOceanContext,
        mock_entity_processor: JQEntityProcessor,
    ) -> None:
        first_batch = [{"id": "1", "items": [{"sub_id": "a"}]}]
        second_batch = [{"id": "2", "items": [{"sub_id": "b"}]}]

        async def fake_generator(kind: str) -> Any:
            yield first_batch
            yield second_batch

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.yield_items_to_parse_batch_size = 100
            mock_ocean_context.app.integration.entity_processor = mock_entity_processor
            mock_ocean_context.metrics = mock_context.app.metrics
            mock_ocean_context.port_client.ingest_integration_kind_examples = AsyncMock(
                side_effect=[Exception("temporary failure"), None]
            )

            _expanded_batches = [
                batch
                async for batch in resync_generator_wrapper(
                    fake_generator,
                    "test-kind",
                    items_to_parse_name="item",
                    items_to_parse=".items",
                    send_raw_data_examples_amount=1,
                )
            ]

            assert (
                mock_ocean_context.port_client.ingest_integration_kind_examples.await_count
                == 2
            )
            calls = (
                mock_ocean_context.port_client.ingest_integration_kind_examples.await_args_list
            )
            assert calls[0].args == (
                "test-kind",
                [{"id": "1", "items": [{"sub_id": "a"}]}],
            )
            assert calls[0].kwargs == {"should_log": False}
            assert calls[1].args == (
                "test-kind",
                [{"id": "2", "items": [{"sub_id": "b"}]}],
            )
            assert calls[1].kwargs == {"should_log": False}


class TestProcessingModes:
    @pytest.mark.asyncio
    async def test_is_dsp_mode_enabled_uses_local_only_warning_for_missing_flags(
        self,
    ) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.config.processing_mode = ProcessingMode.dsp
            mock_ocean_context.config.lakehouse_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[]
            )

            with patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_dsp_mode_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "required feature flags are missing" in mock_bound.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_is_dsp_mode_enabled_uses_local_only_warning_when_lakehouse_disabled(
        self,
    ) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.config.processing_mode = ProcessingMode.dsp
            mock_ocean_context.config.lakehouse_enabled = False

            with patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_dsp_mode_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "lakehouse_enabled is False" in mock_bound.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_is_dsp_mode_enabled_uses_local_only_warning_on_exception(
        self,
    ) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.config.processing_mode = ProcessingMode.dsp
            mock_ocean_context.config.lakehouse_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                side_effect=Exception("connection error")
            )

            with patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_dsp_mode_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "Failed to check DSP mode" in mock_bound.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_is_lakehouse_data_enabled_uses_local_only_warning_on_exception(
        self,
    ) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                side_effect=Exception("timeout")
            )

            with patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_lakehouse_data_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "Failed to check lakehouse feature flags" in mock_bound.warning.call_args.args[0]

    @pytest.mark.asyncio
    async def test_is_redis_live_events_enabled_when_flag_on(self) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.LIVE_EVENTS_REDIS_STREAM_ENABLED]
            )

            result = await is_redis_live_events_enabled()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_redis_live_events_disabled_when_flag_off(self) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[]
            )

            result = await is_redis_live_events_enabled()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_redis_live_events_enabled_uses_local_only_warning_on_exception(
        self,
    ) -> None:
        with patch("port_ocean.core.integrations.mixins.utils.ocean") as mock_ocean_context:
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                side_effect=Exception("timeout")
            )

            with patch("port_ocean.core.integrations.mixins.utils.logger") as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_redis_live_events_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "Failed to check Redis live events feature flags" in (
            mock_bound.warning.call_args.args[0]
        )
