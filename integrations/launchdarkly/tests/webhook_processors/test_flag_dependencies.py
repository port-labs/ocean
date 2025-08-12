import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.port_app_config.models import ResourceConfig, PortResourceConfig, MappingsConfig, EntityMapping
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults

from client import LaunchDarklyClient, ObjectKind
from webhook_processors.feature_flag_webhook_processor import FeatureFlagWebhookProcessor


@pytest.fixture
def feature_flag_webhook_processor():
    mock_event = WebhookEvent(
        trace_id="test-trace-id",
        payload={"kind": "flag"},
        headers={},
        original_request=None
    )
    return FeatureFlagWebhookProcessor(event=mock_event)


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=LaunchDarklyClient)
    client.get_feature_flag_dependencies = AsyncMock()
    return client


@pytest.fixture
def flag_dependency_payload():
    return {
        "kind": "flag",
        "_links": {
            "canonical": {
                "href": "/api/v2/flags/test-project/test-flag"
            },
            "self": {
                "href": "/api/v2/flags/test-project/test-flag"
            }
        },
        "name": "Test Flag",
        "key": "test-flag"
    }


@pytest.fixture
def flag_dependency_resource_config():
    return ResourceConfig(
        kind=ObjectKind.FEATURE_FLAG_DEPENDENCIES,
        selector={"query": "$.kind"},
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier="${key}",
                    blueprint="launchDarklyFlagDependency",
                    icon="LaunchDarkly"
                )
            )
        )
    )


@pytest.fixture
def mock_dependencies():
    return [
        {
            "flagKey": "test-flag",
            "dependentFlagKey": "dependent-flag",
            "dependentFlagName": "Dependent Flag",
            "projectKey": "test-project",
            "dependentProjectKey": "test-project",
            "relationshipType": "is_depended_on_by",
            "__projectKey": "test-project"
        },
        {
            "flagKey": "test-flag",
            "dependentFlagKey": "parent-flag",
            "dependentFlagName": "Parent Flag",
            "projectKey": "test-project",
            "dependentProjectKey": "test-project",
            "relationshipType": "depends_on",
            "__projectKey": "test-project"
        }
    ]


@pytest.mark.asyncio
async def test_handle_flag_dependency_update_event(
    feature_flag_webhook_processor,
    flag_dependency_payload,
    flag_dependency_resource_config,
    mock_client,
    mock_dependencies
):
    # Arrange
    mock_client.get_feature_flag_dependencies.return_value = mock_dependencies
    
    with patch(
        "webhook_processors.feature_flag_webhook_processor.LaunchDarklyClient.create_from_ocean_configuration",
        return_value=mock_client
    ):
        # Act
        result = await feature_flag_webhook_processor.handle_event(
            flag_dependency_payload, flag_dependency_resource_config
        )
        
        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == len(mock_dependencies)
        assert result.deleted_raw_results == []
        
        # Verify client was called with correct parameters
        mock_client.get_feature_flag_dependencies.assert_called_once_with(
            "test-project", "test-flag"
        )
        
        # Verify the structure of the returned dependencies
        dependencies = result.updated_raw_results
        assert dependencies == mock_dependencies
        
        # Check first dependency (is_depended_on_by relationship)
        assert dependencies[0]["relationshipType"] == "is_depended_on_by"
        assert dependencies[0]["flagKey"] == "test-flag"
        assert dependencies[0]["dependentFlagKey"] == "dependent-flag"
        
        # Check second dependency (depends_on relationship)
        assert dependencies[1]["relationshipType"] == "depends_on"
        assert dependencies[1]["flagKey"] == "test-flag"
        assert dependencies[1]["dependentFlagKey"] == "parent-flag"


@pytest.mark.asyncio
async def test_handle_flag_dependency_deletion_event(
    feature_flag_webhook_processor,
    flag_dependency_payload,
    flag_dependency_resource_config
):
    # Arrange
    # Modify payload to simulate deletion event
    deletion_payload = flag_dependency_payload.copy()
    deletion_payload["_deleted"] = True
    
    # Act
    result = await feature_flag_webhook_processor.handle_event(
        deletion_payload, flag_dependency_resource_config
    )
    
    # Assert
    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert len(result.deleted_raw_results) == 1
    
    # Check deleted record structure
    deleted_record = result.deleted_raw_results[0]
    assert deleted_record["key"] == "test-flag"
    assert deleted_record["__projectKey"] == "test-project"


@pytest.mark.asyncio
async def test_handle_flag_dependency_error(
    feature_flag_webhook_processor,
    flag_dependency_payload,
    flag_dependency_resource_config,
    mock_client
):
    # Arrange
    mock_client.get_feature_flag_dependencies.side_effect = Exception("API Error")
    
    with patch(
        "webhook_processors.feature_flag_webhook_processor.LaunchDarklyClient.create_from_ocean_configuration",
        return_value=mock_client
    ):
        # Act
        result = await feature_flag_webhook_processor.handle_event(
            flag_dependency_payload, flag_dependency_resource_config
        )
        
        # Assert
        assert isinstance(result, WebhookEventRawResults)
        # When an error occurs, the client returns an empty list
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
