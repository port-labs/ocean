from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.raw_enricher import (
    BaseRawEnricher,
    MappingRefRawEnricher,
)
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.core.utils.mapping_refs import (
    collect_mapping_refs,
    rewrite_mapping_refs,
)


def _resource(**properties: str) -> ResourceConfig:
    return ResourceConfig(
        kind="file",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".path",
                    blueprint='"file"',
                    properties=properties,
                )
            )
        ),
    )


class RecordingEnricher(MappingRefRawEnricher):
    def __init__(self) -> None:
        super().__init__(MagicMock())
        self.calls: list[tuple[str, str]] = []

    async def resolve_file_ref(self, item: RAW_ITEM, path: str) -> Any:
        self.calls.append(("file", path))
        if path == "broken.json":
            raise RuntimeError("fetch failed")
        return f"{item['path']}/{path}"

    async def resolve_search_ref(self, item: RAW_ITEM, query: str) -> Any:
        self.calls.append(("search", query))
        return query == "name=found"


def test_rewrite_mapping_refs_replaces_only_ref_values() -> None:
    mapping = {
        "identifier": ".path",
        "properties": {
            "readme": " file://docs/README.md ",
            "exists": 'search://name="x y"',
            "plain": ".file.content",
        },
        "relations": {"items": ["file://a.json", ".b"]},
    }

    assert rewrite_mapping_refs(mapping) == {
        "identifier": ".path",
        "properties": {
            "readme": '.__includedFiles["docs/README.md"]',
            "exists": '.__search["name=\\"x y\\""]',
            "plain": ".file.content",
        },
        "relations": {"items": ['.__includedFiles["a.json"]', ".b"]},
    }


def test_collect_mapping_refs_finds_nested_refs() -> None:
    refs = collect_mapping_refs(
        {"a": "file://x", "b": ["search://q", {"c": "file://y"}], "d": ".plain"}
    )

    assert refs.files == {"x", "y"}
    assert refs.searches == {"q"}
    assert not collect_mapping_refs({"a": ".plain"})


@pytest.mark.asyncio
async def test_base_enricher_returns_items_unchanged() -> None:
    items = [{"path": "a"}]

    assert await BaseRawEnricher(MagicMock()).enrich(_resource(), items) is items


@pytest.mark.asyncio
async def test_mapping_ref_enricher_attaches_resolved_refs_per_item() -> None:
    enricher = RecordingEnricher()
    resource = _resource(
        readme="file://README.md",
        found="search://name=found",
        plain=".name",
    )

    items = await enricher.enrich(resource, [{"path": "a"}, {"path": "b"}])

    assert items == [
        {
            "path": "a",
            "__includedFiles": {"README.md": "a/README.md"},
            "__search": {"name=found": True},
        },
        {
            "path": "b",
            "__includedFiles": {"README.md": "b/README.md"},
            "__search": {"name=found": True},
        },
    ]


@pytest.mark.asyncio
async def test_mapping_ref_enricher_without_refs_leaves_items_untouched() -> None:
    enricher = RecordingEnricher()

    items = await enricher.enrich(_resource(plain=".name"), [{"path": "a"}])

    assert items == [{"path": "a"}]
    assert enricher.calls == []


@pytest.mark.asyncio
async def test_mapping_ref_enricher_keeps_values_already_attached() -> None:
    enricher = RecordingEnricher()
    item = {"path": "a", "__includedFiles": {"README.md": "prefetched"}}

    [enriched] = await enricher.enrich(_resource(readme="file://README.md"), [item])

    assert enriched["__includedFiles"] == {"README.md": "prefetched"}
    assert "__search" not in enriched
    assert enricher.calls == []


@pytest.mark.asyncio
async def test_mapping_ref_enricher_maps_resolution_failures_to_null() -> None:
    enricher = RecordingEnricher()

    [enriched] = await enricher.enrich(
        _resource(config="file://broken.json"), [{"path": "a"}]
    )

    assert enriched["__includedFiles"] == {"broken.json": None}


@pytest.mark.asyncio
async def test_mapping_ref_enricher_raises_for_unsupported_ref_type() -> None:
    enricher = MappingRefRawEnricher(MagicMock())

    with pytest.raises(NotImplementedError, match="file://"):
        await enricher.enrich(_resource(readme="file://README.md"), [{"path": "a"}])


@pytest.mark.asyncio
async def test_mapping_ref_enricher_logs_deprecation_for_each_ref() -> None:
    enricher = RecordingEnricher()
    resource = _resource(readme="file://README.md", found="search://name=found")

    with patch("port_ocean.core.handlers.raw_enricher.logger") as mock_logger:
        await enricher.enrich(resource, [{"path": "a"}, {"path": "b"}])

    warnings = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert len(warnings) == 2
    assert "file://README.md" in warnings[0] and "includedFiles" in warnings[0]
    assert "search://name=found" in warnings[1] and "searchQueries" in warnings[1]


@pytest.mark.asyncio
async def test_mapping_ref_enricher_without_refs_logs_no_deprecation() -> None:
    with patch("port_ocean.core.handlers.raw_enricher.logger") as mock_logger:
        await RecordingEnricher().enrich(_resource(plain=".name"), [{"path": "a"}])

    mock_logger.warning.assert_not_called()
