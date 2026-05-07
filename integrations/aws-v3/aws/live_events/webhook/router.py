"""
Event router.

Takes a parsed EventBridge event envelope (unwrapped from the SNS message)
and dispatches it to the correct per-kind handler based on detail-type and source.
"""

import asyncio
import json
from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from aws.live_events.handlers.base import BaseLiveEventHandler
from aws.live_events.handlers.ec2 import EC2InstanceLiveEventHandler
from aws.live_events.handlers.ecs import ECSServiceLiveEventHandler
from aws.live_events.handlers.lambda_function import LambdaFunctionLiveEventHandler
from aws.live_events.handlers.s3 import S3BucketLiveEventHandler

# Maps (source, detail-type) tuples to the handler class.
# A None detail-type entry acts as a wildcard for that source.
_HANDLER_REGISTRY: dict[tuple[str, str], type[BaseLiveEventHandler]] = {
    ("aws.ec2", "EC2 Instance State-change Notification"): EC2InstanceLiveEventHandler,
    ("aws.ecs", "ECS Service Action"): ECSServiceLiveEventHandler,
    ("aws.ecs", "ECS Deployment State Change"): ECSServiceLiveEventHandler,
    ("aws.lambda", "AWS API Call via CloudTrail"): LambdaFunctionLiveEventHandler,
    ("aws.s3", "AWS API Call via CloudTrail"): S3BucketLiveEventHandler,
}


def _resolve_handler(
    source: str, detail_type: str, session: AioSession
) -> BaseLiveEventHandler | None:
    handler_cls = _HANDLER_REGISTRY.get((source, detail_type))
    if handler_cls is None:
        return None
    return handler_cls(session)


async def route_event(event: dict[str, Any], session: AioSession) -> None:
    """
    Route a single EventBridge event to its handler.

    Pulls account_id and region from the EventBridge envelope so handlers
    don't need to parse them individually.
    """
    source: str = event.get("source", "")
    detail_type: str = event.get("detail-type", "")
    account_id: str = event.get("account", "")
    region: str = event.get("region", "")

    logger.info(
        f"[router] event received",
        extra={
            "source": source,
            "detail_type": detail_type,
            "account_id": account_id,
            "region": region,
        },
    )

    handler = _resolve_handler(source, detail_type, session)
    if handler is None:
        logger.info(
            f"[router] no handler for source={source!r} detail-type={detail_type!r}, discarding"
        )
        return

    try:
        await handler.handle(event, account_id, region)
    except Exception as exc:
        logger.error(
            f"[router] handler {handler.__class__.__name__} raised: {exc}",
            extra={"source": source, "detail_type": detail_type, "account_id": account_id},
        )


async def route_sns_notification(sns_message: dict[str, Any], session: AioSession) -> None:
    """
    Unwrap an SNS notification and route the inner EventBridge event(s).

    SNS wraps the EventBridge event as a JSON string in the `Message` field.
    A single SNS notification contains exactly one EventBridge event.
    """
    raw_message: str = sns_message.get("Message", "")
    if not raw_message:
        logger.warning("[router] SNS notification has empty Message field, skipping")
        return

    try:
        event: dict[str, Any] = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        logger.error(f"[router] failed to parse SNS Message as JSON: {exc}")
        return

    await route_event(event, session)
