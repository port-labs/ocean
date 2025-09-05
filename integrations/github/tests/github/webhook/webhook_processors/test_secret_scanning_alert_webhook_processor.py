from typing import Dict, Literal
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.secret_scanning_alert_webhook_processor import (
    SecretScanningAlertWebhookProcessor,
)
from github.helpers.utils import ObjectKind

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    GithubSecretScanningAlertConfig,
    GithubSecretScanningAlertSelector,
)


@pytest.fixture
def resource_config() -> GithubSecretScanningAlertConfig:
    return GithubSecretScanningAlertConfig(
        kind="secret-scanning-alerts",
        selector=GithubSecretScanningAlertSelector(
            query="true", state="open", hideSecret=True
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.repo + "-" + (.number | tostring)',
                    title=".secret_type",
                    blueprint='"secret_scanning_alerts"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def secret_scanning_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> SecretScanningAlertWebhookProcessor:
    return SecretScanningAlertWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestSecretScanningAlertWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,result", [("secret_scanning_alert", True), ("invalid", False)]
    )
    async def test_should_process_event(
        self,
        secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor,
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

        assert (
            await secret_scanning_webhook_processor._should_process_event(event)
            is result
        )

    async def test_get_matching_kinds(
        self, secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor
    ) -> None:
        kinds = await secret_scanning_webhook_processor.get_matching_kinds(
            secret_scanning_webhook_processor.event
        )
        assert ObjectKind.SECRET_SCANNING_ALERT in kinds

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": "created",
                    "alert": {"number": 42},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "resolved",
                    "alert": {"number": 43},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "publicly_leaked",
                    "alert": {"number": 44},
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
        secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await secret_scanning_webhook_processor._validate_payload(payload)
        assert result is expected

    @pytest.mark.parametrize(
        "config_state,action",
        [
            ("open", "created"),
            ("open", "publicly_leaked"),
            ("open", "reopened"),
            ("open", "validated"),
            ("resolved", "resolved"),
            ("all", "created"),
            ("all", "resolved"),
        ],
    )
    async def test_handle_event_action_in_allowed_state(
        self,
        secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor,
        config_state: Literal["open", "resolved", "all"],
        action: str,
        resource_config: GithubSecretScanningAlertConfig,
    ) -> None:
        """Test handling events when the action is allowed for the configured state."""

        resource_config.selector.state = config_state

        alert_data = {
            "number": 42,
            "state": "open" if action != "resolved" else "resolved",
            "secret_type": "api_key",
            "secret": "ghp_1234567890abcdef",
            "location": {
                "type": "commit",
                "target": {
                    "ref": "refs/heads/main",
                    "sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
                },
                "path": "config/api.js",
                "start_line": 15,
                "end_line": 15,
            },
            "validity": "active",
        }

        payload = {
            "action": action,
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        # Mock the RestSecretScanningAlertExporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = {
            **alert_data,
            "__repository": "test-repo",
        }

        with (
            patch(
                "github.webhook.webhook_processors.secret_scanning_alert_webhook_processor.create_github_client"
            ) as mock_create_client,
            patch(
                "github.webhook.webhook_processors.secret_scanning_alert_webhook_processor.RestSecretScanningAlertExporter",
                return_value=mock_exporter,
            ),
        ):
            mock_create_client.return_value = AsyncMock()

            result = await secret_scanning_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["__repository"] == "test-repo"

    @pytest.mark.parametrize(
        "config_state,action",
        [
            ("open", "resolved"),  # resolved action not allowed for open state
            ("resolved", "created"),  # created action not allowed for resolved state
            (
                "resolved",
                "publicly_leaked",
            ),  # publicly_leaked action not allowed for resolved state
        ],
    )
    async def test_handle_event_action_not_allowed(
        self,
        secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor,
        config_state: Literal["open", "resolved"],
        action: str,
        resource_config: GithubSecretScanningAlertConfig,
    ) -> None:
        """Test handling events when the action is not allowed for the configured state."""

        resource_config.selector.state = config_state

        alert_data = {
            "number": 45,
            "state": config_state,
            "secret_type": "private_key",
            "secret": "-----BEGIN PRIVATE KEY-----",
            "location": {
                "type": "commit",
                "target": {
                    "ref": "refs/heads/feature",
                    "sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
                },
                "path": "keys/private.pem",
                "start_line": 1,
                "end_line": 10,
            },
            "validity": "active",
        }

        payload = {
            "action": action,
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        result = await secret_scanning_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == alert_data

    async def test_handle_event_unknown_action(
        self,
        secret_scanning_webhook_processor: SecretScanningAlertWebhookProcessor,
        resource_config: GithubSecretScanningAlertConfig,
    ) -> None:
        """Test handling events with unknown actions that don't map to any states."""

        alert_data = {
            "number": 46,
            "state": "open",
            "secret_type": "api_key",
            "secret": "ghp_abcdef123456",
            "location": {
                "type": "commit",
                "target": {
                    "ref": "refs/heads/main",
                    "sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
                },
                "path": "config/test.js",
                "start_line": 20,
                "end_line": 20,
            },
            "validity": "active",
        }

        payload = {
            "action": "unknown_action",
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        result = await secret_scanning_webhook_processor.handle_event(
            payload, resource_config
        )

        # Unknown actions that don't map to any states should be skipped
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
