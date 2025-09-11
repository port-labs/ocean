from typing import Dict
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
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

from github.helpers.utils import ObjectKind, GithubClientType

from integration import GithubTeamConfig, GithubTeamSector


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
        "action,is_deletion,include_members,expected_updated,expected_deleted",
        [
            ("created", False, False, True, False),  # REST exporter
            ("created", False, True, True, False),  # GraphQL exporter
            ("added", False, True, True, False),  # GraphQL exporter
            ("deleted", True, False, False, True),  # Deletion, no exporter needed
        ],
    )
    async def test_handle_event_create_and_delete(
        self,
        team_webhook_processor: TeamWebhookProcessor,
        action: str,
        is_deletion: bool,
        include_members: bool,
        expected_updated: bool,
        expected_deleted: bool,
    ) -> None:
        team_data = {
            "id": 1,
            "name": "test-repo",
            "slug": "test-team",
            "description": "Test team",
        }

        # Mocked GraphQL response structure
        graphql_team_data = {
            "data": {
                "organization": {
                    "team": {
                        "id": 1,
                        "name": "test-repo",
                        "slug": "test-team",
                        "description": "Test team",
                        # In a real scenario, members data would be here
                    }
                }
            }
        }

        payload = {"action": action, "team": team_data}

        # Create resource_config based on include_members
        resource_config = GithubTeamConfig(
            kind=ObjectKind.TEAM,
            selector=GithubTeamSector(members=include_members, query="true"),
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

        if is_deletion:
            result = await team_webhook_processor.handle_event(payload, resource_config)
        else:
            mock_exporter = AsyncMock()
            if include_members:
                mock_exporter.get_resource.return_value = graphql_team_data["data"][
                    "organization"
                ]["team"]
                exporter_path = "github.webhook.webhook_processors.team_webhook_processor.GraphQLTeamWithMembersExporter"
                client_type = GithubClientType.GRAPHQL
            else:
                mock_exporter.get_resource.return_value = team_data
                exporter_path = "github.webhook.webhook_processors.team_webhook_processor.RestTeamExporter"
                client_type = GithubClientType.REST

            with (
                patch(exporter_path, return_value=mock_exporter),
                patch(
                    "github.webhook.webhook_processors.team_webhook_processor.create_github_client"
                ) as mock_create_client,
            ):
                result = await team_webhook_processor.handle_event(
                    payload, resource_config
                )

                # Verify create_github_client was called with correct type
                mock_create_client.assert_called_once_with(client_type)

                # Verify exporter was called with correct team slug
                mock_exporter.get_resource.assert_called_once_with(
                    SingleTeamOptions(slug="test-team")
                )

        assert isinstance(result, WebhookEventRawResults)
        assert bool(result.updated_raw_results) is expected_updated
        assert bool(result.deleted_raw_results) is expected_deleted

        if expected_updated:
            # If GraphQL, the result will be the extracted team data from the graphql_team_data mock
            if include_members:
                assert result.updated_raw_results == [
                    graphql_team_data["data"]["organization"]["team"]
                ]
            else:
                assert result.updated_raw_results == [team_data]

        if expected_deleted:
            assert result.deleted_raw_results == [team_data]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": TEAM_UPSERT_EVENTS[0],
                    "team": {"slug": "team1", "name": "team1"},
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
            ({"team": {"slug": "team4", "name": "team4"}}, False),  # missing action
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
