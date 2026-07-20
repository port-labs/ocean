from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.assessment_webhook_processor import AssessmentWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return AssessmentWebhookProcessor(mock_event)


@pytest.fixture()
def payload() -> dict[str, Any]:
    return {
        "payload_version": "2",
        "notification_configuration_id": "nc-SZ3V3cLFxK6sqLKn",
        "notification_configuration_url": "https://app.terraform.io/api/v2/notification-configurations/nc-SZ3V3cLFxK6sqLKn",
        "trigger_scope": "assessment",
        "trigger": "assessment:drifted",
        "message": "Drift Detected",
        "details": {
            "new_assessment_result": {
                "id": "asmtres-vRVQxpqq64EA9V5a",
                "url": "https://app.terraform.io/api/v2/assessment-results/asmtres-vRVQxpqq64EA9V5a",
                "succeeded": True,
                "drifted": True,
                "all_checks_succeeded": True,
                "resources_drifted": 4,
                "resources_undrifted": 55,
                "checks_passed": 33,
                "checks_failed": 0,
                "checks_errored": 0,
                "checks_unknown": 0,
                "created_at": "2022-06-09T05:23:10Z",
            },
            "prior_assessment_result": {
                "id": "asmtres-A6zEbpGArqP74fdL",
                "url": "https://app.terraform.io/api/v2/assessment-results/asmtres-A6zEbpGArqP74fdL",
                "succeeded": True,
                "drifted": True,
                "all_checks_succeeded": True,
                "resources_drifted": 4,
                "resources_undrifted": 55,
                "checks_passed": 33,
                "checks_failed": 0,
                "checks_errored": 0,
                "checks_unknown": 0,
                "created_at": "2022-06-09T05:22:51Z",
            },
            "workspace_id": "ws-XdeUVMWShTesDMME",
            "workspace_name": "my-workspace",
            "organization_name": "acme-org",
        },
    }


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_workspace(self, processor: Any) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.HEALTH_ASSESSMENT]
        assert len(result) == 1


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_should_process_event_always_returns_true(
        self, processor: Any, payload: dict[str, Any]
    ) -> None:
        event = MagicMock()
        event.payload = payload

        result = await processor._should_process_event(event)

        assert result is True


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_handle_event_success(
        self, processor: Any, payload: dict[str, Any]
    ) -> None:
        resource_config = MagicMock()

        mock_client = MagicMock()
        mock_client.get_single_health_assessment = AsyncMock(
            return_value=payload["details"]["new_assessment_result"]
        )

        with patch(
            "webhook_processors.assessment_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert (
                result.updated_raw_results[0]
                == payload["details"]["new_assessment_result"]
            )
            assert result.deleted_raw_results == []
            mock_client.get_single_health_assessment.assert_called_once_with(
                payload["details"]["new_assessment_result"]["id"]
            )

    @pytest.mark.asyncio
    async def test_handle_event_calls_init_terraform_client(
        self, processor: Any, payload: dict[str, Any]
    ) -> None:
        resource_config = MagicMock()

        mock_client = MagicMock()
        mock_client.get_single_health_assessment = AsyncMock(
            return_value=payload["details"]["new_assessment_result"]
        )

        with patch(
            "webhook_processors.assessment_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            await processor.handle_event(payload, resource_config)

            mock_init.assert_called_once()
