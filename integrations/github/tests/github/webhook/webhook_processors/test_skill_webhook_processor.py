import pytest
from unittest.mock import AsyncMock, patch

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
from github.helpers.utils import ObjectKind
from github.core.options import FileContentOptions


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


@pytest.mark.asyncio
class TestSkillWebhookProcessor:
    async def test_get_matching_kinds(
        self, skill_webhook_processor: SkillWebhookProcessor
    ) -> None:
        kinds = await skill_webhook_processor.get_matching_kinds(
            WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        )
        assert kinds == [ObjectKind.SKILL]

    async def test_handle_event_updated_skill_includes_blob_sha(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
    ) -> None:
        """The webhook update path should carry the Contents API's top-level
        `sha` through to `skill.blob_sha`, exactly like the resync path."""

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "skills/hello/SKILL.md",
                    "status": "modified",
                }
            ]
        }
        mock_exporter.get_resource.return_value = {
            "content": "---\nname: hello\n---\n# Hi",
            "path": "skills/hello/SKILL.md",
            "sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        }

        with (
            patch(
                "github.webhook.webhook_processors.skill_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.skill_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.deleted_raw_results == []

        skill = result.updated_raw_results[0]["skill"]
        assert skill["blob_sha"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"

        mock_exporter.get_resource.assert_called_once_with(
            FileContentOptions(
                organization="test-org",
                repo_name="test-repo",
                file_path="skills/hello/SKILL.md",
                branch="main",
            )
        )

    async def test_handle_event_deleted_skill_has_no_blob_sha(
        self,
        skill_webhook_processor: SkillWebhookProcessor,
        resource_config: GithubSkillResourceConfig,
        payload: EventPayload,
    ) -> None:
        """Delete stubs never fetch content, so `blob_sha` stays `None`."""

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "skills/hello/SKILL.md",
                    "status": "removed",
                }
            ]
        }

        with (
            patch(
                "github.webhook.webhook_processors.skill_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.skill_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await skill_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["skill"]["blob_sha"] is None
        mock_exporter.get_resource.assert_not_called()
