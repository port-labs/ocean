import json
from typing import Any, AsyncGenerator, Dict, List, Optional
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

    async def test_maps_metadata_sha_to_skill_blob_sha(
        self, rest_client: GithubRestClient
    ) -> None:
        """The skill's `blob_sha` is plumbed through from the file's metadata,
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
        assert skill["blob_sha"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"

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

        assert batches[0][0]["skill"]["blob_sha"] is None

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


@pytest.fixture
def plugin_exporter(rest_client: GithubRestClient) -> PluginExporter:
    return PluginExporter(rest_client, ["claude", "cursor", "opencode"])


def _plugin_options() -> PluginRepositoryOptions:
    return PluginRepositoryOptions(
        organization="test-org", repository=TEST_REPOSITORY, branch="main"
    )


async def _plugins(
    exporter: PluginExporter, files: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Run get_resource on a mocked repo; `files` maps blob path -> manifest.

    A dict is served as JSON, a str as raw content, anything else is a blob that
    is never fetched (for example a directory-marker file).
    """

    async def fetch(options: Any) -> Dict[str, Any]:
        content = files[options["file_path"]]
        return {"content": content if isinstance(content, str) else json.dumps(content)}

    exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
        return_value=(_tree(*files), False)
    )
    exporter._file_exporter.get_resource = AsyncMock(side_effect=fetch)  # type: ignore[method-assign]
    items = await exporter.get_resource(_plugin_options())
    assert len(items) == len({item["plugin"]["path"] for item in items})
    return {item["plugin"]["path"]: item["plugin"] for item in items}


class TestPluginExporter:
    async def test_root_plugin_has_empty_path_and_all_provider_keys(
        self, plugin_exporter: PluginExporter
    ) -> None:
        files = {".cursor-plugin/plugin.json": {"name": "superpowers"}}
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=(_tree(*files), False)
        )
        plugin_exporter._file_exporter.get_resource = AsyncMock(  # type: ignore[method-assign]
            return_value={"content": json.dumps(files[".cursor-plugin/plugin.json"])}
        )

        [item] = await plugin_exporter.get_resource(_plugin_options())

        assert item["__repository"] == TEST_REPOSITORY
        assert item["__branch"] == "main"
        assert item["__organization"] == "test-org"
        plugin = item["plugin"]
        assert plugin["name"] == "superpowers"
        assert plugin["path"] == ""
        assert plugin["supports"]["cursor"] is True
        assert plugin["supports"]["claude"] is False
        assert all(provider in plugin for provider in plugin["supports"])

    async def test_one_item_per_plugin_root(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugins = await _plugins(
            plugin_exporter,
            {
                "plugins/a/.claude-plugin/plugin.json": {"name": "a"},
                "plugins/b/.cursor-plugin/plugin.json": {"name": "b"},
                "README.md": "",
            },
        )
        assert set(plugins) == {"plugins/a", "plugins/b"}
        assert plugins["plugins/a"]["supports"]["claude"] is True
        assert plugins["plugins/a"]["supports"]["cursor"] is False
        assert plugins["plugins/b"]["supports"]["cursor"] is True

    async def test_mixed_providers_in_one_root(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugins = await _plugins(
            plugin_exporter,
            {
                "plugins/t/.claude-plugin/plugin.json": {"name": "t"},
                "plugins/t/.cursor-plugin/plugin.json": {"name": "t"},
            },
        )
        assert set(plugins) == {"plugins/t"}
        assert plugins["plugins/t"]["supports"]["claude"] is True
        assert plugins["plugins/t"]["supports"]["cursor"] is True
        assert plugins["plugins/t"]["claude"]["name"] == "t"

    async def test_marketplace_only_repo_emits_nothing(
        self, plugin_exporter: PluginExporter
    ) -> None:
        marketplace = {"name": "market", "plugins": [{"name": "first-entry"}]}
        assert (
            await _plugins(
                plugin_exporter, {".claude-plugin/marketplace.json": marketplace}
            )
            == {}
        )

    async def test_root_marketplace_does_not_leak_into_nested_plugin(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugins = await _plugins(
            plugin_exporter,
            {
                ".claude-plugin/marketplace.json": {"name": "registry"},
                "plugins/a/.claude-plugin/plugin.json": {"name": "a"},
            },
        )
        assert set(plugins) == {"plugins/a"}
        assert "marketplaceName" not in plugins["plugins/a"]["claude"]

    @pytest.mark.parametrize(
        "path,root",
        [
            (".opencode/plugins/hook.ts", ""),
            ("plugins/hooks/.opencode/plugins/hook.ts", "plugins/hooks"),
        ],
    )
    async def test_directory_only_provider(
        self, plugin_exporter: PluginExporter, path: str, root: str
    ) -> None:
        plugins = await _plugins(plugin_exporter, {path: None})
        assert set(plugins) == {root}
        assert plugins[root]["opencode"] == {"detected": True}
        assert plugins[root]["name"] == "repo1"

    async def test_ignored_paths_are_not_plugins(
        self, plugin_exporter: PluginExporter
    ) -> None:
        files = {
            "node_modules/x/.claude-plugin/plugin.json": {"name": "x"},
            "vendor/y/.opencode/plugins/hook.ts": None,
        }
        assert await _plugins(plugin_exporter, files) == {}

    @pytest.mark.parametrize(
        "max_depth,expected",
        [
            (1, {"", "toolkit"}),
            (None, {"", "toolkit", "plugins/a"}),
        ],
    )
    async def test_max_depth(
        self,
        rest_client: GithubRestClient,
        max_depth: Optional[int],
        expected: set[str],
    ) -> None:
        exporter = PluginExporter(rest_client, ["claude"], max_depth=max_depth)
        manifest = {"name": "p"}
        plugins = await _plugins(
            exporter,
            {
                ".claude-plugin/plugin.json": manifest,
                "toolkit/.claude-plugin/plugin.json": manifest,
                "plugins/a/.claude-plugin/plugin.json": manifest,
            },
        )
        assert set(plugins) == expected

    async def test_invalid_json_manifest_is_skipped(
        self, plugin_exporter: PluginExporter
    ) -> None:
        plugins = await _plugins(
            plugin_exporter,
            {
                "plugins/t/.claude-plugin/plugin.json": "{not json",
                "plugins/t/.cursor-plugin/plugin.json": {"name": "t"},
            },
        )
        assert plugins["plugins/t"]["supports"]["claude"] is False
        assert plugins["plugins/t"]["supports"]["cursor"] is True
        assert plugins["plugins/t"]["name"] == "t"

    async def test_skills_registry_demo_layout(
        self, plugin_exporter: PluginExporter
    ) -> None:
        """Five plugins under plugins/ and a root marketplace: no root entity."""
        names = [
            "code-quality-toolkit",
            "cursor-productivity-toolkit",
            "frontend-toolkit",
            "infrastructure-toolkit",
            "port-ops-toolkit",
        ]
        files: Dict[str, Any] = {
            ".claude-plugin/marketplace.json": {
                "name": "registry",
                "plugins": [{"name": "cursor-productivity-toolkit"}],
            }
        }
        for name in names:
            files[f"plugins/{name}/.cursor-plugin/plugin.json"] = {"name": name}
            if name != "cursor-productivity-toolkit":
                files[f"plugins/{name}/.claude-plugin/plugin.json"] = {"name": name}

        plugins = await _plugins(plugin_exporter, files)

        assert set(plugins) == {f"plugins/{name}" for name in names}
        cursor_only = plugins["plugins/cursor-productivity-toolkit"]
        assert cursor_only["supports"]["claude"] is False
        assert plugins["plugins/frontend-toolkit"]["supports"]["claude"] is True

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
