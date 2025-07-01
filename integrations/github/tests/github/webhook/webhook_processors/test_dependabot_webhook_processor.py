from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.dependabot_webhook_processor import (
    DependabotAlertWebhookProcessor,
)
from github.helpers.utils import ObjectKind

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import GithubDependabotAlertConfig, GithubDependabotAlertSelector


@pytest.fixture
def dependabot_resource_config() -> GithubDependabotAlertConfig:
    return GithubDependabotAlertConfig(
        kind="dependabot-alert",
        selector=GithubDependabotAlertSelector(
            query="true", states=["open", "dismissed"]
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.repo.name + "-" + (.number | tostring)',
                    title=".number | tostring",
                    blueprint='"githubDependabotAlert"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def dependabot_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> DependabotAlertWebhookProcessor:
    return DependabotAlertWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestDependabotAlertWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,result", [("dependabot_alert", True), ("invalid", False)]
    )
    async def test_should_process_event(
        self,
        dependabot_webhook_processor: DependabotAlertWebhookProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await dependabot_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, dependabot_webhook_processor: DependabotAlertWebhookProcessor
    ) -> None:
        kinds = await dependabot_webhook_processor.get_matching_kinds(
            dependabot_webhook_processor.event
        )
        assert ObjectKind.DEPENDABOT_ALERT in kinds

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": "created",
                    "alert": {"number": 1},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "dismissed",
                    "alert": {"number": 2},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "fixed",
                    "alert": {"number": 3},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "created",
                    "repository": {"name": "test-repo"},
                },  # missing alert
                False,
            ),
            (
                {
                    "action": "created",
                    "alert": {},  # missing number
                    "repository": {"name": "test-repo"},
                },
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        dependabot_webhook_processor: DependabotAlertWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await dependabot_webhook_processor._validate_payload(payload)
        assert result is expected

    async def test_handle_event_created_in_allowed_state(
        self,
        dependabot_webhook_processor: DependabotAlertWebhookProcessor,
        dependabot_resource_config: GithubDependabotAlertConfig,
    ) -> None:
        """Test handling a 'created' event when 'open' state is allowed."""
        alert_data = {
            "number": 1,
            "state": "open",
            "dependency": {
                "package": {"name": "lodash", "ecosystem": "npm"},
                "manifest_path": "package.json",
                "scope": "runtime",
            },
            "security_advisory": {
                "ghsa_id": "GHSA-jf85-cpcp-j695",
                "cve_id": "CVE-2019-10744",
                "severity": "high",
            },
            "url": "https://api.github.com/repos/test-org/test-repo/dependabot/alerts/1",
            "html_url": "https://github.com/test-org/test-repo/security/dependabot/1",
            "created_at": "2019-01-02T19:23:10Z",
            "updated_at": "2019-01-02T19:23:10Z",
        }

        payload = {
            "action": "created",
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        # Mock the RestDependabotAlertExporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = {
            **alert_data,
            "repo": {"name": "test-repo"},
        }

        with (
            patch(
                "github.webhook.webhook_processors.dependabot_webhook_processor.create_github_client"
            ) as mock_create_client,
            patch(
                "github.webhook.webhook_processors.dependabot_webhook_processor.RestDependabotAlertExporter",
                return_value=mock_exporter,
            ),
        ):
            mock_create_client.return_value = AsyncMock()

            result = await dependabot_webhook_processor.handle_event(
                payload, dependabot_resource_config
            )

            # Verify exporter was called with correct parameters
            mock_exporter.get_resource.assert_called_once()
            call_args = mock_exporter.get_resource.call_args[0][0]
            assert call_args["repo_name"] == "test-repo"
            assert call_args["alert_number"] == 1

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["repo"]["name"] == "test-repo"

    async def test_handle_event_dismissed_not_in_allowed_state(
        self,
        dependabot_webhook_processor: DependabotAlertWebhookProcessor,
    ) -> None:
        """Test handling a 'dismissed' event when 'dismissed' state is not allowed."""
        # Create config that only allows 'open' state
        resource_config = GithubDependabotAlertConfig(
            kind="dependabot-alert",
            selector=GithubDependabotAlertSelector(
                query="true", states=["open"]  # Only open alerts allowed
            ),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier='.repo.name + "-" + (.number | tostring)',
                        title=".number | tostring",
                        blueprint='"githubDependabotAlert"',
                        properties={},
                    )
                )
            ),
        )

        alert_data = {
            "number": 2,
            "state": "dismissed",
            "dependency": {
                "package": {"name": "debug", "ecosystem": "npm"},
                "manifest_path": "package.json",
                "scope": "runtime",
            },
            "security_advisory": {
                "ghsa_id": "GHSA-gxpj-cx7g-858c",
                "cve_id": "CVE-2017-20165",
                "severity": "medium",
            },
        }

        payload = {
            "action": "dismissed",
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        result = await dependabot_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == alert_data

    @pytest.mark.parametrize(
        "action,expected_state",
        [
            ("created", "open"),
            ("reopened", "open"),
            ("auto_reopened", "open"),
            ("dismissed", "dismissed"),
            ("auto_dismissed", "auto_dismissed"),
            ("fixed", "fixed"),
        ],
    )
    async def test_action_to_state_mapping(
        self,
        dependabot_webhook_processor: DependabotAlertWebhookProcessor,
        action: str,
        expected_state: str,
    ) -> None:
        """Test that actions are correctly mapped to states."""
        # Import the mapping to verify it's correct
        from github.webhook.events import DEPENDABOT_ACTION_TO_STATE

        assert DEPENDABOT_ACTION_TO_STATE[action] == expected_state
