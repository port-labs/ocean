from dataclasses import dataclass
from typing import Any

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError
from loguru import logger
from types_aiobotocore_iam import IAMClient
from types_aiobotocore_iam.type_defs import ContextEntryTypeDef

from aws.core.helpers.utils import is_access_denied_exception, is_throttling_exception
from aws.utils import RegionHelper

MISSING_SIMULATE_PERMISSIONS_MESSAGE = (
    "IAM policy simulation is not permitted. Add iam:SimulatePrincipalPolicy and "
    "iam:GetContextKeysForPrincipalPolicy to PortOceanReadRole."
)

_REGION_CONTEXT_KEYS = frozenset({"aws:requestedregion", "aws:region"})


@dataclass(frozen=True)
class SimulateOutcome:
    decisions: dict[str, str]
    missing_simulate_permission: bool = False
    throttled: bool = False
    error_message: str | None = None


async def _get_context_entries(
    iam: IAMClient,
    policy_source_arn: str,
    region: str,
) -> list[ContextEntryTypeDef]:
    context_keys_response = await iam.get_context_keys_for_principal_policy(
        PolicySourceArn=policy_source_arn,
    )

    return [
        {
            "ContextKeyName": key,
            "ContextKeyValues": [region],
            "ContextKeyType": "string",
        }
        for key in context_keys_response.get("ContextKeyNames", [])
        if key.lower() in _REGION_CONTEXT_KEYS
    ]


async def simulate_principal_policy(
    session: AioSession,
    policy_source_arn: str,
    action_names: list[str],
    region: str,
) -> SimulateOutcome:
    if not action_names:
        return SimulateOutcome(decisions={})

    try:
        async with session.create_client(
            "iam",
            region_name=await RegionHelper.get_custom_partition_region_or_none(session),
        ) as iam:
            kwargs: dict[str, Any] = {
                "PolicySourceArn": policy_source_arn,
                "ActionNames": action_names,
            }

            context_entries = await _get_context_entries(iam, policy_source_arn, region)
            if context_entries:
                kwargs["ContextEntries"] = context_entries

            decisions: dict[str, str] = {}
            while True:
                response = await iam.simulate_principal_policy(**kwargs)
                for result in response.get("EvaluationResults", []):
                    action = result.get("EvalActionName")
                    decision = result.get("EvalDecision")
                    if isinstance(action, str) and isinstance(decision, str):
                        decisions[action] = decision
                if not response.get("IsTruncated"):
                    break
                marker = response.get("Marker")
                if not marker:
                    break
                kwargs["Marker"] = marker

            return SimulateOutcome(decisions=decisions)
    except ClientError as error:
        if is_access_denied_exception(error):
            logger.warning("IAM policy simulation is not permitted")
            return SimulateOutcome(
                decisions={},
                missing_simulate_permission=True,
                error_message=MISSING_SIMULATE_PERMISSIONS_MESSAGE,
            )
        if is_throttling_exception(error):
            return SimulateOutcome(
                decisions={},
                throttled=True,
                error_message=(
                    "IAM policy simulation was throttled. This may be temporary."
                ),
            )
        error_response = getattr(error, "response", None)
        error_code = (
            error_response.get("Error", {}).get("Code")
            if isinstance(error_response, dict)
            else None
        )
        logger.exception("IAM policy simulation failed: {}", error)
        return SimulateOutcome(
            decisions={},
            error_message=f"IAM policy simulation failed: {error_code or error}",
        )
