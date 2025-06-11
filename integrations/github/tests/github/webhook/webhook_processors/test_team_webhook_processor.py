from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.team_webhook_processor import (
    TeamWebhookProcessor,
)
from github.webhook.events import TEAM_UPSERT_EVENTS, TEAM_DELETE_EVENTS
from github.core.options import SingleTeamOptions

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.TEAM,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".slug",
                    title=".name",
                    blueprint='"githubTeam"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def team_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> TeamWebhookProcessor:
    return TeamWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestTeamWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,action,result",
        [
            ("team", TEAM_UPSERT_EVENTS[0], True),
            ("team", TEAM_DELETE_EVENTS[0], True),
            ("team", "some_other_action", False),
            ("invalid", TEAM_UPSERT_EVENTS[0], False),
            ("invalid", "some_other_action", False),
        ],
    )
    async def test_should_process_event(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        github_event: str,
        action: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await team_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, team_webhook_processor: TeamWebhookProcessor
    ) -> None:
        kinds = await team_webhook_processor.get_matching_kinds(
            team_webhook_processor.event
        )
        assert ObjectKind.TEAM in kinds

    @pytest.mark.parametrize(
        "action,is_deletion,expected_updated,expected_deleted",
        [
            ("created", False, True, False),
            ("deleted", True, False, True),
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
        is_deletion: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        team_data = {
            "id": 1,
            "name": "test-repo",
            "slug": "test-team",
            "description": "Test team",
        }

        payload = {"action": action, "team": team_data}

        if is_deletion:
            result = await team_webhook_processor.handle_event(payload, resource_config)
        else:
            # Mock the TeamExporter
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = team_data

            with patch(
                "github.webhook.webhook_processors.team_webhook_processor.RestTeamExporter",
                return_value=mock_exporter,
            ):
                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct team slug
            mock_exporter.get_resource.assert_called_once_with(
                SingleTeamOptions(slug="test-team")
            )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            assert result.updated_raw_results == [team_data]

        if expected_deleted:
            assert result.deleted_raw_results == [team_data]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": TEAM_UPSERT_EVENTS[0],
                    "team": {"slug": "team1"},
                },
                True,
            ),
            (
                {
                    "action": TEAM_DELETE_EVENTS[0],
                    "team": {"slug": "team2"},
                },
                True,
            ),
            ({"action": TEAM_UPSERT_EVENTS[0]}, False),  # missing team
            ({"team": {"slug": "team4"}}, False),  # missing action
            (
                {"action": TEAM_UPSERT_EVENTS[0], "team": {}},  # no slug
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await team_webhook_processor.validate_payload(payload)
        assert result is expected
