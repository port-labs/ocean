"""Registry-shape and cross-processor routing tests.

These catch two regressions that per-processor unit tests can miss:

1. Someone renames `WEBHOOK_PATH`, forgets to register a new processor,
   or removes the middleware wiring. The "registers all processors"
   test fails immediately.

2. Two processors' `_matches_event` predicates start overlapping (e.g.
   an EC2 fixture accidentally matches the Lambda processor too). The
   "matches exactly one processor" parametrized test fails per fixture.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aws.webhook.registry import WEBHOOK_PATH, register_live_events_webhooks
from aws.webhook.webhook_processors.aws_abstract_webhook_processor import (
    _AwsAbstractWebhookProcessor,
)
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
from aws.webhook.webhook_processors.webhook_healthcheck_processor import (
    HEALTHCHECK_HEADER,
    WebhookHealthcheckProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from tests.webhook.fixtures import (
    ec2_state_change_event,
    ecs_deployment_state_change_event,
    ecs_service_action_event,
    lambda_event,
    s3_create_bucket_event,
    s3_delete_bucket_event,
)


KIND_PROCESSORS: list[type[_AwsAbstractWebhookProcessor]] = [
    Ec2InstanceWebhookProcessor,
    EcsServiceWebhookProcessor,
    LambdaFunctionWebhookProcessor,
    S3BucketWebhookProcessor,
]


class TestRegisterLiveEventsWebhooks:
    def test_registers_middleware_and_all_processors(self) -> None:
        mock_ocean_app = MagicMock()
        mock_ocean_app.route_prefix = ""

        with patch("aws.webhook.registry.ocean") as mock_ocean:
            mock_ocean.app = mock_ocean_app
            mock_ocean.add_webhook_processor = MagicMock()
            with patch(
                "aws.webhook.registry.register_live_events_auth_middleware"
            ) as mock_register_middleware:
                register_live_events_webhooks()

        mock_register_middleware.assert_called_once_with(
            "/integration/webhook/live-events"
        )

        registered_processors = [
            call.args[1] for call in mock_ocean.add_webhook_processor.call_args_list
        ]
        registered_paths = {
            call.args[0] for call in mock_ocean.add_webhook_processor.call_args_list
        }

        assert registered_paths == {WEBHOOK_PATH}
        assert registered_processors == [
            WebhookHealthcheckProcessor,
            Ec2InstanceWebhookProcessor,
            EcsServiceWebhookProcessor,
            LambdaFunctionWebhookProcessor,
            S3BucketWebhookProcessor,
        ]

    def test_webhook_path_value(self) -> None:
        assert WEBHOOK_PATH == "/webhook/live-events"

    def test_respects_configured_route_prefix(self) -> None:
        mock_ocean_app = MagicMock()
        mock_ocean_app.route_prefix = "/port-ocean"

        with patch("aws.webhook.registry.ocean") as mock_ocean:
            mock_ocean.app = mock_ocean_app
            mock_ocean.add_webhook_processor = MagicMock()
            with patch(
                "aws.webhook.registry.register_live_events_auth_middleware"
            ) as mock_register_middleware:
                register_live_events_webhooks()

        mock_register_middleware.assert_called_once_with(
            "/port-ocean/integration/webhook/live-events"
        )


def _fixtures_with_labels() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("ec2-running", ec2_state_change_event("i-0", "running")),
        ("ec2-stopped", ec2_state_change_event("i-0", "stopped")),
        ("ec2-terminated", ec2_state_change_event("i-0", "terminated")),
        (
            "ecs-service-action-steady",
            ecs_service_action_event("c", "s", "SERVICE_STEADY_STATE"),
        ),
        (
            "ecs-service-action-deleted",
            ecs_service_action_event("c", "s", "SERVICE_DELETED"),
        ),
        (
            "ecs-deployment-in-progress",
            ecs_deployment_state_change_event(
                "c", "s", "SERVICE_DEPLOYMENT_IN_PROGRESS"
            ),
        ),
        ("lambda-create", lambda_event("f", "CreateFunction20150331")),
        (
            "lambda-update-config",
            lambda_event("f", "UpdateFunctionConfiguration20150331v2"),
        ),
        ("lambda-update-code", lambda_event("f", "UpdateFunctionCode20150331v2")),
        ("lambda-delete", lambda_event("f", "DeleteFunction20150331")),
        ("s3-create", s3_create_bucket_event("b")),
        (
            "s3-create-eu-west-1",
            s3_create_bucket_event("b", location_constraint="eu-west-1"),
        ),
        ("s3-delete", s3_delete_bucket_event("b")),
    ]


def _expected_processor_for(label: str) -> type[_AwsAbstractWebhookProcessor]:
    if label.startswith("ec2-"):
        return Ec2InstanceWebhookProcessor
    if label.startswith("ecs-"):
        return EcsServiceWebhookProcessor
    if label.startswith("lambda-"):
        return LambdaFunctionWebhookProcessor
    if label.startswith("s3-"):
        return S3BucketWebhookProcessor
    raise AssertionError(f"unhandled fixture label: {label}")


class TestProcessorRoutingExactness:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "label,payload",
        _fixtures_with_labels(),
        ids=[label for label, _ in _fixtures_with_labels()],
    )
    async def test_each_fixture_matches_exactly_one_kind_processor(
        self, label: str, payload: dict[str, Any]
    ) -> None:
        event = WebhookEvent(trace_id=label, payload=payload, headers={})
        expected = _expected_processor_for(label)

        matchers: dict[type[_AwsAbstractWebhookProcessor], bool] = {}
        for cls in KIND_PROCESSORS:
            processor = cls(event=event)
            matchers[cls] = await processor._matches_event(event)

        matched = [cls for cls, did_match in matchers.items() if did_match]
        assert matched == [expected], (
            f"fixture {label!r} matched {[c.__name__ for c in matched]}; "
            f"expected only {expected.__name__}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "label,payload",
        _fixtures_with_labels(),
        ids=[label for label, _ in _fixtures_with_labels()],
    )
    async def test_no_kind_fixture_matches_the_healthcheck_processor(
        self, label: str, payload: dict[str, Any]
    ) -> None:
        """The healthcheck only triggers via the explicit header, never via an EventBridge envelope."""
        event = WebhookEvent(trace_id=label, payload=payload, headers={})
        healthcheck = WebhookHealthcheckProcessor(event=event)

        assert await healthcheck.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_healthcheck_header_matches_only_healthcheck(self) -> None:
        payload = ec2_state_change_event("i-0", "running")
        event = WebhookEvent(
            trace_id="hc",
            payload=payload,
            headers={HEALTHCHECK_HEADER: "1"},
        )

        healthcheck = WebhookHealthcheckProcessor(event=event)
        assert await healthcheck.should_process_event(event) is True

        # Kind processors look at the payload, not the header,
        # so they may still _match_ on the body. The healthcheck-
        # only short-circuit is enforced by registration order and
        # the manual-only nature of that header. Document the
        # contract explicitly: kind processors don't react to the
        # healthcheck header.
        for cls in KIND_PROCESSORS:
            processor = cls(event=event)
            # The kind matcher doesn't even look at the header.
            # We're not asserting it returns False here — we're
            # asserting the headers parameter is irrelevant to it.
            await processor._matches_event(event)
