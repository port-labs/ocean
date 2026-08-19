# Adding New AWS Resource Kinds to AWS-v3 Integration

This guide walks you through adding a new AWS resource kind (like SQS queues, RDS instances, etc.) to the AWS-v3 integration.

## Overview

The AWS-v3 integration follows a consistent pattern for all resource types:
```
Ocean Event → Resync Handler → Exporter → ResourceInspector → Actions → AWS API
```

After implementing the steps below, run the
[Self-Review Checklist](#self-review-checklist-before-opening-a-pr) against the real AWS API
before opening a PR. Bootstrapped kinds often look correct while still using non-existent
paginators, redundant actions, or invented model fields.

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

**File:** `integration.py`

Create a new `AWSResourceConfig` subclass named `AWS<Resource>ResourceConfig`. Its `kind` field must be a `Literal` matching the exact `ObjectKind` string value added above:

```python
class AWSSQSQueueResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::SQS::Queue"] = Field(
        title="AWS SQS Queue",
        description="AWS SQS Queue resource kind.",
    )
```

**File:** `integration.py`

Append the new subclass to the `Union` in `AWSPortAppConfig.resources` so Ocean can validate `port-app-config.yml` entries for this kind.

```python
class AWSPortAppConfig(PortAppConfig):
    resources: List[
        AWSS3BucketResourceConfig
        | AWSEC2InstanceResourceConfig
        | AWSECSClusterResourceConfig
        | AWSSQSQueueResourceConfig # example
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations to sync from AWS.",
    )  # type: ignore[assignment]

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
        extra = "ignore"  # Drop unexpected fields instead of failing resync
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


class GetResourceDetailsAction(Action[List[Dict[str, Any]]]):
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


class GetResourceTagsAction(Action[List[Dict[str, Any]]]):
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


class ListResourcesAction(Action[List[Dict[str, Any]]]):
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

## Self-Review Checklist (before opening a PR)

New kinds (`aws/core/exporters/{service}/{resource}/`) are usually one-shot bootstrapped from
this guide, with no real AWS calls made and no tests run against live data. Pattern-matching
other kinds can hallucinate: paginators that don't exist, actions for data that's already
available elsewhere, model fields that don't exist on the real API. Nothing catches this until
it runs against a real account.

**Do not open a PR until every item below is verified against the actual AWS API** — not against
what "looks right" or what other kinds do.

### 1. Paginator must actually exist

`proxy.get_paginator(operation, key)` wraps botocore's native paginator. If the operation has no
paginator config, it raises `OperationNotPageableError` at runtime — never at review time.

**Verify:**
```bash
python3 -c "
import botocore.session
c = botocore.session.get_session().create_client('<service>', region_name='us-east-1', aws_access_key_id='x', aws_secret_access_key='y')
print(c.can_paginate('<operation_name>'))
"
```
If `False`: hand-roll the loop in the exporter using whatever token field the operation actually
returns (`NextToken`, `Marker`, etc.) — do not use `proxy.get_paginator`.

### 2. Don't add an action the resource doesn't need

Check what the "describe/get details" call already returns before adding a separate action for
tags/policy/etc. If the primary response already includes it (SES's `GetEmailIdentity` returns
`Tags` natively — a separate `ListTagsForResource` action was pure dead weight), don't add a
second call. Only add an action for data that is genuinely absent from every other call already
being made.

**Verify:** read the operation's response shape in the real botocore service model, not AWS
prose docs:
```bash
python3 -c "
import gzip, json
with gzip.open('<path-to-venv>/lib/python3.12/site-packages/botocore/data/<service>/<version>/service-2.json.gz') as f:
    d = json.load(f)
print(json.dumps(d['shapes'][d['operations']['<Operation>']['output']['shape']], indent=2))
"
```

### 3. Confirm the service is available in every region you'll query

Not every AWS service is deployed to every region. If unsupported regions aren't filtered out,
resync throws `Could not connect to the endpoint URL` (not an access-denied error, so the
generic `safe_iterate` skip logic won't catch it).

**Verify:**
```bash
python3 -c "
import json, botocore, os
p = os.path.dirname(botocore.__file__)
d = json.load(open(os.path.join(p, 'data', 'endpoints.json')))
for partition in d['partitions']:
    svc = partition['services'].get('<endpointPrefix>')  # endpointPrefix from service-2.json metadata, not the service id
    print(partition['partition'], list(svc.get('endpoints', {})) if svc else None)
"
```
If the region list is narrower than "all", add a `<KIND>_SUPPORTED_REGIONS: frozenset[str]` in a
`regions.py` next to the exporter, and set `_supported_regions` on the exporter class (see
`memorydb/user/exporter.py`). `resync.py`'s `filter_regions_for_exporter` reads this
automatically — no other wiring needed.

### 4. Model fields must mirror the real API, not an invented shape

- Every field on a `*Properties` model must come from an actual field in a real API response
  (checked per #2's method) — never guessed from memory or AWS doc prose.
- Don't rename raw fields to "nicer" names (`IdentityName` → `EmailIdentity`). Use the AWS
  field name as-is. If a genuine identifier needs a stable/predictable key across list vs. get
  calls that use different names for the same concept, that's a sign the model or the exporter
  needs a deliberate decision — flag it, don't silently rename in an action.
- Don't flatten nested response structures into new top-level convenience fields (e.g. computing
  `DkimEnabled` from `DkimAttributes.SigningEnabled` in Python). Keep the nested raw structure as
  a single field; compute convenience values in the Port mapping's jq instead
  (`.Properties.DkimAttributes.SigningEnabled`), the same way ARNs are often built in
  `port-app-config.yml` from `.Properties.X` + `.__ExtraContext.Region`/`AccountId` rather than
  in Python.
- Don't construct and store IDs/ARNs in Python if the mapping can derive them from fields already
  on the model plus `.__ExtraContext`. Only compute a value in Python if it's needed for an
  actual AWS API call the action must make (e.g. an ARN required as a `list_tags_for_resource`
  parameter) — never just to expose it as a property.

### 5. Strip SDK response envelopes

Every raw boto3/aiobotocore response includes a top-level `ResponseMetadata` key (HTTP headers,
request ID, retry count). If an action returns a raw response dict directly, pop it first:
```python
response.pop("ResponseMetadata", None)
```
This isn't part of any service's actual data contract — it's transport plumbing botocore adds to
every call.

### 6. No redundant double-fetch in `get_resource`

`get_resource` (single-resource fetch) must avoid redundant AWS calls. If your default action already
fetches details, seed `inspector.inspect()` with only the minimal identifier (name/ARN) and let the
`defaults` action(s) make the AWS call.
If the defaults are pass-through actions that expect full response items (e.g., ECR repositories,
MemoryDB users), `get_resource` may perform the single "describe/get" call and pass its result to
the inspector — but it must not call an API that a default action will call again.

### 7. Actions run concurrently over the same raw input, not chained

All actions in `defaults` + selected `options` run via `asyncio.gather` over the *same* raw
identifier list (see `ResourceInspector.inspect`) — one action's output never becomes another
action's input. Every action must independently read whatever key it needs straight from the raw
item passed to `_execute`. Don't assume a prior action in the list "already ran" and reshaped the
data.

### 8. Extra-field handling on the model must match what's actually returned

- Use `extra="ignore"` on `*Properties` (not `extra="forbid"`). AWS responses can gain fields
  over time; ignoring unknowns keeps resync resilient instead of failing the whole sync.
- Still declare every field you care about and that appears in the raw responses used to build
  Properties. If an action does a true raw passthrough (recommended default — don't
  filter/rename in Python, see #4), declare the full union of fields from every raw response
  that feeds the model so those values are kept rather than silently dropped.

### 9. Keep mapping/blueprint/examples in sync with the model

A field rename or removal in `models.py` must be mirrored in:
`.port/resources/port-app-config.yml`, `.port/resources/blueprints.json`,
`examples/{kind}/*-mappings.yaml`, `examples/{kind}/*-raw-data.json`,
`examples/{kind}/*-expected-output.json`. Verify the jq mapping actually resolves against the
raw-data example:
```bash
jq '<mapping-expression>' examples/{kind}/*-raw-data.json
```
and confirm the result matches `*-expected-output.json`.

### 10. Tests must exercise the real boto call shape, not just the abstraction

Mock the actual client method (`list_email_identities`, `get_email_identity`, etc.) with
realistic return shapes — not `proxy.get_paginator`/`ResourceInspector` directly for every test.
Tests that only patch the internal abstractions will pass even when the underlying operation
doesn't support pagination, doesn't return an assumed field, or doesn't exist. It's fine for
exporter-level tests to mock `ResourceInspector.inspect` when testing exporter-only concerns
(e.g. `NextToken` looping), but action-level tests must mock the AWS client method itself.

### 11. Delete tests that test nothing

If a `*Properties`/`*Request` model has no custom validators — just `Field(...)` declarations —
don't write tests asserting default values or required-field errors. That tests Pydantic, not
this codebase.

### 12. Prefer importing from the service package when it re-exports symbols

If `aws/core/exporters/{service}/__init__.py` re-exports an exporter/model, prefer importing from
`aws.core.exporters.{service}` in central wiring modules (`exporter_metadata.py`, `main.py`) to
avoid deep import paths; otherwise import from the defining submodule.

### 13. Optional list/dict fields default to `None`, not `Field(default_factory=list/dict)`

Only default to an empty collection if the field is genuinely always populated (e.g. list
concatenation). Fields like `Tags` that many resources simply won't have should be
`list[dict[str, str]] | None = None`, consistent with every other optional field on the model —
not an allocated-but-empty collection on every single resource.

### 14. Type the data actions operate on with a `TypedDict`, when it's shaped like a dict

If the identifiers actions receive are dicts (e.g. `list[dict[str, Any]]` built from a `list_*`
response), define a `TypedDict` next to the actions (mark fields `NotRequired` if they're only
present from one of the call sites feeding it, e.g. list vs. single-get) and parameterize
`Action[list[YourRecord]]` with it instead of `Action[list[dict[str, Any]]]`. This documents the
exact shape actions can rely on without cross-referencing AWS docs, and mypy will catch a typo'd
key at the construction site.

This does **not** apply when the API's list call returns plain strings (e.g. SQS's
`list_queues` → `QueueUrls`, a `list[str]`) — there's no dict shape to document, so keep
`Action[list[str]]` as-is.
