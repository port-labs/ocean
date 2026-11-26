from aws.core.exporters.bedrock_agent_core.runtime.models import (
    SingleBedrockAgentCoreRuntimeRequest,
)
from aws.core.exporters.bedrock_agent_core.runtime.utils import (
    build_agent_runtime_arn,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

# The control-plane API signs as "bedrock-agentcore".
CLOUDTRAIL_EVENT_SOURCE = "bedrock-agentcore.amazonaws.com"

RUNTIME_ARN_RESOURCE_PREFIX = ":runtime/"


def _runtime_id_from_arn(runtime_arn: str) -> str | None:
    _, separator, runtime_id = runtime_arn.partition(RUNTIME_ARN_RESOURCE_PREFIX)
    return runtime_id if separator and runtime_id else None


def _extract_runtime_id(detail: CloudTrailDetail) -> str | None:
    """Runtime ID from the request (Update/Delete) or the response (Create)."""
    request_parameters = detail.get("requestParameters") or {}
    runtime_id = request_parameters.get("agentRuntimeId")
    if isinstance(runtime_id, str) and runtime_id:
        return runtime_id

    response_elements = detail.get("responseElements") or {}
    runtime_id = response_elements.get("agentRuntimeId")
    if isinstance(runtime_id, str) and runtime_id:
        return runtime_id

    runtime_arn = response_elements.get("agentRuntimeArn")
    if isinstance(runtime_arn, str):
        return _runtime_id_from_arn(runtime_arn)

    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleBedrockAgentCoreRuntimeRequest:
    return SingleBedrockAgentCoreRuntimeRequest(
        agent_runtime_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "AgentRuntimeArn": build_agent_runtime_arn(
            context.region, context.account_id, context.identifier
        ),
        "AgentRuntimeId": context.identifier,
    }


# TagResource / UntagResource are shared by every AgentCore resource type under
# this event source, and a mapping key can point at one kind only, so they are
# not mapped here; tag changes are picked up on the next resync.
BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateAgentRuntime": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_runtime_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateAgentRuntime": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_runtime_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteAgentRuntime": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_runtime_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
