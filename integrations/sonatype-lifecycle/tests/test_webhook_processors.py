from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhook_processors.report_webhook_processor import ReportWebhookProcessor
from webhook_processors.organization_webhook_processor import (
    OrganizationWebhookProcessor,
)

APP_EVAL_PAYLOAD = {
    "applicationEvaluation": {
        "application": {
            "id": "app-1",
            "publicId": "my-app",
            "name": "My App",
            "organizationId": "org-1",
        },
        "stage": "release",
        "reportId": "rid1",
        "outcome": "fail",
    }
}


def _event(payload: dict[str, Any], webhook_id: str) -> WebhookEvent:
    return WebhookEvent(
        trace_id="t1",
        payload=payload,
        headers={"x-nexus-webhook-id": webhook_id},
    )


async def test_report_processor_should_process_application_evaluation() -> None:
    event = _event(APP_EVAL_PAYLOAD, "iq:applicationEvaluation")
    processor = ReportWebhookProcessor(event)
    assert await processor.should_process_event(event) is True
    assert await processor.get_matching_kinds(event) == ["report"]
    assert await processor.validate_payload(APP_EVAL_PAYLOAD) is True


async def test_report_processor_ignores_policy_management() -> None:
    event = _event({"owner": {"type": "APPLICATION"}}, "iq:policyManagement")
    processor = ReportWebhookProcessor(event)
    assert await processor.should_process_event(event) is False


async def test_report_processor_handle_event_refreshes_report() -> None:
    event = _event(APP_EVAL_PAYLOAD, "iq:applicationEvaluation")
    processor = ReportWebhookProcessor(event)

    fake_client = MagicMock()
    fake_client.get_scan_data_for_single_report = AsyncMock(
        return_value={"reports": [{"__identifier": "app-1-release"}], "violations": []}
    )
    with patch(
        "webhook_processors.report_webhook_processor.get_sonatype_client",
        return_value=fake_client,
    ):
        result = await processor.handle_event(APP_EVAL_PAYLOAD, MagicMock())

    assert result.updated_raw_results == [{"__identifier": "app-1-release"}]
    assert result.deleted_raw_results == []
    fake_client.get_scan_data_for_single_report.assert_awaited_once_with(
        APP_EVAL_PAYLOAD["applicationEvaluation"]["application"], "release", "rid1"
    )


async def test_org_processor_only_handles_organization_owner() -> None:
    org_event = _event(
        {"owner": {"type": "ORGANIZATION", "id": "org-1"}}, "iq:policyManagement"
    )
    app_event = _event(
        {"owner": {"type": "APPLICATION", "id": "app-1"}}, "iq:policyManagement"
    )
    processor = OrganizationWebhookProcessor(org_event)
    assert await processor.should_process_event(org_event) is True
    assert await processor.should_process_event(app_event) is False


async def test_component_processor_reads_remediation_without_isinstance() -> None:
    from webhook_processors.component_webhook_processor import ComponentWebhookProcessor

    event = _event(APP_EVAL_PAYLOAD, "iq:applicationEvaluation")
    processor = ComponentWebhookProcessor(event)

    # Plain object with the attribute — not a ComponentSelector instance.
    resource_config = MagicMock()
    resource_config.selector = MagicMock(include_remediation=True)

    fake_client = MagicMock()
    fake_client.get_component_data_for_single_report = AsyncMock(
        return_value={"components": [{"__identifier": "c1"}]}
    )
    with patch(
        "webhook_processors.component_webhook_processor.get_sonatype_client",
        return_value=fake_client,
    ):
        result = await processor.handle_event(APP_EVAL_PAYLOAD, resource_config)

    assert result.updated_raw_results == [{"__identifier": "c1"}]
    fake_client.get_component_data_for_single_report.assert_awaited_once_with(
        APP_EVAL_PAYLOAD["applicationEvaluation"]["application"],
        "release",
        "rid1",
        include_remediation=True,
    )


@pytest.mark.parametrize("has_secret", [False])
async def test_authenticate_without_secret_accepts_valid_header(
    has_secret: bool,
) -> None:
    event = _event(APP_EVAL_PAYLOAD, "iq:applicationEvaluation")
    processor = ReportWebhookProcessor(event)
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"webhook_secret": ""}
    with patch("webhook_processors._base.ocean", mock_ocean):
        assert await processor.authenticate(APP_EVAL_PAYLOAD, event.headers) is True


async def test_authenticate_rejects_missing_webhook_header() -> None:
    event = WebhookEvent(trace_id="t", payload=APP_EVAL_PAYLOAD, headers={})
    processor = ReportWebhookProcessor(event)
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"webhook_secret": ""}
    with patch("webhook_processors._base.ocean", mock_ocean):
        assert await processor.authenticate(APP_EVAL_PAYLOAD, {}) is False
