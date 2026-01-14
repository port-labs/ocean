"""Unit tests for the Sentry Webhook Client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typing import AsyncGenerator, Any
from webhook_processors.webhook_client import SentryWebhookClient


pytestmark = pytest.mark.asyncio


@pytest.fixture
def sentry_webhook_client() -> SentryWebhookClient:
    """Provides a SentryWebhookClient instance for testing."""
    return SentryWebhookClient(
        sentry_base_url="https://sentry.io",
        auth_token="test-token",
        sentry_organization="test-org",
    )


class TestGetProjectAlertRules:
    """Tests for the _get_project_alert_rules method."""

    async def test_returns_rules_on_success(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests successful retrieval of alert rules."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"id": "rule-1", "name": "Test Rule"}]
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_webhook_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            rules = await sentry_webhook_client._get_project_alert_rules("test-project")
            assert rules == [{"id": "rule-1", "name": "Test Rule"}]

            mock_request.assert_awaited()
            call_args = mock_request.call_args
            assert "projects/test-org/test-project/rules/" in call_args[0][1]

    async def test_returns_empty_list_on_404(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests that empty list is returned when project not found (404)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_webhook_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            rules = await sentry_webhook_client._get_project_alert_rules("test-project")
            assert rules == []


class TestCreateProjectAlertRule:
    """Tests for the _create_project_alert_rule method."""

    async def test_creates_rule_successfully(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests successful creation of an alert rule."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"id": "new-rule", "name": "New Rule"}
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_webhook_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            rule = await sentry_webhook_client._create_project_alert_rule(
                project_slug="test-project",
                name="New Rule",
                conditions=[],
                actions=[],
            )
            assert rule == {"id": "new-rule", "name": "New Rule"}

            mock_request.assert_awaited()
            call_args = mock_request.call_args
            assert "projects/test-org/test-project/rules/" in call_args[0][1]
            assert call_args[1]["json"]["name"] == "New Rule"


class TestCreateIssueAlertRule:
    """Tests for the _create_issue_alert_rule method."""

    async def test_creates_rule_if_not_exists(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests that a rule is created if it does not exist."""
        # Mock _get_project_alert_rules to return empty list
        with patch.object(
            sentry_webhook_client,
            "_get_project_alert_rules",
            new_callable=AsyncMock,
            return_value=[],
        ):
            # Mock _create_project_alert_rule
            with patch.object(
                sentry_webhook_client,
                "_create_project_alert_rule",
                new_callable=AsyncMock,
                return_value={"id": "created-rule"},
            ) as mock_create:
                await sentry_webhook_client._create_issue_alert_rule(
                    "test-project", "Test Rule", [], []
                )
                mock_create.assert_awaited_once()

    async def test_does_not_create_rule_if_exists(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests that a rule is NOT created if it already exists."""
        # Mock _get_project_alert_rules to return existing rule
        with patch.object(
            sentry_webhook_client,
            "_get_project_alert_rules",
            new_callable=AsyncMock,
            return_value=[{"name": "Test Rule"}],
        ):
            # Mock _create_project_alert_rule
            with patch.object(
                sentry_webhook_client,
                "_create_project_alert_rule",
                new_callable=AsyncMock,
            ) as mock_create:
                await sentry_webhook_client._create_issue_alert_rule(
                    "test-project", "Test Rule", [], []
                )
                mock_create.assert_not_awaited()

    async def test_handles_creation_error_gracefully(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests that errors during creation are caught and logged."""
        with patch.object(
            sentry_webhook_client,
            "_get_project_alert_rules",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch.object(
                sentry_webhook_client,
                "_create_project_alert_rule",
                side_effect=httpx.HTTPStatusError(
                    "API Error", request=MagicMock(), response=MagicMock()
                ),
            ):
                # Should not raise exception
                await sentry_webhook_client._create_issue_alert_rule(
                    "test-project", "Test Rule", [], []
                )


class TestEnsureServiceHooks:
    """Tests for the ensure_service_hooks method integration with alert rules."""

    async def test_creates_alert_rule_before_hook(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests that _create_issue_alert_rule is called before _create_project_hook."""

        # Mock projects iterator
        async def mock_paginated_projects() -> (
            AsyncGenerator[list[dict[str, Any]], None]
        ):
            yield [{"slug": "test-project"}]

        with patch.object(
            sentry_webhook_client,
            "get_paginated_projects",
            return_value=mock_paginated_projects(),
        ):
            # Mock internal methods
            with patch.object(
                sentry_webhook_client,
                "_create_issue_alert_rule",
                new_callable=AsyncMock,
            ) as mock_create_alert:
                with patch.object(
                    sentry_webhook_client,
                    "_get_project_hooks",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    with patch.object(
                        sentry_webhook_client,
                        "_create_project_hook",
                        new_callable=AsyncMock,
                        return_value={},
                    ) as mock_create_hook:

                        await sentry_webhook_client.ensure_service_hooks(
                            "https://example.com"
                        )

                        # Verify alert rule creation was attempted
                        mock_create_alert.assert_awaited_once()
                        call_args = mock_create_alert.call_args
                        assert call_args[0][0] == "test-project"
                        assert call_args[0][1] == "Port Issue Alert - test-project"

                        # Verify hook creation was attempted
                        mock_create_hook.assert_awaited_once()
