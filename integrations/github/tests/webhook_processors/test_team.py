import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.team import TeamWebhookProcessor
from client import GitHubClient
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from helpers.utils import ObjectKind


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


@pytest.mark.asyncio
class TestTeamWebhookProcessor:
    @pytest.fixture
    def team_webhook_processor(
        self, mock_webhook_event: WebhookEvent
    ) -> TeamWebhookProcessor:
        return TeamWebhookProcessor(event=mock_webhook_event)

    @pytest.mark.parametrize(
        "action",
        [
            "created",
            "deleted",
            "edited",
            "added_to_repository",
            "removed_from_repository",
        ],
    )
    async def test_should_process_valid_events(
        self, team_webhook_processor: TeamWebhookProcessor, action: str
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action, "team": {}},
            headers={"x-github-event": "team"},
        )
        result = await team_webhook_processor.should_process_event(event)
        assert result is True

    async def test_handle_event_create_success(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        team_data = {
            "id": 1,
            "name": "engineering",
            "slug": "engineering",
            "description": "Engineering team",
            "privacy": "closed",
        }

        mock_client = AsyncMock(spec=GitHubClient)
        mock_client.get_single_resource.return_value = team_data

        with patch(
            "webhook_processors.team.GitHubClient.from_ocean_config",
            return_value=mock_client,
        ):
            result = await team_webhook_processor.handle_event(
                {"action": "created", "team": {"slug": "engineering"}},
                resource_config,
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [team_data]
        assert result.deleted_raw_results == []
        mock_client.get_single_resource.assert_called_once_with(
            ObjectKind.TEAM, "engineering"
        )

    async def test_handle_event_delete(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        team_data = {"id": 1, "name": "engineering", "slug": "engineering"}

        result = await team_webhook_processor.handle_event(
            {"action": "deleted", "team": team_data}, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [team_data]
