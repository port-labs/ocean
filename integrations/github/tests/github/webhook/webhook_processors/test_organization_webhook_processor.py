from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
    ResourceConfig,
    Selector,
)

from github.webhook.webhook_processors.organization_webhook_processor import (
    OrganizationWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import ORGANIZATION_EVENTS
from github.core.options import SingleOrganizationOptions


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.ORGANIZATION,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".login",
                    title=".name",
                    blueprint='"githubOrganization"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def organization_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> OrganizationWebhookProcessor:
    return OrganizationWebhookProcessor(event=mock_webhook_event)


def make_org_payload(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "organization": {"login": "test-org", "id": 123},
        "sender": {"login": "admin-user"},
    }


@pytest.mark.asyncio
class TestOrganizationWebhookProcessor:
    @pytest.mark.parametrize("action", ORGANIZATION_EVENTS)
    async def test_should_process_event_valid(
        self,
        organization_webhook_processor: OrganizationWebhookProcessor,
        action: str,
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "organization"}
        mock_event.payload = {"action": action}

        assert (
            await organization_webhook_processor._should_process_event(mock_event)
            is True
        )

    async def test_should_process_event_wrong_event_type(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "team"}
        mock_event.payload = {"action": "deleted"}

        assert (
            await organization_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_should_process_event_unknown_action(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "organization"}
        mock_event.payload = {"action": "unknown_action"}

        assert (
            await organization_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_should_process_event_no_action(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "organization"}
        mock_event.payload = {}

        assert (
            await organization_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_get_matching_kinds(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        kinds = await organization_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.ORGANIZATION]

    async def test_validate_payload_valid(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        payload = make_org_payload("renamed")
        assert await organization_webhook_processor.validate_payload(payload) is True

    async def test_validate_payload_missing_action(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        payload = {"organization": {"login": "test-org"}}
        assert await organization_webhook_processor.validate_payload(payload) is False

    async def test_validate_payload_missing_organization(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        payload = {"action": "renamed"}
        assert await organization_webhook_processor.validate_payload(payload) is False

    async def test_validate_payload_missing_login(
        self, organization_webhook_processor: OrganizationWebhookProcessor
    ) -> None:
        payload = {"action": "renamed", "organization": {"id": 123}}
        assert await organization_webhook_processor.validate_payload(payload) is False

    async def test_handle_event_deleted(
        self,
        organization_webhook_processor: OrganizationWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = make_org_payload("deleted")

        result = await organization_webhook_processor.handle_event(
            payload, resource_config
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [{"login": "test-org", "id": 123}]

    @pytest.mark.parametrize(
        "action",
        ["renamed"],
    )
    async def test_handle_event_upsert(
        self,
        action: str,
        organization_webhook_processor: OrganizationWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = make_org_payload(action)

        fetched_org = {
            "login": "test-org",
            "id": 123,
            "name": "Test Organization",
            "description": "A test org",
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = fetched_org

        with (
            patch(
                "github.webhook.webhook_processors.organization_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
            ) as mock_create_client,
            patch(
                "github.webhook.webhook_processors.organization_webhook_processor.RestOrganizationExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await organization_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [fetched_org]
        assert result.deleted_raw_results == []
        mock_create_client.assert_called_once_with("test-org")
        mock_exporter.get_resource.assert_called_once_with(
            SingleOrganizationOptions(organization="test-org")
        )

    async def test_handle_event_upsert_fetch_fails(
        self,
        organization_webhook_processor: OrganizationWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        payload = make_org_payload("renamed")

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = {}

        with (
            patch(
                "github.webhook.webhook_processors.organization_webhook_processor.create_github_client_for_org",
                new_callable=AsyncMock,
            ),
            patch(
                "github.webhook.webhook_processors.organization_webhook_processor.RestOrganizationExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await organization_webhook_processor.handle_event(
                payload, resource_config
            )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
