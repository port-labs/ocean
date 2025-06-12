from typing import Dict
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
        selector=GithubCodeScanningAlertSelector(
            query="true", state=["open", "dismissed"]
        ),
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

    async def test_handle_event_created_in_allowed_state(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        code_scanning_resource_config: GithubCodeScanningAlertConfig,
    ) -> None:
        """Test handling a 'created' event when 'open' state is allowed."""
        alert_data = {
            "number": 42,
            "state": "open",
            "rule": {
                "id": "js/unused-local-variable",
                "name": "Unused variable, import, function or class",
                "severity": "note",
                "security_severity_level": None,
                "description": "Unused variables may be a symptom of a bug.",
                "tags": ["maintainability", "useless-code"],
            },
            "tool": {"name": "CodeQL", "guid": None, "version": "2.4.0"},
            "created_at": "2020-06-19T11:21:34Z",
            "updated_at": "2020-06-19T11:21:34Z",
            "url": "https://api.github.com/repos/test-org/test-repo/code-scanning/alerts/42",
            "html_url": "https://github.com/test-org/test-repo/security/code-scanning/42",
        }

        payload = {
            "action": "created",
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
                payload, code_scanning_resource_config
            )

            # Verify exporter was called with correct parameters
            mock_exporter.get_resource.assert_called_once()
            call_args = mock_exporter.get_resource.call_args[0][0]
            assert call_args["repo_name"] == "test-repo"
            assert call_args["alert_number"] == 42

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["__repository"] == "test-repo"

    async def test_handle_event_closed_by_user_not_in_allowed_state(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
    ) -> None:
        """Test handling a 'closed_by_user' event when 'dismissed' state is not allowed."""
        # Create config that only allows 'open' state
        resource_config = GithubCodeScanningAlertConfig(
            kind="code-scanning-alerts",
            selector=GithubCodeScanningAlertSelector(
                query="true", state=["open"]  # Only open alerts allowed
            ),
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
            "number": 43,
            "state": "dismissed",
            "rule": {
                "id": "js/unused-local-variable",
                "name": "Unused variable, import, function or class",
                "severity": "warning",
                "description": "Unused variables may be a symptom of a bug.",
                "tags": ["maintainability", "useless-code"],
            },
            "dismissed_by": {"login": "test-user", "type": "User"},
            "dismissed_reason": "used_in_tests",
        }

        payload = {
            "action": "closed_by_user",
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

    async def test_handle_event_fixed_in_allowed_state(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
    ) -> None:
        """Test handling a 'fixed' event when 'fixed' state is allowed."""
        # Create config that allows 'fixed' state
        resource_config = GithubCodeScanningAlertConfig(
            kind="code-scanning-alerts",
            selector=GithubCodeScanningAlertSelector(
                query="true", state=["open", "fixed"]
            ),
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
            "action": "fixed",
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

    async def test_handle_event_appeared_in_branch_multiple_states(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        code_scanning_resource_config: GithubCodeScanningAlertConfig,
    ) -> None:
        """Test handling an 'appeared_in_branch' event which maps to 'open' state."""
        alert_data = {
            "number": 45,
            "state": "open",
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
            "action": "appeared_in_branch",
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
                payload, code_scanning_resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["rule"]["severity"] == "error"

    @pytest.mark.parametrize(
        "action,expected_states",
        [
            ("appeared_in_branch", ["open"]),
            ("reopened_by_user", ["open"]),
            ("reopened", ["open"]),
            ("created", ["open"]),
            ("fixed", ["fixed", "dismissed"]),
            ("closed_by_user", ["dismissed"]),
        ],
    )
    async def test_action_to_state_mapping(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
        action: str,
        expected_states: list[str],
    ) -> None:
        """Test that actions are correctly mapped to states."""
        # Import the mapping to verify it's correct
        from github.webhook.events import CODE_SCANNING_ALERT_ACTION_TO_STATE

        assert CODE_SCANNING_ALERT_ACTION_TO_STATE[action] == expected_states

    async def test_handle_event_with_multiple_matching_states(
        self,
        code_scanning_webhook_processor: CodeScanningAlertWebhookProcessor,
    ) -> None:
        """Test handling a 'fixed' event where multiple states match the configuration."""
        # Create config that allows both 'fixed' and 'dismissed' states
        resource_config = GithubCodeScanningAlertConfig(
            kind="code-scanning-alerts",
            selector=GithubCodeScanningAlertSelector(
                query="true", state=["open", "fixed", "dismissed"]
            ),
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
            "number": 46,
            "state": "fixed",
            "rule": {
                "id": "js/xss",
                "name": "Client-side cross-site scripting",
                "severity": "error",
                "security_severity_level": "medium",
                "description": "Directly writing user input to the DOM.",
                "tags": ["security", "external/cwe/cwe-079"],
            },
        }

        payload = {
            "action": "fixed",  # Maps to both "fixed" and "dismissed"
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

        # Should process the event because at least one of the mapped states is allowed
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
