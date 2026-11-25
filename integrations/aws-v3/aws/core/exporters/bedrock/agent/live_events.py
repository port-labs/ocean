from aws.core.exporters.bedrock.agent.models import SingleAgentRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    CloudTrailEventMapping,
    LiveEventContext,
    LiveEventFactories,
)

CLOUDTRAIL_EVENT_SOURCE = "bedrock.amazonaws.com"


def _extract_agent_id(detail: CloudTrailDetail) -> str | None:
    request_parameters = detail.get("requestParameters", {})
    agent_id = request_parameters.get("agentId")
    if isinstance(agent_id, str):
        return agent_id

    response_elements = detail.get("responseElements")
    if isinstance(response_elements, dict):
        agent = response_elements.get("agent", {})
        if isinstance(agent, dict):
            response_agent_id = agent.get("agentId")
            if isinstance(response_agent_id, str):
                return response_agent_id

    return None


def _request_factory(
    context: LiveEventContext, include_actions: list[str]
) -> SingleAgentRequest:
    return SingleAgentRequest(
        agent_id=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _deletion_identifier_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "agentId": context.identifier,
    }


BEDROCK_AGENT_LIVE_EVENTS = LiveEventFactories(
    request_factory=_request_factory,
    deletion_identifier_properties_factory=_deletion_identifier_properties,
    cloudtrail_mappings={
        "CreateAgent": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_agent_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "UpdateAgent": CloudTrailEventMapping(
            CloudTrailEventAction.UPSERT,
            _extract_agent_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
        "DeleteAgent": CloudTrailEventMapping(
            CloudTrailEventAction.DELETE,
            _extract_agent_id,
            event_source=CLOUDTRAIL_EVENT_SOURCE,
        ),
    },
)
