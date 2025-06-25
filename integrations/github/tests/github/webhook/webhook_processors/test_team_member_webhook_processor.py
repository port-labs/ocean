from typing import Dict, Any
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
from github.webhook.webhook_processors.team_member_webhook_processor import (
    TeamMemberWebhookProcessor,
)
from github.webhook.events import (
    TEAM_MEMBERSHIP_EVENTS,
    MEMBERSHIP_DELETE_EVENTS,
)
from github.core.options import SingleTeamOptions

from github.helpers.utils import ObjectKind, GithubClientType

from integration import GithubTeamConfig, GithubTeamSector


@pytest.fixture
def team_member_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> TeamMemberWebhookProcessor:
    return TeamMemberWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestTeamMemberWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,action,result",
        [
            ("membership", TEAM_MEMBERSHIP_EVENTS[0], True),  # e.g. "added"
            ("membership", TEAM_MEMBERSHIP_EVENTS[1], True),  # e.g. "removed"
            ("membership", "some_other_action", False),  # Correct event, wrong action
            ("team", TEAM_MEMBERSHIP_EVENTS[0], False),  # Wrong event, correct action
            ("invalid", TEAM_MEMBERSHIP_EVENTS[0], False),  # Invalid event
            ("membership", None, False),  # Action is None
            ("invalid", "some_other_action", False),  # Invalid event and action
        ],
    )
    async def test_should_process_event(
        self,
        team_member_webhook_processor: TeamMemberWebhookProcessor,
        github_event: str,
        action: str | None,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        payload_dict: Dict[str, Any] = {"action": action} if action is not None else {}
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload=payload_dict,
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert (
            await team_member_webhook_processor._should_process_event(event) is result
        )

    async def test_get_matching_kinds(
        self, team_member_webhook_processor: TeamMemberWebhookProcessor
    ) -> None:
        kinds = await team_member_webhook_processor.get_matching_kinds(
            team_member_webhook_processor.event
        )
        assert ObjectKind.TEAM in kinds

    @pytest.mark.parametrize(
        "action, members_selector_setting, expected_updated_count, expected_deleted_count",
        [
            (MEMBERSHIP_DELETE_EVENTS[0], True, 0, 0),  # "removed", selector enabled
            (
                MEMBERSHIP_DELETE_EVENTS[0],
                False,
                0,
                0,
            ),  # "removed", selector disabled (delete still happens)
            (
                TEAM_MEMBERSHIP_EVENTS[0],
                True,
                1,
                0,
            ),  # "added", selector enabled (upsert happens)
            (
                TEAM_MEMBERSHIP_EVENTS[0],
                False,
                0,
                0,
            ),  # "added", selector disabled (skips processing, no upsert)
        ],
    )
    async def test_handle_event(
        self,
        team_member_webhook_processor: TeamMemberWebhookProcessor,
        action: str,
        members_selector_setting: bool,
        expected_updated_count: int,
        expected_deleted_count: int,
    ) -> None:
        team_data = {"name": "test-team-name", "slug": "test-team-slug"}
        member_data = {"login": "test-member"}

        payload = {"action": action, "team": team_data, "member": member_data}

        resource_config = GithubTeamConfig(
            kind=ObjectKind.TEAM,
            selector=GithubTeamSector(members=members_selector_setting, query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".slug",  # This is team's identifier
                        title=".name",
                        blueprint='"githubTeam"',
                        properties={},
                    )
                )
            ),
        )

        mock_graphql_client = AsyncMock()
        mock_exporter_instance = AsyncMock()

        full_team_export_data = {
            "id": "team123",  # Example additional field from exporter
            "name": team_data["name"],
            "slug": team_data["slug"],
            "members": {
                "nodes": [
                    {"login": "other-member"},
                    {"login": member_data["login"]},
                ]
            },
        }

        if action in MEMBERSHIP_DELETE_EVENTS:
            result = await team_member_webhook_processor.handle_event(
                payload, resource_config
            )
        else:  # "added" action
            mock_exporter_instance.get_resource.return_value = full_team_export_data
            exporter_class_path = "github.webhook.webhook_processors.team_member_webhook_processor.GraphQLTeamWithMembersExporter"
            create_client_path = "github.webhook.webhook_processors.team_member_webhook_processor.create_github_client"

            with (
                patch(
                    create_client_path, return_value=mock_graphql_client
                ) as mock_create_client,
                patch(
                    exporter_class_path, return_value=mock_exporter_instance
                ) as mock_exporter_class_constructor,
            ):
                result = await team_member_webhook_processor.handle_event(
                    payload, resource_config
                )

                mock_create_client.assert_called_once_with(GithubClientType.GRAPHQL)
                mock_exporter_class_constructor.assert_called_once_with(
                    mock_graphql_client
                )
                mock_exporter_instance.get_resource.assert_called_once_with(
                    SingleTeamOptions(slug=team_data["slug"])
                )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == expected_updated_count
        assert len(result.deleted_raw_results) == expected_deleted_count

        if expected_updated_count > 0:
            # Now we expect the full_team_export_data as is, without filtering members
            assert result.updated_raw_results == [full_team_export_data]

        if expected_deleted_count > 0:
            # This part of the assertion will no longer be reached for "removed" events
            # as expected_deleted_count will be 0.
            # Keeping it for "added" events or future changes where deletion might occur.
            assert result.deleted_raw_results == [{"members": {"nodes": [member_data]}}]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (  # Valid: action and team with name
                {
                    "action": TEAM_MEMBERSHIP_EVENTS[0],  # e.g. "added"
                    "team": {
                        "name": "team1",
                        "slug": "team1-slug",
                    },  # slug also present, name is validated
                    "member": {"login": "user1"},
                },
                True,
            ),
            (  # Valid: action and team with name (member not strictly needed for this validation)
                {
                    "action": TEAM_MEMBERSHIP_EVENTS[1],  # e.g. "removed"
                    "team": {"name": "team2"},
                },
                True,
            ),
            (
                {"action": TEAM_MEMBERSHIP_EVENTS[0], "member": {"login": "user1"}},
                False,
            ),  # missing team
            (
                {"team": {"name": "team4"}, "member": {"login": "user1"}},
                False,
            ),  # missing action
            (
                {
                    "action": TEAM_MEMBERSHIP_EVENTS[0],
                    "team": {"slug": "team-slug-only"},
                },  # team present, but no 'name'
                False,
            ),
            (  # Missing action key
                {"team": {"name": "team1"}, "member": {"login": "user1"}},
                False,
            ),
            (  # Missing team key
                {"action": TEAM_MEMBERSHIP_EVENTS[0], "member": {"login": "user1"}},
                False,
            ),
            (  # Empty payload
                {},
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        team_member_webhook_processor: TeamMemberWebhookProcessor,
        payload: Dict[str, Any],
        expected: bool,
    ) -> None:
        result = await team_member_webhook_processor.validate_payload(payload)
        assert result is expected
