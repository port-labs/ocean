from typing import Dict, Literal
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.code_scanning_alert_webhook_processor import (
    CodeScanningAlertWebhookProcessor,
)
from github.helpers.utils import ObjectKind

from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import GithubCodeScanningAlertConfig, GithubCodeScanningAlertSelector


@pytest.fixture
def code_scanning_resource_config() -> GithubCodeScanningAlertConfig:
    return GithubCodeScanningAlertConfig(
        kind="code-scanning-alerts",
        selector=GithubCodeScanningAlertSelector(query="true", state="open"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.repo + "-" + (.number | tostring)',
                    title=".rule.name",
                    blueprint='"code_scan_alerts"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def code_scanning_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> CodeScanningAlertWebhookProcessor:
    return CodeScanningAlertWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestCodeScanningAlertWebhookProcessor:

    @pytest.mark.parametrize(
        "github_event,result", [("code_scanning_alert", True), ("invalid", False)]
    )
    async def test_should_process_event(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
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
            await code_scanning_webhook_processor._should_process_event(event) is result
        )

    async def test_get_matching_kinds(
        self, code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor
    ) -> None:
        kinds = await code_scanning_webhook_processor.get_matching_kinds(
            code_scanning_webhook_processor.event
        )
        assert ObjectKind.CODE_SCANNING_ALERT in kinds

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
                    "action": "closed_by_user",
                    "alert": {"number": 43},
                    "repository": {"name": "test-repo"},
                },
                True,
            ),
            (
                {
                    "action": "fixed",
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
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await code_scanning_webhook_processor._validate_payload(payload)
        assert result is expected

    @pytest.mark.parametrize(
        "config_state,action",
        [
            ("open", "created"),
            ("dismissed", "fixed"),
            ("fixed", "fixed"),
            ("closed", "closed_by_user"),
        ],
    )
    async def test_handle_event_fixed_in_allowed_state(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        config_state: Literal["open", "dismissed", "fixed", "closed"],
        action: str,
    ) -> None:
        """Test handling a 'fixed' event when 'fixed' state is allowed."""
        # Create config that allows 'fixed' state
        resource_config = GithubCodeScanningAlertConfig(
            kind="code-scanning-alerts",
            selector=GithubCodeScanningAlertSelector(query="true", state=config_state),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier='.repo + "-" + (.number | tostring)',
                        title=".rule.name",
                        blueprint='"code_scan_alerts"',
                        properties={},
                    )
                )
            ),
        )

        alert_data = {
            "number": 44,
            "state": "fixed",
            "rule": {
                "id": "js/sql-injection",
                "name": "Database query built from user-controlled sources",
                "severity": "error",
                "security_severity_level": "high",
                "description": "Building a database query with user-controlled data.",
                "tags": ["security", "external/cwe/cwe-089"],
            },
            "tool": {"name": "CodeQL", "version": "2.4.0"},
            "fixed_at": "2020-07-15T08:30:00Z",
        }

        payload = {
            "action": action,
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        # Mock the RestCodeScanningAlertExporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = {
            **alert_data,
            "__repository": "test-repo",
        }

        with (
            patch(
                "github.webhook.webhook_processors.code_scanning_alert_webhook_processor.create_github_client"
            ) as mock_create_client,
            patch(
                "github.webhook.webhook_processors.code_scanning_alert_webhook_processor.RestCodeScanningAlertExporter",
                return_value=mock_exporter,
            ),
        ):
            mock_create_client.return_value = AsyncMock()

            result = await code_scanning_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["state"] == "fixed"
        assert result.updated_raw_results[0]["__repository"] == "test-repo"

    @pytest.mark.parametrize(
        "config_state,action",
        [
            ("open", "fixed"),  # fixed action not allowed for open state
            ("dismissed", "created"),  # created action not allowed for dismissed state
            (
                "fixed",
                "closed_by_user",
            ),  # closed_by_user action not allowed for fixed state
            ("closed", "reopened"),  # reopened action not allowed for closed state
        ],
    )
    async def test_handle_event_action_not_allowed(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        config_state: Literal["open", "dismissed", "fixed", "closed"],
        action: str,
    ) -> None:
        """Test handling events when the action is not allowed for the configured state."""
        resource_config = GithubCodeScanningAlertConfig(
            kind="code-scanning-alerts",
            selector=GithubCodeScanningAlertSelector(query="true", state=config_state),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier='.repo + "-" + (.number | tostring)',
                        title=".rule.name",
                        blueprint='"code_scan_alerts"',
                        properties={},
                    )
                )
            ),
        )

        alert_data = {
            "number": 45,
            "state": config_state,
            "rule": {
                "id": "js/hardcoded-credentials",
                "name": "Hard-coded credentials",
                "severity": "error",
                "security_severity_level": "high",
                "description": "Credentials are hard-coded in the source code.",
                "tags": ["security", "external/cwe/cwe-798"],
            },
            "tool": {"name": "CodeQL", "version": "2.4.0"},
        }

        payload = {
            "action": action,
            "alert": alert_data,
            "repository": {"name": "test-repo"},
        }

        result = await code_scanning_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == alert_data
