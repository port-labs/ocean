import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.core import PluginExporter
from github.core.exporters.skill_exporter.core import SkillExporter
from github.core.exporters.skill_exporter.skill_folder import MAX_SKILL_BUNDLE_SIZE
from github.core.exporters.skill_exporter.utils import SkillFile
from github.core.options import (
    FileSearchOptions,
    ListFileSearchOptions,
    ListPluginOptions,
    PluginRepositoryOptions,
)
from port_ocean.exceptions.core import OceanAbortException

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


def _sized_blob(path: str, size: int = 10) -> Dict[str, Any]:
    return {"type": "blob", "path": path, "size": size, "mode": "100644"}


class _FakeContentFetcher:
    """Stands in for the batched GraphQL/REST fetchers and records requested paths and refs."""

    def __init__(self) -> None:
        self.graphql_paths: List[str] = []
        self.rest_paths: List[str] = []
        self.refs: set[str] = set()

    async def graphql(
        self, files: List[Dict[str, Any]]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.graphql_paths.extend(file["file_path"] for file in files)
        self.refs.update(file["branch"] for file in files)
        if files:
            yield [self._file(file) for file in files]

    async def rest(
        self, files: List[Dict[str, Any]]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.rest_paths.extend(file["file_path"] for file in files)
        self.refs.update(file["branch"] for file in files)
        yield [self._file(file) for file in files]

    @staticmethod
    def _file(file: Dict[str, Any]) -> Dict[str, Any]:
        return {"path": file["file_path"], "content": f"content of {file['file_path']}"}


def _exporter_with_skill_folder(
    rest_client: GithubRestClient, tree: List[Dict[str, Any]]
) -> tuple[SkillExporter, _FakeContentFetcher]:
    exporter = SkillExporter(rest_client, include_skill_folder=True)
    fetcher = _FakeContentFetcher()
    exporter.get_tree_recursive = AsyncMock(return_value=(tree, False))  # type: ignore[method-assign]
    exporter.process_graphql_files = fetcher.graphql  # type: ignore[method-assign]
    exporter.process_rest_api_files = fetcher.rest  # type: ignore[method-assign]
    return exporter, fetcher


class TestSkillExporterSkillFolder:
    async def test_flag_off_skips_skill_folder_fetching(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("skills/hello/SKILL.md", SKILL_MD)]

        exporter = SkillExporter(rest_client)
        exporter.get_tree_recursive = AsyncMock()  # type: ignore[method-assign]
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        assert batches[0][0]["skill"]["files"] is None
        exporter.get_tree_recursive.assert_not_called()

    async def test_flag_on_bundles_sorted_relative_files(
        self, rest_client: GithubRestClient
    ) -> None:
        tree = [
            _sized_blob("skills/hello/SKILL.md"),
            _sized_blob("skills/hello/references/b.md"),
            _sized_blob("skills/hello/references/a.md"),
            _sized_blob("skills/hello/scripts/big.py", size=200_000),
            _sized_blob("skills/hello/assets/logo.png"),
        ]
        exporter, fetcher = _exporter_with_skill_folder(rest_client, tree)

        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("skills/hello/SKILL.md", SKILL_MD)]

        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        assert batches[0][0]["skill"]["files"] == [
            {
                "path": "references/a.md",
                "content": "content of skills/hello/references/a.md",
            },
            {
                "path": "references/b.md",
                "content": "content of skills/hello/references/b.md",
            },
            {
                "path": "scripts/big.py",
                "content": "content of skills/hello/scripts/big.py",
            },
        ]
        assert sorted(fetcher.graphql_paths) == [
            "skills/hello/references/a.md",
            "skills/hello/references/b.md",
        ]
        assert fetcher.rest_paths == ["skills/hello/scripts/big.py"]

    async def test_skill_over_size_limit_is_dropped_without_fetching(
        self, rest_client: GithubRestClient
    ) -> None:
        file_size_at_limit = MAX_SKILL_BUNDLE_SIZE - len(SKILL_MD.encode())
        tree = [
            _sized_blob("skills/fits/SKILL.md"),
            _sized_blob("skills/fits/references/api.md", size=file_size_at_limit),
            _sized_blob("skills/big/SKILL.md"),
            _sized_blob("skills/big/references/huge.md", size=file_size_at_limit + 1),
        ]
        exporter, fetcher = _exporter_with_skill_folder(rest_client, tree)

        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                _file_object("skills/fits/SKILL.md", SKILL_MD),
                _file_object("skills/big/SKILL.md", SKILL_MD),
            ]

        mock_logger = MagicMock()
        with (
            patch.object(RestFileExporter, "get_paginated_resources", fake_files),
            patch("github.core.exporters.skill_exporter.core.logger", mock_logger),
        ):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _skill_search_options("skills/**/SKILL.md")
                )
            ]

        assert [item["skill"]["skillMdPath"] for item in batches[0]] == [
            "skills/fits/SKILL.md"
        ]
        assert fetcher.rest_paths == ["skills/fits/references/api.md"]
        assert fetcher.graphql_paths == []
        [warning_call] = mock_logger.warning.call_args_list
        assert "skills/big/SKILL.md" in warning_call.args[0]

    async def test_skill_folder_is_read_at_given_ref(
        self, rest_client: GithubRestClient
    ) -> None:
        tree = [
            _sized_blob("skills/hello/SKILL.md"),
            _sized_blob("skills/hello/references/api.md"),
        ]
        exporter, fetcher = _exporter_with_skill_folder(rest_client, tree)

        item = await exporter.build_skill_item(
            skill_md_path="skills/hello/SKILL.md",
            content=SKILL_MD,
            repository=TEST_REPOSITORY,
            branch="main",
            organization="test-org",
            path_globs=["skills/**/SKILL.md"],
            ref="abc123",
        )

        assert item is not None
        assert item["__branch"] == "main"
        exporter.get_tree_recursive.assert_called_once_with(  # type: ignore[attr-defined]
            "test-org", TEST_REPOSITORY["name"], "abc123"
        )
        assert fetcher.refs == {"abc123"}

    async def test_truncated_repo_tree_falls_back_to_skill_folder_tree(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter, fetcher = _exporter_with_skill_folder(rest_client, [])
        exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                ([_sized_blob("skills/hello/SKILL.md")], True),
                (
                    [
                        _sized_blob("SKILL.md"),
                        _sized_blob("references/api.md"),
                        _sized_blob("child/SKILL.md"),
                        _sized_blob("child/notes.md"),
                    ],
                    False,
                ),
            ]
        )

        files = await exporter.fetch_skill_folder_files(
            organization="test-org",
            repo_name="repo1",
            ref="main",
            skill_md_path="skills/hello/SKILL.md",
            skill_md_size=10,
        )

        assert exporter.get_tree_recursive.call_args_list[1].args == (
            "test-org",
            "repo1",
            "main:skills/hello",
        )
        assert files == [
            SkillFile(
                path="references/api.md",
                content="content of skills/hello/references/api.md",
            )
        ]
        assert fetcher.graphql_paths == ["skills/hello/references/api.md"]

    async def test_truncated_tree_for_root_skill_uses_repo_tree(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter, _ = _exporter_with_skill_folder(rest_client, [])
        exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=([_sized_blob("SKILL.md"), _sized_blob("notes.md")], True)
        )

        files = await exporter.fetch_skill_folder_files(
            organization="test-org",
            repo_name="repo1",
            ref="main",
            skill_md_path="SKILL.md",
            skill_md_size=10,
        )

        exporter.get_tree_recursive.assert_called_once()
        assert [file.path for file in files or []] == ["notes.md"]


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

    async def test_agents_marketplace_marks_support_on_an_existing_plugin(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = PluginExporter(rest_client, ["claude", "agents"])
        marketplace = {"name": "acme-market", "plugins": [{"name": "listed"}]}

        # Next to a real manifest it annotates the plugin ...
        plugins = await _plugins(
            exporter,
            {
                ".claude-plugin/plugin.json": {"name": "p"},
                ".agents/plugins/marketplace.json": marketplace,
            },
        )
        assert plugins[""]["supports"]["agents"] is True
        assert plugins[""]["agents"] == {"name": "p", "marketplaceName": "acme-market"}

        # ... but never creates one on its own.
        assert (
            await _plugins(exporter, {".agents/plugins/marketplace.json": marketplace})
            == {}
        )

    async def test_truncated_tree_emits_nothing(
        self, plugin_exporter: PluginExporter
    ) -> None:
        """A partial tree can drop a provider's manifest, so write nothing."""
        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=(_tree(".claude-plugin/plugin.json"), True)
        )
        plugin_exporter._file_exporter.get_resource = AsyncMock()  # type: ignore[method-assign]

        assert await plugin_exporter.get_resource(_plugin_options()) == []
        plugin_exporter._file_exporter.get_resource.assert_not_called()

    async def test_truncated_repository_aborts_the_resync_after_the_others(
        self, plugin_exporter: PluginExporter
    ) -> None:
        """Aborting makes Ocean skip reconciliation, so no entity gets deleted."""

        async def tree(
            _org: str, repo: str, _branch: str
        ) -> tuple[List[Dict[str, Any]], bool]:
            return _tree(".opencode/plugins/hook.ts"), repo == "huge"

        plugin_exporter._file_exporter.get_tree_recursive = AsyncMock(side_effect=tree)  # type: ignore[method-assign]
        items: List[Dict[str, Any]] = []

        with pytest.raises(OceanAbortException, match="huge"):
            async for batch in plugin_exporter.get_paginated_resources(
                ListPluginOptions(
                    organization="test-org",
                    repositories=[
                        PluginRepositoryOptions(
                            organization="test-org",
                            repository={"name": name},
                            branch="main",
                        )
                        for name in ("huge", "small")
                    ],
                )
            ):
                items.extend(batch)

        assert [item["__repository"]["name"] for item in items] == ["small"]
