from typing import Any, Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from client import ObjectKind
from webhook_processors.feature_flag_webhook_processor import (
    FeatureFlagWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from typing import Generator


@pytest.fixture
def feature_flag_processor(
    mock_webhook_event: WebhookEvent,
) -> FeatureFlagWebhookProcessor:
    return FeatureFlagWebhookProcessor(mock_webhook_event)


@pytest.fixture
def valid_feature_flag_payload() -> Dict[str, Any]:
    return {
        "kind": ObjectKind.FEATURE_FLAG,
        "_links": {"canonical": {"href": "/api/v2/flags/project-1/flag-1"}},
        "titleVerb": "created",
        "name": "Test Flag",
        "accesses": [
            {"resource": "proj/project-1:env/env-1:flag/flag-1"},
            {"resource": "proj/project-1:env/env-2:flag/flag-1"},
        ],
    }


@pytest.fixture
def invalid_feature_flag_payload() -> Dict[str, Any]:
    return {
        "kind": ObjectKind.AUDITLOG,
        "_links": {"canonical": {"href": "/api/v2/flags/project-1/flag-1"}},
        "titleVerb": "created",
        "name": "Test Flag",
    }


@pytest.fixture
def mock_feature_flag_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.FEATURE_FLAG,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.key + "-" + .__projectKey',
                    title=".name",
                    blueprint='"launchDarklyFeatureFlag"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_feature_flag_status_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.FEATURE_FLAG_STATUS,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=r'. as $root | ._links.self.href | split("/") | last as $last | "\($last)-\($root.__environmentKey)"',
                    title=r'. as $root | ._links.self.href | split("/") | last as $last | "\($last)-\($root.__environmentKey)"',
                    blueprint='"launchDarklyFFInEnvironment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    with patch(
        "webhook_processors.feature_flag_webhook_processor.LaunchDarklyClient"
    ) as mock:
        client = AsyncMock()
        mock.create_from_ocean_configuration.return_value = client
        yield client


@pytest.mark.asyncio
class TestFeatureFlagWebhookProcessor:

    async def test_should_process_event(
        self,
        valid_feature_flag_payload: Dict[str, Any],
        feature_flag_processor: FeatureFlagWebhookProcessor,
        mock_client: AsyncMock,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id", headers={}, payload=valid_feature_flag_payload
        )
        assert await feature_flag_processor._should_process_event(event)

    async def test_get_matching_kinds(
        self, feature_flag_processor: FeatureFlagWebhookProcessor
    ) -> None:
        kinds = await feature_flag_processor.get_matching_kinds(
            feature_flag_processor.event
        )
        assert all(
            kind in kinds
            for kind in [ObjectKind.FEATURE_FLAG, ObjectKind.FEATURE_FLAG_STATUS]
        )

    @pytest.mark.parametrize(
        "resource_kind,is_deletion,expected_updated_count,expected_deleted_count",
        [
            # Feature Flag Deletion
            (ObjectKind.FEATURE_FLAG, True, 0, 1),
            # Feature Flag Status Deletion
            (ObjectKind.FEATURE_FLAG_STATUS, True, 0, 2),
            # # Feature Flag Update
            (ObjectKind.FEATURE_FLAG, False, 1, 0),
            # # Feature Flag Status Update
            (ObjectKind.FEATURE_FLAG_STATUS, False, 2, 0),
        ],
    )
    async def test_handle_event(
        self,
        feature_flag_processor: FeatureFlagWebhookProcessor,
        mock_client: AsyncMock,
        valid_feature_flag_payload: Dict[str, Any],
        resource_kind: ObjectKind,
        is_deletion: bool,
        expected_updated_count: int,
        expected_deleted_count: int,
        mock_feature_flag_resource_config: ResourceConfig,
        mock_feature_flag_status_resource_config: ResourceConfig,
    ) -> None:
        # Setup
        if is_deletion:
            valid_feature_flag_payload["titleVerb"] = "deleted"
            valid_feature_flag_payload["_links"]["self"] = {
                "href": "/api/v2/flags/project-1/flag-1"
            }
            valid_feature_flag_payload["accesses"] = [
                {"resource": "proj:project-1:env/env1:flag/flag-1"},
                {"resource": "proj:project-1:env/env2:flag/flag-1"},
            ]

        resource_configs = {
            ObjectKind.FEATURE_FLAG: mock_feature_flag_resource_config,
            ObjectKind.FEATURE_FLAG_STATUS: mock_feature_flag_status_resource_config,
        }

        if resource_kind == ObjectKind.FEATURE_FLAG and not is_deletion:
            mock_client.send_api_request.return_value = {
                "key": "flag-1",
                "name": "Test Flag",
            }
        elif resource_kind == ObjectKind.FEATURE_FLAG_STATUS and not is_deletion:
            mock_client.get_feature_flag_status.return_value = {
                "key": "flag-1",
                "environments": {"env1": {"on": True}, "env2": {"on": False}},
            }

        # Execute
        result = await feature_flag_processor.handle_event(
            valid_feature_flag_payload, resource_configs[resource_kind]
        )

        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == expected_updated_count
        assert len(result.deleted_raw_results) == expected_deleted_count

        if expected_updated_count > 0:
            assert all("__projectKey" in item for item in result.updated_raw_results)
            if resource_kind == ObjectKind.FEATURE_FLAG_STATUS:
                assert all(
                    "__environmentKey" in item for item in result.updated_raw_results
                )

        if expected_deleted_count > 0:
            if resource_kind == ObjectKind.FEATURE_FLAG:
                assert result.deleted_raw_results[0]["key"] == "flag-1"
                assert result.deleted_raw_results[0]["__projectKey"] == "project-1"
            else:
                assert all(
                    "__environmentKey" in item for item in result.deleted_raw_results
                )
