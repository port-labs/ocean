"""File, folder, skill and mcp exporters limited to paths changed since a time."""

from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import FilePatternMappingBuilder
from github.core.exporters.folder_exporter.core import RestFolderExporter
from github.core.exporters.folder_exporter.utils import FolderPatternMappingBuilder
from github.core.exporters.skill_exporter.core import SkillExporter
from github.core.options import FileSearchOptions, ListFolderOptions

SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
REPO = {"name": "repo", "default_branch": "main"}
TREE = [
    {"path": "a/port.yml", "type": "blob", "size": 10, "sha": "1"},
    {"path": "b/port.yml", "type": "blob", "size": 10, "sha": "2"},
    {"path": "a", "type": "tree"},
    {"path": "b", "type": "tree"},
]
FILE_PATTERN = [
    FileSearchOptions(
        organization="org", path="**/port.yml", skip_parsing=False, branch="main"
    )
]


def _patch_changed_paths(module: str, paths: list[str] | None) -> Any:
    """Patch ``changed_paths_since``; like the real one, no ``since`` means unknown changes."""

    async def _changed(*args: Any) -> list[str] | None:
        return None if args[-1] is None else paths

    return patch(f"{module}.changed_paths_since", AsyncMock(side_effect=_changed))


async def _matched_paths(
    exporter: RestFileExporter, changed_paths: list[str] | None
) -> list[str]:
    with (
        _patch_changed_paths(
            "github.core.exporters.file_exporter.core", changed_paths
        ) as changed_mock,
        patch.object(
            exporter, "get_tree_recursive", AsyncMock(return_value=(TREE, False))
        ),
        patch(
            "github.core.exporters.file_exporter.core.get_repository_metadata",
            AsyncMock(return_value=REPO),
        ),
    ):
        graphql_files, rest_files = await exporter.collect_matched_files(
            "repo", FILE_PATTERN, SINCE
        )
    changed_mock.assert_awaited_once_with(exporter.client, "org", "repo", "main", SINCE)
    return [file["file_path"] for file in graphql_files + rest_files]


@pytest.mark.asyncio
class TestFileExporterChangedSince:
    async def test_keeps_only_changed_files(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        assert await _matched_paths(exporter, ["a/port.yml", "a/other.txt"]) == [
            "a/port.yml"
        ]

    @pytest.mark.parametrize(
        "included_files, changed_paths, expected",
        [
            (["README.md"], ["a/README.md"], ["a/port.yml"]),
            (["/CODEOWNERS"], ["a/CODEOWNERS"], ["a/port.yml"]),
            (["README.md"], ["README.md"], []),
            ([], ["a/README.md"], []),
        ],
        ids=[
            "included-file-next-to-it",
            "leading-slash-is-still-next-to-it",
            "same-name-elsewhere",
            "no-included-files",
        ],
    )
    async def test_included_file_change_refreshes_the_file(
        self,
        rest_client: GithubRestClient,
        included_files: list[str],
        changed_paths: list[str],
        expected: list[str],
    ) -> None:
        exporter = RestFileExporter(rest_client, included_files=included_files)

        assert await _matched_paths(exporter, changed_paths) == expected

    async def test_nothing_changed_matches_no_file(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        assert await _matched_paths(exporter, []) == []

    async def test_untrusted_changes_list_every_file(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestFileExporter(rest_client)

        assert await _matched_paths(exporter, None) == ["a/port.yml", "b/port.yml"]


SKILL_TREE = [
    {"path": f"skills/{name}/{file}", "type": "blob", "size": 10, "sha": name}
    for name in ("a", "ab", "c")
    for file in ("SKILL.md", "scripts/run.sh")
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "include_skill_folder, changed_paths, expected",
    [
        (True, ["skills/a/scripts/run.sh"], ["skills/a/SKILL.md"]),
        (False, ["skills/a/scripts/run.sh"], []),
        (True, ["skills/ab/SKILL.md"], ["skills/ab/SKILL.md"]),
        (False, ["skills/ab/SKILL.md"], ["skills/ab/SKILL.md"]),
        (True, ["README.md"], []),
        (
            True,
            None,
            ["skills/a/SKILL.md", "skills/ab/SKILL.md", "skills/c/SKILL.md"],
        ),
    ],
    ids=[
        "folder-file-with-folder",
        "folder-file-without-folder",
        "skill-md-with-folder",
        "skill-md-without-folder",
        "outside-skills",
        "unknown-changes",
    ],
)
async def test_skill_changes(
    rest_client: GithubRestClient,
    include_skill_folder: bool,
    changed_paths: list[str] | None,
    expected: list[str],
) -> None:
    """With includeSkillFolder a change to any file in the folder rebuilds the skill;
    without it only SKILL.md changes count."""
    exporter = SkillExporter(rest_client, include_skill_folder=include_skill_folder)
    with (
        _patch_changed_paths(
            "github.core.exporters.skill_exporter.core", changed_paths
        ),
        _patch_changed_paths("github.core.exporters.file_exporter.core", changed_paths),
        patch.object(
            exporter, "get_tree_recursive", AsyncMock(return_value=(SKILL_TREE, False))
        ),
    ):
        skills = await exporter._match_files(
            "org", "repo", "main", "skills/*/SKILL.md", SINCE
        )

    assert [skill["path"] for skill in skills] == expected


@pytest.mark.asyncio
class TestFolderExporterChangedSince:
    async def _folders(
        self, rest_client: GithubRestClient, changed_paths: list[str] | None
    ) -> list[str]:
        exporter = RestFolderExporter(rest_client)
        options = [
            ListFolderOptions(
                organization="org",
                repo_name="repo",
                folders=[
                    {"organization": "org", "path": "*", "branch": "main", "repo": REPO}
                ],
                changed_since=SINCE,
            )
        ]
        with (
            _patch_changed_paths(
                "github.core.exporters.folder_exporter.core", changed_paths
            ),
            patch.object(exporter, "_get_tree", AsyncMock(return_value=TREE)),
        ):
            return [
                folder["folder"]["path"]
                async for batch in exporter.get_paginated_resources(options)
                for folder in batch
            ]

    async def test_keeps_only_folders_with_a_change(
        self, rest_client: GithubRestClient
    ) -> None:
        assert await self._folders(rest_client, ["b/nested/file.txt", "root.md"]) == [
            "b"
        ]

    async def test_nothing_changed_yields_nothing(
        self, rest_client: GithubRestClient
    ) -> None:
        assert await self._folders(rest_client, ["root.md"]) == []

    async def test_untrusted_changes_list_every_folder(
        self, rest_client: GithubRestClient
    ) -> None:
        assert await self._folders(rest_client, None) == ["a", "b"]


def _selector_mock() -> MagicMock:
    async def _select(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield "repo", "main", REPO

    selector = MagicMock()
    selector.select_repos = MagicMock(side_effect=_select)
    return selector


def _org_exporter() -> MagicMock:
    async def _orgs(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield [{"login": "org", "type": "Organization"}]

    exporter = MagicMock()
    exporter.get_paginated_resources = MagicMock(side_effect=_orgs)
    return exporter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "builder_cls, pattern",
    [
        (
            FilePatternMappingBuilder,
            MagicMock(organization="org", path="**/port.yml", skip_parsing=False),
        ),
        (FolderPatternMappingBuilder, MagicMock(organization="org", path="*")),
    ],
)
async def test_builders_pass_changed_since(builder_cls: Any, pattern: Any) -> None:
    builder = builder_cls(
        org_exporter=_org_exporter(), repo_exporter=MagicMock(), repo_type="all"
    )
    builder.repo_selector = _selector_mock()

    [repo_options] = await builder.build([pattern], changed_since=SINCE)

    assert repo_options["changed_since"] == SINCE
    assert builder.repo_selector.select_repos.call_args.kwargs == {
        "pushed_since": SINCE
    }
