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

from github.raw_enricher import GithubRawEnricher

REPOSITORY = {
    "name": "test-repo",
    "default_branch": "main",
    "owner": {"login": "test-org"},
}


def _exporter(content: Any, size: int = 20) -> AsyncMock:
    exporter = AsyncMock()
    exporter.get_resource.return_value = {"content": content, "size": size}
    return exporter


@pytest.fixture
def enricher() -> GithubRawEnricher:
    return GithubRawEnricher(context=MagicMock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item, path, expected_options",
    [
        pytest.param(
            REPOSITORY,
            "src/config/app.json",
            {"file_path": "src/config/app.json", "branch": "main"},
            id="repository",
        ),
        pytest.param(
            {
                "repository": REPOSITORY,
                "branch": "develop",
                "metadata": {"path": "services/auth/config.yaml"},
            },
            "app.json",
            {"file_path": "services/auth/app.json", "branch": "develop"},
            id="monorepo_relative_to_folder",
        ),
        pytest.param(
            {"name": "test-repo", "owner": {"login": "test-org"}},
            "config.json",
            {"file_path": "config.json", "branch": None},
            id="missing_default_branch",
        ),
    ],
)
async def test_resolve_file_ref_fetches_file_from_item_repository(
    enricher: GithubRawEnricher,
    item: dict[str, Any],
    path: str,
    expected_options: dict[str, Any],
) -> None:
    exporter = _exporter('{"key": "value"}')

    with patch("github.raw_enricher.RestFileExporter", return_value=exporter):
        assert await enricher.resolve_file_ref(item, path) == '{"key": "value"}'

    exporter.get_resource.assert_called_once_with(
        {"organization": "test-org", "repo_name": "test-repo", **expected_options}
    )


@pytest.mark.asyncio
async def test_resolve_file_ref_returns_none_for_too_large_file(
    enricher: GithubRawEnricher,
) -> None:
    with patch(
        "github.raw_enricher.RestFileExporter",
        return_value=_exporter(None, size=1048577),
    ):
        assert await enricher.resolve_file_ref(REPOSITORY, "large-file.txt") is None


@pytest.mark.asyncio
async def test_resolve_file_ref_raises_on_missing_repository_fields(
    enricher: GithubRawEnricher,
) -> None:
    with pytest.raises(KeyError, match="'name'"):
        await enricher.resolve_file_ref({"default_branch": "main"}, "config.json")


@pytest.mark.asyncio
async def test_enrich_attaches_file_contents_for_file_mappings(
    enricher: GithubRawEnricher,
) -> None:
    resource = ResourceConfig(
        kind="repository",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    blueprint='"service"',
                    properties={"readme": "file://README.md"},
                )
            )
        ),
    )

    with patch(
        "github.raw_enricher.RestFileExporter", return_value=_exporter("# readme")
    ):
        [item] = await enricher.enrich(resource, [dict(REPOSITORY)])

    assert item["__includedFiles"] == {"README.md": "# readme"}


@pytest.mark.asyncio
async def test_enrich_maps_fetch_errors_to_null(enricher: GithubRawEnricher) -> None:
    resource = ResourceConfig(
        kind="repository",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    blueprint='"service"',
                    properties={"readme": "file://README.md"},
                )
            )
        ),
    )
    exporter = AsyncMock()
    exporter.get_resource.side_effect = Exception("API error")

    with patch("github.raw_enricher.RestFileExporter", return_value=exporter):
        [item] = await enricher.enrich(resource, [dict(REPOSITORY)])

    assert item["__includedFiles"] == {"README.md": None}
