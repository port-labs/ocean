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

from azure_devops.raw_enricher import AzureDevopsRawEnricher

ORG_URL = "https://dev.azure.com/org"


def _resource(properties: dict[str, str]) -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
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
def client() -> Any:
    client = MagicMock()
    client.get_file_by_branch = AsyncMock(return_value=b"readme content")
    manager = MagicMock()
    manager.get_client_for_org.return_value = client
    with patch(
        "azure_devops.raw_enricher.AzureDevopsClientManager.create_from_ocean_config_no_cache",
        return_value=manager,
    ):
        yield client


@pytest.mark.asyncio
async def test_resolves_file_refs_against_default_branch(client: Any) -> None:
    item = {
        "id": "repo-1",
        "defaultBranch": "refs/heads/main",
        "__organizationUrl": ORG_URL,
    }

    [enriched] = await AzureDevopsRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [item]
    )

    assert enriched["__includedFiles"] == {"README.md": "readme content"}
    client.get_file_by_branch.assert_awaited_once_with("README.md", "repo-1", "main")


@pytest.mark.asyncio
async def test_resolves_file_refs_for_branch_items(client: Any) -> None:
    item = {
        "__repository": {"id": "repo-1"},
        "__branch": "refs/heads/dev",
        "__organizationUrl": ORG_URL,
    }

    await AzureDevopsRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [item]
    )

    client.get_file_by_branch.assert_awaited_once_with("README.md", "repo-1", "dev")


@pytest.mark.asyncio
async def test_item_without_organization_maps_file_as_null(client: Any) -> None:
    [enriched] = await AzureDevopsRawEnricher(MagicMock()).enrich(
        _resource({"readme": "file://README.md"}), [{"id": "repo-1"}]
    )

    assert enriched["__includedFiles"] == {"README.md": None}
    client.get_file_by_branch.assert_not_called()


@pytest.mark.asyncio
async def test_plain_mappings_are_untouched(client: Any) -> None:
    item = {"id": "repo-1", "__organizationUrl": ORG_URL}

    [enriched] = await AzureDevopsRawEnricher(MagicMock()).enrich(
        _resource({"name": ".name"}), [item]
    )

    assert "__includedFiles" not in enriched
    client.get_file_by_branch.assert_not_called()
