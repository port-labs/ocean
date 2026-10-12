from contextlib import contextmanager
from typing import Any, Iterator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    GithubSkillPattern,
    GithubSkillResourceConfig,
    GithubSkillSelector,
)
from github.webhook.webhook_processors.skill_webhook_processor import (
    SkillWebhookProcessor,
)
from github.core.exporters.skill_exporter import SkillExporter
from github.core.exporters.skill_exporter.utils import SkillReference
from github.helpers.utils import ObjectKind
from github.core.options import FileContentOptions

MODULE = "github.webhook.webhook_processors.skill_webhook_processor"


@pytest.fixture
def resource_config() -> GithubSkillResourceConfig:
    return GithubSkillResourceConfig(
        kind=ObjectKind.SKILL,
        selector=GithubSkillSelector(
            query="true",
            paths=[GithubSkillPattern(path="skills/**/SKILL.md")],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".skill.path",
                    title=".skill.name",
                    blueprint='"githubSkill"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def skill_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> SkillWebhookProcessor:
    return SkillWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "commits": [],
        "repository": {"name": "test-repo", "default_branch": "main"},
        "organization": {"login": "test-org"},
    }


@pytest.fixture
def exporter() -> SkillExporter:
    """Real SkillExporter whose GitHub calls are mocked per test."""
    exporter = SkillExporter(AsyncMock())
    exporter.fetch_commit_diff = AsyncMock(return_value={"files": []})  # type: ignore[method-assign]
    exporter.get_resource = AsyncMock(return_value=None)  # type: ignore[method-assign]
    exporter.get_tree_recursive = AsyncMock(return_value=([], False))  # type: ignore[method-assign]
    exporter.fetch_references = AsyncMock(return_value=[])  # type: ignore[method-assign]
    return exporter


@contextmanager
def use_exporter(exporter: SkillExporter) -> Iterator[None]:
    def build(_client: Any, include_references: bool = False) -> SkillExporter:
        exporter.include_references = include_references
        return exporter

    with (
        patch(f"{MODULE}.create_github_client_for_org", return_value=AsyncMock()),
        patch(f"{MODULE}.SkillExporter", MagicMock(side_effect=build)),
    ):
        yield


def _blob(path: str) -> dict[str, Any]:
    return {"type": "blob", "path": path, "size": 10, "mode": "100644"}


@pytest.mark.asyncio
class TestSkillWebhookProcessor:
    async def test_get_matching_kinds(
        self, skill_webhook_processor: SkillWebhookProcessor
    ) -> None:
        kinds = await skill_webhook_processor.get_matching_kinds(
            WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        )
        assert kinds == [ObjectKind.SKILL]

    async def test_handle_event_preserves_exclude_archived_when_building_file_patterns(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
    ) -> None:
        resource_config.selector.paths = [
            GithubSkillPattern(path="skills/**/SKILL.md", excludeArchived=True)
        ]
        archived_payload = {
            **payload,
            "repository": {
                **payload["repository"],
                "archived": True,
            },
        }
        captured: dict[str, Any] = {}

        def _capture_matching_patterns(
            file_patterns: list[Any],
            organization: str,
            repository: dict[str, Any],
            current_branch: str,
            default_branch: str,
        ) -> list[Any]:
            captured["file_patterns"] = file_patterns
            captured["organization"] = organization
            captured["repository"] = repository
            captured["current_branch"] = current_branch
            captured["default_branch"] = default_branch
            return []

        with patch.object(
            skill_webhook_processor,
            "_get_matching_patterns",
            side_effect=_capture_matching_patterns,
        ):
            result = await skill_webhook_processor.handle_event(
                archived_payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

        [file_pattern] = captured["file_patterns"]
        assert file_pattern.exclude_archived is True
        assert captured["organization"] == "test-org"
        assert captured["repository"] == archived_payload["repository"]
        assert captured["current_branch"] == "main"
        assert captured["default_branch"] == "main"

    async def test_handle_event_updated_skill_includes_blob_sha(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        """The webhook update path should carry the Contents API's top-level
        `sha` through to `skill.blob_sha`, exactly like the resync path."""

        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [
                {
                    "filename": "skills/hello/SKILL.md",
                    "status": "modified",
                }
            ]
        }
        exporter.get_resource.return_value = {  # type: ignore[attr-defined]
            "content": "---\nname: hello\n---\n# Hi",
            "path": "skills/hello/SKILL.md",
            "sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        }

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.deleted_raw_results == []

        skill = result.updated_raw_results[0]["skill"]
        assert skill["blob_sha"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        assert skill["references"] is None

        exporter.get_resource.assert_called_once_with(  # type: ignore[attr-defined]
            FileContentOptions(
                organization="test-org",
                repo_name="test-repo",
                file_path="skills/hello/SKILL.md",
                branch="main",
            )
        )

    async def test_handle_event_deleted_skill_includes_blob_sha_from_compare_api(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        """Delete stubs never fetch content, but GitHub's compare API already
        includes `sha` for removed files, so `blob_sha` should still be
        populated from that diff entry with no extra fetch."""

        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [
                {
                    "filename": "skills/hello/SKILL.md",
                    "status": "removed",
                    "sha": "d670460b4b4aece5915caf5c68d12f560a9fe3e",
                }
            ]
        }

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert (
            result.deleted_raw_results[0]["skill"]["blob_sha"]
            == "d670460b4b4aece5915caf5c68d12f560a9fe3e"
        )
        exporter.get_resource.assert_not_called()  # type: ignore[attr-defined]

    async def test_reference_change_rebuilds_skill_when_flag_on(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        resource_config.selector.include_references = True
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [
                {"filename": "skills/hello/references/api.md", "status": "modified"}
            ]
        }
        exporter.get_tree_recursive.return_value = (  # type: ignore[attr-defined]
            [
                _blob("skills/hello/SKILL.md"),
                _blob("skills/hello/references/api.md"),
                _blob("skills/other/SKILL.md"),
            ],
            False,
        )
        exporter.get_resource.return_value = {  # type: ignore[attr-defined]
            "content": "---\nname: hello\n---\n# Hi",
            "sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        }
        exporter.fetch_references.return_value = [  # type: ignore[attr-defined]
            SkillReference(path="references/api.md", content="# API v2")
        ]

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        [updated] = result.updated_raw_results
        assert updated["skill"]["skillMdPath"] == "skills/hello/SKILL.md"
        assert updated["skill"]["references"] == [
            {"path": "references/api.md", "content": "# API v2"}
        ]
        assert result.deleted_raw_results == []
        exporter.get_tree_recursive.assert_called_once_with(  # type: ignore[attr-defined]
            "test-org", "test-repo", payload["after"]
        )
        exporter.fetch_references.assert_called_once()  # type: ignore[attr-defined]
        fetch_kwargs = exporter.fetch_references.call_args.kwargs  # type: ignore[attr-defined]
        assert fetch_kwargs["skill_md_path"] == "skills/hello/SKILL.md"
        assert fetch_kwargs["ref"] == payload["after"]

    async def test_reference_change_ignored_when_flag_off(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [
                {"filename": "skills/hello/references/api.md", "status": "modified"}
            ]
        }

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        exporter.get_tree_recursive.assert_not_called()  # type: ignore[attr-defined]

    async def test_deleted_skill_folder_only_emits_delete_when_flag_on(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        resource_config.selector.include_references = True
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [
                {"filename": "skills/hello/SKILL.md", "status": "removed"},
                {"filename": "skills/hello/references/api.md", "status": "removed"},
            ]
        }

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert result.updated_raw_results == []
        [deleted] = result.deleted_raw_results
        assert deleted["skill"]["skillMdPath"] == "skills/hello/SKILL.md"
        exporter.get_resource.assert_not_called()  # type: ignore[attr-defined]

    async def test_deleted_nested_skill_rebuilds_parent_when_flag_on(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        resource_config.selector.include_references = True
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [{"filename": "skills/hello/child/SKILL.md", "status": "removed"}]
        }
        exporter.get_tree_recursive.return_value = (  # type: ignore[attr-defined]
            [
                _blob("skills/hello/SKILL.md"),
                _blob("skills/hello/child/references/api.md"),
            ],
            False,
        )
        exporter.get_resource.return_value = {"content": "# Hi"}  # type: ignore[attr-defined]

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        [updated] = result.updated_raw_results
        assert updated["skill"]["skillMdPath"] == "skills/hello/SKILL.md"
        [deleted] = result.deleted_raw_results
        assert deleted["skill"]["skillMdPath"] == "skills/hello/child/SKILL.md"

    async def test_skill_md_edit_does_not_fetch_tree_when_flag_on(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        resource_config.selector.include_references = True
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [{"filename": "skills/hello/SKILL.md", "status": "modified"}]
        }
        exporter.get_resource.return_value = {"content": "# Hi"}  # type: ignore[attr-defined]

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        [updated] = result.updated_raw_results
        assert updated["skill"]["skillMdPath"] == "skills/hello/SKILL.md"
        exporter.get_tree_recursive.assert_not_called()  # type: ignore[attr-defined]

    async def test_oversized_skill_is_skipped_when_flag_on(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
        exporter: SkillExporter,
    ) -> None:
        resource_config.selector.include_references = True
        exporter.fetch_commit_diff.return_value = {  # type: ignore[attr-defined]
            "files": [{"filename": "skills/hello/SKILL.md", "status": "modified"}]
        }
        exporter.get_resource.return_value = {"content": "# Hi"}  # type: ignore[attr-defined]
        exporter.fetch_references.return_value = None  # type: ignore[attr-defined]

        with use_exporter(exporter):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
