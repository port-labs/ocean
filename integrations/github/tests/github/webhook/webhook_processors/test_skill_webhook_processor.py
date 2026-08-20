from typing import Any
from unittest.mock import patch

import pytest

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.skill_webhook_processor import SkillWebhookProcessor
from integration import (
    GithubSkillPattern,
    GithubSkillResourceConfig,
    GithubSkillSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


@pytest.fixture
def skill_resource_config() -> GithubSkillResourceConfig:
    return GithubSkillResourceConfig(
        kind=ObjectKind.SKILL,
        selector=GithubSkillSelector(
            query="true",
            paths=[
                GithubSkillPattern(
                    path=".cursor/skills/**/SKILL.md",
                    excludeArchived=True,
                )
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".metadata.path",
                    title=".metadata.name",
                    blueprint='"githubSkill"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def skill_webhook_processor(mock_webhook_event: WebhookEvent) -> SkillWebhookProcessor:
    return SkillWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "repository": {
            "name": "test-repo",
            "default_branch": "main",
            "archived": True,
        },
        "organization": {"login": "test-org"},
    }


@pytest.mark.asyncio
async def test_handle_event_preserves_exclude_archived_when_building_file_patterns(
    skill_webhook_processor: SkillWebhookProcessor,
    skill_resource_config: GithubSkillResourceConfig,
    payload: EventPayload,
) -> None:
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
            payload, skill_resource_config
        )

    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []

    [file_pattern] = captured["file_patterns"]
    assert file_pattern.exclude_archived is True
    assert captured["organization"] == "test-org"
    assert captured["repository"] == payload["repository"]
    assert captured["current_branch"] == "main"
    assert captured["default_branch"] == "main"
