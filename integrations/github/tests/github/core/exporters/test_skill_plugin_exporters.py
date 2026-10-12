import json
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.core import PluginExporter
from github.core.exporters.skill_exporter.core import SkillExporter
from github.core.exporters.skill_exporter.references import MAX_SKILL_BUNDLE_SIZE
from github.core.exporters.skill_exporter.utils import SkillReference
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


def _exporter_with_references(
    rest_client: GithubRestClient, tree: List[Dict[str, Any]]
) -> tuple[SkillExporter, _FakeContentFetcher]:
    exporter = SkillExporter(rest_client, include_references=True)
    fetcher = _FakeContentFetcher()
    exporter.get_tree_recursive = AsyncMock(return_value=(tree, False))  # type: ignore[method-assign]
    exporter.process_graphql_files = fetcher.graphql  # type: ignore[method-assign]
    exporter.process_rest_api_files = fetcher.rest  # type: ignore[method-assign]
    return exporter, fetcher


class TestSkillExporterReferences:
    async def test_flag_off_skips_reference_fetching(
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

        assert batches[0][0]["skill"]["references"] is None
        exporter.get_tree_recursive.assert_not_called()

    async def test_flag_on_bundles_sorted_relative_references(
        self, rest_client: GithubRestClient
    ) -> None:
        tree = [
            _sized_blob("skills/hello/SKILL.md"),
            _sized_blob("skills/hello/references/b.md"),
            _sized_blob("skills/hello/references/a.md"),
            _sized_blob("skills/hello/scripts/big.py", size=200_000),
            _sized_blob("skills/hello/assets/logo.png"),
        ]
        exporter, fetcher = _exporter_with_references(rest_client, tree)

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

        assert batches[0][0]["skill"]["references"] == [
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
        reference_size_at_limit = MAX_SKILL_BUNDLE_SIZE - len(SKILL_MD.encode())
        tree = [
            _sized_blob("skills/fits/SKILL.md"),
            _sized_blob("skills/fits/references/api.md", size=reference_size_at_limit),
            _sized_blob("skills/big/SKILL.md"),
            _sized_blob(
                "skills/big/references/huge.md", size=reference_size_at_limit + 1
            ),
        ]
        exporter, fetcher = _exporter_with_references(rest_client, tree)

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

    async def test_references_are_read_at_given_ref(
        self, rest_client: GithubRestClient
    ) -> None:
        tree = [
            _sized_blob("skills/hello/SKILL.md"),
            _sized_blob("skills/hello/references/api.md"),
        ]
        exporter, fetcher = _exporter_with_references(rest_client, tree)

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
        exporter, fetcher = _exporter_with_references(rest_client, [])
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

        references = await exporter.fetch_references(
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
        assert references == [
            SkillReference(
                path="references/api.md",
                content="content of skills/hello/references/api.md",
            )
        ]
        assert fetcher.graphql_paths == ["skills/hello/references/api.md"]

    async def test_truncated_tree_for_root_skill_uses_repo_tree(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter, _ = _exporter_with_references(rest_client, [])
        exporter.get_tree_recursive = AsyncMock(  # type: ignore[method-assign]
            return_value=([_sized_blob("SKILL.md"), _sized_blob("notes.md")], True)
        )

        references = await exporter.fetch_references(
            organization="test-org",
            repo_name="repo1",
            ref="main",
            skill_md_path="SKILL.md",
            skill_md_size=10,
        )

        exporter.get_tree_recursive.assert_called_once()
        assert [reference.path for reference in references or []] == ["notes.md"]


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
