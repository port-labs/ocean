import json
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.core import PluginExporter
from github.core.exporters.skill_exporter.core import SkillExporter
from github.core.options import (
    FileSearchOptions,
    ListFileSearchOptions,
    ListPluginOptions,
    PluginRepositoryOptions,
)

TEST_REPOSITORY = {"name": "repo1", "full_name": "test-org/repo1"}

SKILL_MD = """---
name: hello-skill
description: A minimal example
---

# Hello
"""


def _skill_search_options(*paths: str) -> List[ListFileSearchOptions]:
    return [
        ListFileSearchOptions(
            organization="test-org",
            repo_name="repo1",
            files=[
                FileSearchOptions(organization="test-org", path=path, skip_parsing=True)
                for path in paths
            ],
        )
    ]


def _file_object(
    path: str, content: str, metadata: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    return {
        "organization": "test-org",
        "content": content,
        "repository": TEST_REPOSITORY,
        "branch": "main",
        "path": path,
        "name": "SKILL.md",
        "metadata": metadata if metadata is not None else {},
    }


class TestSkillExporter:
    async def test_maps_file_batches_to_skills(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object(".cursor/skills/hello/SKILL.md", SKILL_MD)]

        exporter = SkillExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options(".cursor/skills/**/SKILL.md")
                )
            ]

        assert len(batches) == 1
        skill = batches[0][0]["skill"]
        assert skill["name"] == "hello-skill"
        assert skill["root"] == ".cursor/skills"
        assert skill["skillMdPath"] == ".cursor/skills/hello/SKILL.md"
        assert batches[0][0]["__organization"] == "test-org"

    async def test_maps_metadata_sha_to_skill_sha(
        self, rest_client: GithubRestClient
    ) -> None:
        """The skill's `sha` is plumbed through from the file's metadata,
        which already carries the git blob SHA returned by the GitHub API."""

        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                _file_object(
                    "skills/hello/SKILL.md",
                    SKILL_MD,
                    metadata={"sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"},
                )
            ]

        exporter = SkillExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        skill = batches[0][0]["skill"]
        assert skill["sha"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"

    async def test_missing_metadata_sha_defaults_to_none(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("skills/hello/SKILL.md", SKILL_MD)]

        exporter = SkillExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        assert batches[0][0]["skill"]["sha"] is None

    async def test_skips_files_without_string_content(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("skills/hello/SKILL.md", None)]  # type: ignore[arg-type]

        exporter = SkillExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        assert batches == []


def _tree(*paths: str) -> List[Dict[str, Any]]:
    return [{"type": "blob", "path": path} for path in paths]


def _manifest_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RestFileExporter.get_resource returns already-decoded content."""
    return {"content": json.dumps(payload)}


@pytest.fixture
def plugin_exporter(rest_client: GithubRestClient) -> PluginExporter:
    return PluginExporter(rest_client, ["claude", "cursor", "opencode"])


class TestPluginExporter:
    async def test_get_resource_builds_plugin(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=(_tree(".cursor-plugin/plugin.json"), False)
        )
        plugin_exporter._file_exporter.get_resource = AsyncMock(  # type: ignore[method-assign]
            return_value=_manifest_response(
                {"name": "superpowers", "displayName": "Superpowers"}
            )
        )

        item = await plugin_exporter.get_resource(
            PluginRepositoryOptions(
                organization="test-org", repository=TEST_REPOSITORY, branch="main"
            )
        )

        assert item is not None
        assert item["plugin"]["name"] == "superpowers"
        assert item["plugin"]["supports"]["cursor"] is True
        assert item["__repository"] == TEST_REPOSITORY
        assert item["__branch"] == "main"
        assert item["__organization"] == "test-org"

    async def test_get_resource_returns_none_without_manifests(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=(_tree("README.md"), False)
        )

        assert (
            await plugin_exporter.get_resource(
                PluginRepositoryOptions(
                    organization="test-org", repository=TEST_REPOSITORY, branch="main"
                )
            )
            is None
        )

    async def test_get_resource_detects_directory_only_plugin(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=(_tree(".opencode/plugins/hook.ts"), False)
        )

        item = await plugin_exporter.get_resource(
            PluginRepositoryOptions(
                organization="test-org", repository=TEST_REPOSITORY, branch="main"
            )
        )

        assert item is not None
        assert item["plugin"]["name"] == "repo1"
        assert item["plugin"]["opencode"] == {"detected": True}

    async def test_get_paginated_resources_skips_failing_repositories(
        self, plugin_exporter: PluginExporter
    ) -> None:
        async def tree_side_effect(
            _org: str, repo: str, _branch: str
        ) -> tuple[List[Dict[str, Any]], bool]:
            if repo == "broken":
                raise RuntimeError("boom")
            return _tree(".opencode/plugins/hook.ts"), False

        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            side_effect=tree_side_effect
        )

        items = [
            item
            async for batch in plugin_exporter.get_paginated_resources(
                ListPluginOptions(
                    organization="test-org",
                    repositories=[
                        PluginRepositoryOptions(
                            organization="test-org",
                            repository={"name": "broken"},
                            branch="main",
                        ),
                        PluginRepositoryOptions(
                            organization="test-org",
                            repository=TEST_REPOSITORY,
                            branch="main",
                        ),
                    ],
                )
            )
            for item in batch
        ]

        assert len(items) == 1
        assert items[0]["plugin"]["name"] == "repo1"

    async def test_is_tree_truncated(self, plugin_exporter: PluginExporter) -> None:
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=([], True)
        )

        assert await plugin_exporter.is_tree_truncated("test-org", "repo1", "main")
