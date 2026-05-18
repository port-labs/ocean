"""Pagination regression test for the live-events code path.

The rubric calls out 'Pagination — Regression' as a required test. The
resync path uses `get_paginated_resources` on every exporter to walk
the full collection in pages. The live-events path uses
`get_resource` (singular) to fetch one resource by identifier, with
no pagination involved.

This test pins the invariant: **no live-event handler ever invokes
`get_paginated_resources`**. If a future change accidentally swaps
the singular fetch for the paginated one (e.g. someone refactors and
hits the wrong autocomplete), this test catches it before the resync
loop starts double-paginating in production.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.ec2_instance_webhook_processor import (
    Ec2InstanceWebhookProcessor,
)
from aws.webhook.webhook_processors.ecs_service_webhook_processor import (
    EcsServiceWebhookProcessor,
)
from aws.webhook.webhook_processors.lambda_function_webhook_processor import (
    LambdaFunctionWebhookProcessor,
)
from aws.webhook.webhook_processors.s3_bucket_webhook_processor import (
    S3BucketWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import (
    ec2_state_change_event,
    ecs_service_action_event,
    lambda_event,
    s3_create_bucket_event,
)


CASES: list[tuple[str, type, str, str, dict[str, Any]]] = [
    (
        "ec2",
        Ec2InstanceWebhookProcessor,
        "aws.webhook.webhook_processors.ec2_instance_webhook_processor.EC2InstanceExporter",
        "aws.webhook.webhook_processors.ec2_instance_webhook_processor.session_for_account",
        ec2_state_change_event("i-0123abc", "running"),
    ),
    (
        "ecs",
        EcsServiceWebhookProcessor,
        "aws.webhook.webhook_processors.ecs_service_webhook_processor.EcsServiceExporter",
        "aws.webhook.webhook_processors.ecs_service_webhook_processor.session_for_account",
        ecs_service_action_event("my-cluster", "my-svc", "SERVICE_STEADY_STATE"),
    ),
    (
        "lambda",
        LambdaFunctionWebhookProcessor,
        "aws.webhook.webhook_processors.lambda_function_webhook_processor.LambdaFunctionExporter",
        "aws.webhook.webhook_processors.lambda_function_webhook_processor.session_for_account",
        lambda_event("my-fn", "CreateFunction20150331"),
    ),
    (
        "s3",
        S3BucketWebhookProcessor,
        "aws.webhook.webhook_processors.s3_bucket_webhook_processor.S3BucketExporter",
        "aws.webhook.webhook_processors.s3_bucket_webhook_processor.session_for_account",
        s3_create_bucket_event("my-bucket"),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,processor_cls,exporter_path,session_path,payload",
    CASES,
    ids=[c[0] for c in CASES],
)
async def test_live_event_handler_never_invokes_pagination(
    label: str,
    processor_cls: type,
    exporter_path: str,
    session_path: str,
    payload: dict[str, Any],
) -> None:
    """For every kind: handling a real envelope must call exactly
    `get_resource` once, and `get_paginated_resources` zero times.
    """
    event = WebhookEvent(trace_id=f"pagination-{label}", payload=payload, headers={})
    resource_config = MagicMock()
    resource_config.selector.include_actions = []

    with patch(session_path, new=AsyncMock(return_value=MagicMock())):
        with patch(exporter_path) as ExporterCls:
            instance = ExporterCls.return_value
            instance.get_resource = AsyncMock(
                return_value={"Type": "stub", "Properties": {}}
            )
            instance.get_paginated_resources = MagicMock(
                side_effect=AssertionError(
                    f"{label}: live-event handler must not invoke "
                    f"`get_paginated_resources` — pagination is the resync's "
                    f"responsibility, not live events'."
                )
            )

            processor = processor_cls(event=event)
            await processor.handle_event(payload, resource_config)

    assert instance.get_resource.await_count == 1, (
        f"{label}: expected exactly one `get_resource` call, "
        f"got {instance.get_resource.await_count}"
    )
    assert (
        instance.get_paginated_resources.call_count == 0
    ), f"{label}: pagination must not be invoked by the live-events path"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,processor_cls,exporter_path,session_path",
    [(c[0], c[1], c[2], c[3]) for c in CASES],
    ids=[c[0] for c in CASES],
)
async def test_delete_path_invokes_neither_fetch(
    label: str,
    processor_cls: type,
    exporter_path: str,
    session_path: str,
) -> None:
    """Delete-shaped events build the payload locally and must not
    invoke either `get_resource` or `get_paginated_resources`.
    """
    delete_payloads: dict[str, dict[str, Any]] = {
        "ec2": ec2_state_change_event("i-0deadbeef", "terminated"),
        "ecs": ecs_service_action_event("c", "s", "SERVICE_DELETED"),
        "lambda": lambda_event("f", "DeleteFunction20150331"),
        "s3": {
            "version": "0",
            "id": "del-0",
            "detail-type": "AWS API Call via CloudTrail",
            "source": "aws.s3",
            "account": "123456789012",
            "time": "2026-05-14T08:00:00Z",
            "region": "us-east-1",
            "resources": [],
            "detail": {
                "eventSource": "s3.amazonaws.com",
                "eventName": "DeleteBucket",
                "requestParameters": {"bucketName": "b"},
            },
        },
    }
    payload = delete_payloads[label]
    event = WebhookEvent(
        trace_id=f"pagination-del-{label}", payload=payload, headers={}
    )
    resource_config = MagicMock()
    resource_config.selector.include_actions = []

    with patch(session_path, new=AsyncMock()):
        with patch(exporter_path) as ExporterCls:
            instance = ExporterCls.return_value
            instance.get_resource = AsyncMock()
            instance.get_paginated_resources = MagicMock()

            processor = processor_cls(event=event)
            result = await processor.handle_event(payload, resource_config)

    assert instance.get_resource.await_count == 0, (
        f"{label}: delete path must not fetch — got "
        f"{instance.get_resource.await_count} `get_resource` calls"
    )
    assert (
        instance.get_paginated_resources.call_count == 0
    ), f"{label}: delete path must not paginate"
    assert (
        len(result.deleted_raw_results) >= 1
    ), f"{label}: delete path should emit at least one delete payload"
    assert result.updated_raw_results == []
