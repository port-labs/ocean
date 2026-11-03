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

from gitlab.raw_enricher import GitlabRawEnricher


def _resource(properties: dict[str, str]) -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".path_with_namespace",
                    blueprint='"service"',
                    properties=properties,
                )
            )
        ),
    )


@pytest.fixture
def gitlab_client() -> Any:
    client = MagicMock()
    client.get_file_content = AsyncMock(return_value="readme content")
    client.file_exists = AsyncMock(return_value=True)
    with patch("gitlab.raw_enricher.create_gitlab_client", return_value=client):
        yield client


@pytest.mark.asyncio
async def test_resolves_file_refs_against_default_branch(gitlab_client: Any) -> None:
    item = {"path_with_namespace": "org/repo", "default_branch": "main"}

    [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [item]
    )

    assert enriched["__includedFiles"] == {"README.md": "readme content"}
    gitlab_client.get_file_content.assert_awaited_once_with(
        "org/repo", "README.md", "main"
    )


@pytest.mark.asyncio
async def test_resolves_file_refs_from_nested_repo(gitlab_client: Any) -> None:
    item = {"repo": {"path_with_namespace": "org/repo", "default_branch": "dev"}}

    await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [item]
    )

    gitlab_client.get_file_content.assert_awaited_once_with(
        "org/repo", "README.md", "dev"
    )


@pytest.mark.asyncio
async def test_resolves_search_refs(gitlab_client: Any) -> None:
    query = "scope=blobs&&query=filename:port.yml"
    item = {"path_with_namespace": "org/repo"}

    [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"hasPort": f"search://{query}"}), [item]
    )

    assert enriched["__search"] == {query: True}
    gitlab_client.file_exists.assert_awaited_once_with(
        "org/repo", "blobs", "filename:port.yml"
    )


@pytest.mark.asyncio
async def test_unresolvable_ref_maps_as_null(gitlab_client: Any) -> None:
    [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [{"id": 1}]
    )

    assert enriched["__includedFiles"] == {"README.md": None}
    gitlab_client.get_file_content.assert_not_called()


@pytest.mark.asyncio
async def test_logs_deprecation_warning_per_ref(gitlab_client: Any) -> None:
    with patch("gitlab.raw_enricher.logger") as mock_logger:
        await GitlabRawEnricher(MagicMock()).enrich(
            _resource(
                {
                    "readme": "file://README.md",
                    "hasPort": "search://scope=blobs&&query=filename:port.yml",
                }
            ),
            [{"path_with_namespace": "org/repo", "default_branch": "main"}],
        )

    warnings = [call.args[0] for call in mock_logger.warning.call_args_list]
    assert any("file://README.md" in w and "includedFiles" in w for w in warnings)
    assert any("search://" in w and "searchQueries" in w for w in warnings)


@pytest.mark.asyncio
async def test_plain_mappings_are_untouched(gitlab_client: Any) -> None:
    item = {"path_with_namespace": "org/repo"}

    [enriched] = await GitlabRawEnricher(MagicMock()).enrich(
        _resource({"name": ".name"}), [item]
    )

    assert enriched == {"path_with_namespace": "org/repo"}
