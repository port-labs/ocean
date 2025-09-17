# Adding New AWS Resource Kinds to AWS-v3 Integration

This guide walks you through adding a new AWS resource kind (like SQS queues, RDS instances, etc.) to the AWS-v3 integration.

## Overview

The AWS-v3 integration follows a consistent pattern for all resource types:
```
Ocean Event → Resync Handler → Exporter → ResourceInspector → Actions → AWS API
```

## Prerequisites

- Understanding of Python async/await patterns
- Basic knowledge of Pydantic models
- Familiarity with AWS SDK (boto3/aiobotocore)
- Understanding of the existing AWS-v3 codebase structure

## Step-by-Step Guide

### Step 1: Define the Resource Kind

**File:** `aws/core/helpers/types.py`

Add your new resource kind to the `ObjectKind` enum:

```python
class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    EC2_INSTANCE = "AWS::EC2::Instance"
    AccountInfo = "AWS::Account::Info"
    ECS_CLUSTER = "AWS::ECS::Cluster"
    # Add your new kind here
    SQS_QUEUE = "AWS::SQS::Queue"  # Example
```

**Why:** This defines the resource type that Ocean will recognize and trigger resync events for.

### Step 2: Create the Resource Models

**File:** `aws/core/exporters/{service}/{resource}/models.py`

Create a new directory structure following the pattern: `{service}/{resource}/`

```python
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class YourResourceProperties(BaseModel):
    # Define all properties your resource will have
    Name: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    # Add all relevant AWS resource attributes
    CreatedTime: Optional[str] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        extra = "forbid"  # Prevent unexpected fields
        populate_by_name = True  # Allow field aliases


class YourResource(ResourceModel[YourResourceProperties]):
    Type: str = "AWS::YourService::YourResource"  # Must match ObjectKind
    Properties: YourResourceProperties = Field(default_factory=YourResourceProperties)


class SingleYourResourceRequest(ResourceRequestModel):
    """Options for exporting a single resource."""
    resource_id: str = Field(..., description="The ID of the resource to export")


class PaginatedYourResourceRequest(ResourceRequestModel):
    """Options for exporting all resources in a region."""
    pass
```

**Key Points:**
- Use descriptive field names that match AWS API responses
- Include all relevant attributes your users might need
- Use proper Pydantic types and validation
- Follow the naming convention: `{Service}{Resource}Properties`

### Step 3: Create Actions

**File:** `aws/core/exporters/{service}/{resource}/actions.py`

Actions are the building blocks that fetch data from AWS APIs:

```python
from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetResourceDetailsAction(Action):
    """Fetches detailed information about the resource."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        details = await asyncio.gather(
            *(self._fetch_resource_details(resource) for resource in resources),
            return_exceptions=True,  # Don't fail entire batch if one fails
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                resource_id = resources[idx].get("id", "unknown")
                logger.error(f"Error fetching details for resource '{resource_id}': {detail_result}")
                continue
            results.append(cast(Dict[str, Any], detail_result))
        return results

    async def _fetch_resource_details(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        # Implement your AWS API call here
        response = await self.client.describe_your_resource(
            ResourceId=resource["id"]
        )

        logger.info(f"Successfully fetched details for resource {resource['id']}")

        # Transform AWS response to your model format
        return {
            "Name": response.get("ResourceName", ""),
            "Arn": response.get("ResourceArn", ""),
            # Map all relevant fields
        }


class GetResourceTagsAction(Action):
    """Fetches tags for the resource."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(self._fetch_resource_tags(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                resource_id = resources[idx].get("id", "unknown")
                logger.error(f"Error fetching tags for resource '{resource_id}': {tag_result}")
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_resource_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_for_resource(
                ResourceId=resource["id"]
            )
            return {"Tags": response.get("Tags", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                return {"Tags": []}
            else:
                raise


class ListResourcesAction(Action):
    """Processes the initial list of resources from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            data = {
                "id": resource["ResourceId"],
                "name": resource.get("ResourceName", ""),
                # Add any basic fields available from list operation
            }
            results.append(data)
        return results


class YourResourceActionsMap(ActionMap):
    """Groups all actions for this resource type."""
    defaults: List[Type[Action]] = [
        GetResourceDetailsAction,
        GetResourceTagsAction,
        ListResourcesAction,
    ]
    options: List[Type[Action]] = [
        # Add optional actions here (e.g., GetResourcePolicyAction)
    ]
```

**Key Points:**
- Each action should have a single responsibility
- **Consider batch operations**: Some AWS APIs support fetching multiple resources in a single call (e.g., `describe_instances`, `describe_services`). Use batch operations when available instead of concurrent individual calls for better performance and rate limit compliance.
- Use `asyncio.gather` for concurrent API calls when batch operations aren't supported
- Handle errors gracefully - one bad resource shouldn't break the batch
- Log errors with context for debugging
- Use proper type hints and casting

**Batch vs Concurrent Operations:**
```python
# Option 1: Batch API call (preferred if supported)
async def _fetch_resources_batch(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resource_ids = [resource["id"] for resource in resources]
    response = await self.client.describe_resources_batch(ResourceIds=resource_ids)
    return response.get("Resources", [])

# Option 2: Concurrent individual calls (fallback)
details = await asyncio.gather(
    *(self._fetch_resource_details(resource) for resource in resources),
    return_exceptions=True,
)
```

### Step 4: Create the Exporter

**File:** `aws/core/exporters/{service}/{resource}/exporter.py`

The exporter orchestrates everything and implements the `IResourceExporter` interface:

```python
from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.{service}.{resource}.actions import YourResourceActionsMap
from aws.core.exporters.{service}.{resource}.models import YourResource
from aws.core.exporters.{service}.{resource}.models import (
    SingleYourResourceRequest,
    PaginatedYourResourceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class YourResourceExporter(IResourceExporter):
    _service_name: SupportedServices = "your-service"  # Must be in SupportedServices
    _model_cls: Type[YourResource] = YourResource
    _actions_map: Type[YourResourceActionsMap] = YourResourceActionsMap

    async def get_resource(self, options: SingleYourResourceRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single resource."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"id": options.resource_id}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedYourResourceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all resources in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            # Use the appropriate paginator for your service
            paginator = proxy.get_paginator("list_your_resources", "ResourceIds")

            async for resources in paginator.paginate():
                if resources:
                    action_result = await inspector.inspect(
                        resources,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
```

**Key Points:**
- Use `AioBaseClientProxy` for proper AWS client management
- `ResourceInspector` handles the orchestration of actions
- Use appropriate paginator for your AWS service
- Include account and region context for debugging

### Step 5: Create Package Init File

**File:** `aws/core/exporters/{service}/__init__.py`

```python
from aws.core.exporters.{service}.{resource}.exporter import YourResourceExporter
from aws.core.exporters.{service}.{resource}.models import (
    SingleYourResourceRequest,
    PaginatedYourResourceRequest,
)

__all__ = [
    "YourResourceExporter",
    "SingleYourResourceRequest",
    "PaginatedYourResourceRequest",
]
```

### Step 6: Add Resync Handler

**File:** `main.py`

Add the import and resync handler:

```python
# Add import
from aws.core.exporters.{service} import YourResourceExporter
from aws.core.exporters.{service}.{resource}.models import PaginatedYourResourceRequest

# Add resync handler
@ocean.on_resync(ObjectKind.YOUR_RESOURCE)
async def resync_your_resource(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedYourResourceRequest:
        return PaginatedYourResourceRequest(
            region=region,
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
        )

    async for account, session in get_all_account_sessions():
        logger.info(f"Resyncing {kind} for account {account['Id']}")
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        logger.info(f"Found {len(regions)} allowed regions for account {account['Id']}")
        exporter = YourResourceExporter(session)

        async for batch in _handle_regional_resource_resync(
            exporter, options_factory, kind, regions, account["Id"]
        ):
            logger.info(f"Found {len(batch)} {kind} for account {account['Id']}")
            yield batch
```

### Step 7: Update Port Specification

**File:** `.port/spec.yaml`

Add your resource kind to the resources list:

```yaml
features:
  - type: exporter
    section: Cloud Providers
    resources:
      - kind: AWS::Account::Info
      - kind: AWS::S3::Bucket
      - kind: AWS::EC2::Instance
      - kind: AWS::ECS::Cluster
      - kind: AWS::YourService::YourResource  # Add your kind here
```

### Step 8: Create Blueprint

**File:** `.port/resources/blueprints.json`

Add your blueprint to the blueprints array:

```json
{
  "identifier": "yourResource",
  "title": "Your Resource",
  "icon": "AWS",
  "schema": {
    "properties": {
      "arn": {
        "type": "string",
        "title": "ARN",
        "description": "The Amazon Resource Name (ARN)"
      },
      "region": {
        "type": "string",
        "title": "Region",
        "description": "AWS region"
      },
      "tags": {
        "type": "array",
        "title": "Tags",
        "description": "Resource tags",
        "items": {"type": "object"}
      }
    },
    "required": []
  },
  "relations": {
    "account": {
      "title": "Account",
      "target": "awsAccount",
      "required": false,
      "many": false
    }
  }
}
```

### Step 9: Add Default Mapping

**File:** `.port/resources/port-app-config.yml`

Add your resource mapping after the existing resources:

```yaml
  - kind: AWS::YourService::YourResource
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .Properties.YourResourceId
          title: .Properties.YourResourceName
          blueprint: '"yourResource"'
          properties:
            # Map your resource properties
            arn: .Properties.Arn
            region: .Properties.Region
            tags: .Properties.Tags
          relations:
            account: .__ExtraContext.AccountId
```

## Testing Your Implementation

### 1. Unit Tests
Create tests for your actions and exporter:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.your_service.your_resource.actions import GetResourceDetailsAction

@pytest.mark.asyncio
async def test_get_resource_details_action():
    action = GetResourceDetailsAction()
    action.client = AsyncMock()
    action.client.describe_your_resource.return_value = {
        "ResourceName": "test-resource",
        "ResourceArn": "arn:aws:service:region:account:resource/test-resource"
    }

    result = await action._execute([{"id": "test-resource"}])

    assert len(result) == 1
    assert result[0]["Name"] == "test-resource"
```

### 2. Integration Testing
Test with real AWS resources in a development environment:

```bash
# Run the integration locally
python main.py
```

## Common Patterns and Best Practices

### 1. Error Handling
```python
try:
    response = await self.client.api_call()
    return {"Data": response.get("Data", [])}
except self.client.exceptions.ClientError as e:
    error_code = e.response.get("Error", {}).get("Code")
    if error_code == "ResourceNotFound":
        logger.info(f"Resource not found: {resource_id}")
        return {"Data": []}
    else:
        logger.error(f"Unexpected error: {e}")
        raise
```

### 2. Pagination Handling
```python
# For services that support pagination
paginator = proxy.get_paginator("list_resources", "ResourceIds")
async for page in paginator.paginate():
    if page:
        # Process page
        yield processed_data
```

### 3. Memory Optimization
```python
# Use generators for large datasets
async def get_paginated_resources(self, options) -> AsyncGenerator[list[dict], None]:
    async for batch in self._fetch_resources_in_batches(options):
        yield batch  # Don't accumulate all data in memory
```
