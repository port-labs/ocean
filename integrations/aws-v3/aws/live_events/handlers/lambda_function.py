from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import SingleLambdaFunctionRequest
from aws.live_events.handlers.base import BaseLiveEventHandler

# CloudTrail eventNames that signal a Lambda function has been removed.
_DELETE_EVENT_NAMES = {"DeleteFunction20150331"}

# CloudTrail eventNames that signal a Lambda function was created or updated.
_UPSERT_EVENT_NAMES = {
    "CreateFunction20150331",
    "UpdateFunctionCode20150331v2",
    "UpdateFunctionConfiguration20150331v2",
}


class LambdaFunctionLiveEventHandler(BaseLiveEventHandler):
    kind = "AWS::Lambda::Function"

    def __init__(self, session: AioSession) -> None:
        self._session = session

    async def handle(self, event: dict[str, Any], account_id: str, region: str) -> None:
        detail = event.get("detail", {})
        detail_type: str = event.get("detail-type", "")
        event_name: str = detail.get("eventName", "")

        # Lambda live events come via CloudTrail. The function name is in
        # requestParameters for all Lambda CloudTrail events.
        request_params: dict[str, Any] = detail.get("requestParameters", {}) or {}
        function_name: str = request_params.get("functionName", "")

        if not function_name:
            logger.warning(
                f"[Lambda] event missing requestParameters.functionName, skipping",
                extra={"account_id": account_id, "region": region, "detail_type": detail_type, "event_name": event_name},
            )
            return

        logger.info(
            f"[Lambda] received function event",
            extra={
                "kind": self.kind,
                "account_id": account_id,
                "region": region,
                "detail_type": detail_type,
                "event_name": event_name,
                "function": function_name,
            },
        )

        if event_name in _DELETE_EVENT_NAMES:
            logger.info(f"[Lambda] function {function_name} deleted, removing from Port")
            await self._delete(function_name)
            return

        if event_name not in _UPSERT_EVENT_NAMES:
            logger.info(f"[Lambda] unhandled eventName {event_name!r}, skipping")
            return

        exporter = LambdaFunctionExporter(self._session)
        options = SingleLambdaFunctionRequest(
            region=region,
            account_id=account_id,
            function_name=function_name,
            include=[],
        )

        try:
            resource = await exporter.get_resource(options)
        except Exception as exc:
            logger.error(f"[Lambda] failed to fetch function {function_name}: {exc}")
            return

        logger.info(
            f"[Lambda] upserting function",
            extra={"kind": self.kind, "account_id": account_id, "region": region, "outcome": "upsert"},
        )
        await self._upsert(resource)
