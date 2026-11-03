from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)

from gitlab_integration.raw_enricher import GitlabRawEnricher, parse_search_query

MODULE = "gitlab_integration.raw_enricher"


def _resource(properties: dict[str, str]) -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    blueprint='"service"',
                    properties=properties,
                )
            )
        ),
    )


@pytest.fixture
def project() -> Any:
    project = MagicMock(path_with_namespace="org/repo")
    with patch(f"{MODULE}._get_project_from_cache", return_value=project):
        yield project


def test_parse_search_query() -> None:
    assert parse_search_query("scope=blobs&&query=filename:port.yml") == (
        "blobs",
        "filename:port.yml",
    )
    with pytest.raises(ValueError):
        parse_search_query("scope=blobs")


@pytest.mark.asyncio
async def test_resolves_file_refs_under_folder_path(project: Any) -> None:
    item = {"repo": {"id": 1}, "__branch": "main", "folder": {"path": "svc"}}
    fetched = MagicMock()
    fetched.decode.return_value = b"readme content"

    with patch(
        f"{MODULE}.AsyncFetcher.fetch_single",
        new_callable=AsyncMock,
        return_value=fetched,
    ) as fetch:
        [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
            _resource({"readme": "file://README.md"}), [item]
        )

    assert enriched["__includedFiles"] == {"README.md": "readme content"}
    fetch.assert_awaited_once_with(project.files.get, "svc/README.md", "main")


@pytest.mark.asyncio
async def test_resolves_blob_search_scoped_to_folder(project: Any) -> None:
    query = "scope=blobs&&query=filename:port.yml"
    item = {"id": 1, "default_branch": "main", "folder": {"path": "svc"}}

    with patch(
        f"{MODULE}.AsyncFetcher.fetch_single",
        new_callable=AsyncMock,
        return_value=[{"path": "svc/port.yml"}],
    ) as fetch:
        [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
            _resource({"hasPort": f"search://{query}"}), [item]
        )

    assert enriched["__search"] == {query: True}
    fetch.assert_awaited_once_with(
        project.search, "blobs", "filename:port.yml path:svc"
    )


@pytest.mark.asyncio
async def test_item_without_project_scope_maps_as_null(project: Any) -> None:
    [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [{"name": "no-id"}]
    )

    assert enriched["__includedFiles"] == {"README.md": None}
