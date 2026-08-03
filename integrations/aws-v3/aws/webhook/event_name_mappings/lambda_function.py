from typing import Any

from aws.core.helpers.types import ObjectKind
from aws.webhook.event_name_mappings.mapping import CloudTrailEventAction, EventNameMapping


def _extract_lambda_function_name(detail: dict[str, Any]) -> str | None:
    function_name = detail.get("requestParameters", {}).get("functionName")
    return function_name if isinstance(function_name, str) and function_name else None


MAPPINGS: dict[str, EventNameMapping] = {
    "CreateFunction20150331": EventNameMapping(
        ObjectKind.LAMBDA_FUNCTION,
        CloudTrailEventAction.UPSERT,
        _extract_lambda_function_name,
    ),
    "UpdateFunctionConfiguration20150331v2": EventNameMapping(
        ObjectKind.LAMBDA_FUNCTION,
        CloudTrailEventAction.UPSERT,
        _extract_lambda_function_name,
    ),
    "UpdateFunctionCode20150331v2": EventNameMapping(
        ObjectKind.LAMBDA_FUNCTION,
        CloudTrailEventAction.UPSERT,
        _extract_lambda_function_name,
    ),
    "DeleteFunction20150331": EventNameMapping(
        ObjectKind.LAMBDA_FUNCTION,
        CloudTrailEventAction.DELETE,
        _extract_lambda_function_name,
    ),
}
