from typing import Any, Dict
from unittest.mock import AsyncMock
import pytest


@pytest.fixture
def mock_azure_credential() -> AsyncMock:
    """Mock Azure DefaultAzureCredential"""
    credential = AsyncMock()
    credential.__aenter__ = AsyncMock(return_value=credential)
    credential.__aexit__ = AsyncMock(return_value=None)
    return credential


@pytest.fixture
def mock_service_bus_namespace() -> Dict[str, Any]:
    """Mock ServiceBus Namespace resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-namespace",
        "name": "test-namespace",
        "type": "Microsoft.ServiceBus/namespaces",
        "location": "eastus",
        "tags": {"env": "test"},
        "sku": {
            "name": "Standard",
            "tier": "Standard",
        },
        "properties": {
            "provisioningState": "Succeeded",
            "status": "Active",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
            "serviceBusEndpoint": "https://test-namespace.servicebus.windows.net:443/",
            "metricId": "test-metric-id",
        },
    }


@pytest.fixture
def mock_application_insights() -> Dict[str, Any]:
    """Mock Application Insights resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Insights/components/test-appinsights",
        "name": "test-appinsights",
        "type": "Microsoft.Insights/components",
        "location": "eastus",
        "kind": "web",
        "tags": {"env": "production"},
        "properties": {
            "Application_Type": "web",
            "AppId": "test-app-id",
            "InstrumentationKey": "test-instrumentation-key",
            "ConnectionString": "InstrumentationKey=test-instrumentation-key;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/",
            "provisioningState": "Succeeded",
            "Flow_Type": "Bluefield",
            "Request_Source": "rest",
            "RetentionInDays": 90,
            "SamplingPercentage": 100,
            "publicNetworkAccessForIngestion": "Enabled",
            "publicNetworkAccessForQuery": "Enabled",
        },
    }


@pytest.fixture
def mock_key_vault() -> Dict[str, Any]:
    """Mock Key Vault resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-keyvault",
        "name": "test-keyvault",
        "type": "Microsoft.KeyVault/vaults",
        "location": "eastus",
        "tags": {"env": "production"},
        "properties": {
            "tenantId": "test-tenant-id",
            "sku": {
                "family": "A",
                "name": "standard",
            },
            "vaultUri": "https://test-keyvault.vault.azure.net/",
            "provisioningState": "Succeeded",
            "enabledForDeployment": True,
            "enabledForDiskEncryption": False,
            "enabledForTemplateDeployment": True,
            "enableSoftDelete": True,
            "softDeleteRetentionInDays": 90,
            "enableRbacAuthorization": True,
            "enablePurgeProtection": True,
            "publicNetworkAccess": "Enabled",
            "networkAcls": {
                "bypass": "AzureServices",
                "defaultAction": "Allow",
            },
        },
    }


@pytest.fixture
def mock_service_bus_queue() -> Dict[str, Any]:
    """Mock ServiceBus Queue resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-namespace/queues/test-queue",
        "name": "test-queue",
        "type": "Microsoft.ServiceBus/namespaces/queues",
        "properties": {
            "createdAt": "2024-01-01T00:00:00Z",
            "messageCount": 10,
            "status": "Active",
        },
    }


@pytest.fixture
def mock_service_bus_topic() -> Dict[str, Any]:
    """Mock ServiceBus Topic resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-namespace/topics/test-topic",
        "name": "test-topic",
        "type": "Microsoft.ServiceBus/namespaces/topics",
        "properties": {
            "createdAt": "2024-01-01T00:00:00Z",
            "subscriptionCount": 2,
            "status": "Active",
        },
    }


@pytest.fixture
def mock_service_bus_subscription() -> Dict[str, Any]:
    """Mock ServiceBus Subscription resource"""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ServiceBus/namespaces/test-namespace/topics/test-topic/subscriptions/test-subscription",
        "name": "test-subscription",
        "type": "Microsoft.ServiceBus/namespaces/topics/subscriptions",
        "properties": {
            "createdAt": "2024-01-01T00:00:00Z",
            "messageCount": 5,
            "status": "Active",
        },
    }
