from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from linear.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.cycle_webhook_processor import CycleWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor

PROCESSOR_CASES = [
    pytest.param(
        UserWebhookProcessor,
        ObjectKind.USER,
        "User",
        "user-1",
        "get_single_user",
        {"id": "user-1", "name": "Alice"},
        id="user",
    ),
    pytest.param(
        ProjectWebhookProcessor,
        ObjectKind.PROJECT,
        "Project",
        "project-1",
        "get_single_project",
        {"id": "project-1", "name": "Payments"},
        id="project",
    ),
    pytest.param(
        CycleWebhookProcessor,
        ObjectKind.CYCLE,
        "Cycle",
        "cycle-1",
        "get_single_cycle",
        {"id": "cycle-1", "number": 5},
        id="cycle",
    ),
]


@pytest.mark.asyncio
class TestNewResourceWebhookProcessors:
    @pytest.mark.parametrize(
        "processor_class,kind,event_type,entity_id,client_method,entity_data",
        PROCESSOR_CASES,
    )
    async def test_get_matching_kinds(
        self,
        mock_webhook_event: WebhookEvent,
        processor_class: type,
        kind: ObjectKind,
        event_type: str,
        entity_id: str,
        client_method: str,
        entity_data: dict[str, Any],
    ) -> None:
        processor = processor_class(event=mock_webhook_event)
        event = WebhookEvent(
            trace_id="test",
            payload={"type": event_type, "data": {"id": entity_id}, "action": "create"},
            headers={},
        )

        assert await processor.get_matching_kinds(event) == [kind]

    @pytest.mark.parametrize(
        "processor_class,kind,event_type,entity_id,client_method,entity_data",
        PROCESSOR_CASES,
    )
    async def test_handle_event_success(
        self,
        mock_webhook_event: WebhookEvent,
        processor_class: type,
        kind: ObjectKind,
        event_type: str,
        entity_id: str,
        client_method: str,
        entity_data: dict[str, Any],
    ) -> None:
        processor = processor_class(event=mock_webhook_event)
        resource_config = ResourceConfig(
            kind=kind,
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"linearEntity"',
                        properties={},
                    )
                )
            ),
        )
        payload = {
            "action": "create",
            "type": event_type,
            "data": {"id": entity_id},
        }

        with patch(
            f"webhook_processors.{event_type.lower()}_webhook_processor.LinearClient"
        ) as mock_client_class:
            client = AsyncMock()
            mock_client_class.create_from_ocean_configuration.return_value = client
            getattr(client, client_method).return_value = entity_data

            result = await processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == [entity_data]
        assert result.deleted_raw_results == []
        getattr(client, client_method).assert_awaited_once_with(entity_id)

    @pytest.mark.parametrize(
        "processor_class,kind,event_type,entity_id,client_method,entity_data",
        PROCESSOR_CASES,
    )
    async def test_handle_event_remove(
        self,
        mock_webhook_event: WebhookEvent,
        processor_class: type,
        kind: ObjectKind,
        event_type: str,
        entity_id: str,
        client_method: str,
        entity_data: dict[str, Any],
    ) -> None:
        processor = processor_class(event=mock_webhook_event)
        resource_config = ResourceConfig(
            kind=kind,
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"linearEntity"',
                        properties={},
                    )
                )
            ),
        )
        payload = {
            "action": "remove",
            "type": event_type,
            "data": {"id": entity_id},
        }

        with patch(
            f"webhook_processors.{event_type.lower()}_webhook_processor.LinearClient"
        ) as mock_client_class:
            client = AsyncMock()
            mock_client_class.create_from_ocean_configuration.return_value = client

            result = await processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [{"id": entity_id}]
        getattr(client, client_method).assert_not_awaited()
