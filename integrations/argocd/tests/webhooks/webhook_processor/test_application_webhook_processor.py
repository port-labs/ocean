from types import SimpleNamespace
from typing import Mapping, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from webhooks.webhook_processor.application_webhook_processor import (
    ArgocdApplicationWebhookProcessor,
)


class TestArgocdApplicationWebhookProcessor:
    def _create_processor(self) -> ArgocdApplicationWebhookProcessor:
        event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        return ArgocdApplicationWebhookProcessor(event)

    @staticmethod
    def _create_resource_config_with_query_params(
        query_params: Mapping[str, object] | None,
    ) -> ResourceConfig:
        query_params_obj = (
            SimpleNamespace(generate_request_params=query_params)
            if query_params is not None
            else None
        )
        return cast(
            ResourceConfig,
            SimpleNamespace(selector=SimpleNamespace(query_params=query_params_obj)),
        )

    @pytest.mark.asyncio
    async def test_handle_event_passes_selector_query_params_and_namespace(
        self,
    ) -> None:
        processor = self._create_processor()
        payload = {
            "application_name": "test-app",
            "application_namespace": "test-namespace",
        }
        query_params = {"projects": ["default"], "selector": "team=platform"}
        expected_query_params = {
            "projects": ["default"],
            "selector": "team=platform",
            "appNamespace": "test-namespace",
        }
        resource_config = self._create_resource_config_with_query_params(query_params)
        application = {"metadata": {"name": "test-app", "uid": "uid-1"}}

        mock_client = MagicMock()
        mock_client.get_application_by_name = AsyncMock(return_value=application)

        with patch(
            "webhooks.webhook_processor.application_webhook_processor.init_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, resource_config)

        mock_client.get_application_by_name.assert_called_once_with(
            "test-app",
            params=expected_query_params,
        )
        assert result.updated_raw_results == [application]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_without_selector_query_params_continues_processing(
        self,
    ) -> None:
        processor = self._create_processor()
        payload = {"application_name": "test-app"}
        resource_config = self._create_resource_config_with_query_params(None)
        application = {"metadata": {"name": "test-app", "uid": "uid-1"}}

        mock_client = MagicMock()
        mock_client.get_application_by_name = AsyncMock(return_value=application)

        with patch(
            "webhooks.webhook_processor.application_webhook_processor.init_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, resource_config)

        mock_client.get_application_by_name.assert_called_once_with(
            "test-app",
            params={},
        )
        assert result.updated_raw_results == [application]
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_returns_empty_results_when_application_not_found(
        self,
    ) -> None:
        processor = self._create_processor()
        payload = {"application_name": "missing-app"}
        request_params = {"projects": ["default"]}
        resource_config = self._create_resource_config_with_query_params(request_params)

        mock_client = MagicMock()
        mock_client.get_application_by_name = AsyncMock(return_value={})

        with patch(
            "webhooks.webhook_processor.application_webhook_processor.init_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, resource_config)

        mock_client.get_application_by_name.assert_called_once_with(
            "missing-app",
            params=request_params,
        )
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_skips_when_namespace_does_not_match_selector(
        self,
    ) -> None:
        processor = self._create_processor()
        payload = {
            "application_name": "test-app",
            "application_namespace": "event-namespace",
        }
        resource_config = self._create_resource_config_with_query_params(
            {"appNamespace": "configured-namespace"}
        )

        mock_client = MagicMock()
        mock_client.get_application_by_name = AsyncMock(return_value={})

        with patch(
            "webhooks.webhook_processor.application_webhook_processor.init_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(payload, resource_config)

        mock_client.get_application_by_name.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
