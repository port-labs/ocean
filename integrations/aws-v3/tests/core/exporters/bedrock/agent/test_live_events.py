from aws.core.exporters.bedrock.agent.live_events import (
    BEDROCK_AGENT_LIVE_EVENTS,
    CLOUDTRAIL_EVENT_SOURCE,
)
from aws.core.exporters.bedrock.agent.models import SingleAgentRequest
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    LiveEventContext,
)

_ACCOUNT_ID = "123456789012"
_REGION = "us-east-1"


def _context(identifier: str) -> LiveEventContext:
    return LiveEventContext(
        identifier=identifier, account_id=_ACCOUNT_ID, region=_REGION
    )


def _extract(event_name: str, detail: CloudTrailDetail) -> str | None:
    mapping = BEDROCK_AGENT_LIVE_EVENTS.cloudtrail_mappings[event_name]
    return mapping.extract_identifier(detail)


def test_mapped_events() -> None:
    mappings = BEDROCK_AGENT_LIVE_EVENTS.cloudtrail_mappings

    assert {name: mapping.action for name, mapping in mappings.items()} == {
        "CreateAgent": CloudTrailEventAction.UPSERT,
        "UpdateAgent": CloudTrailEventAction.UPSERT,
        "PrepareAgent": CloudTrailEventAction.UPSERT,
        "DeleteAgent": CloudTrailEventAction.DELETE,
    }
    assert all(
        mapping.event_source == CLOUDTRAIL_EVENT_SOURCE for mapping in mappings.values()
    )


def test_extracts_agent_id_from_request_parameters() -> None:
    detail: CloudTrailDetail = {"requestParameters": {"agentId": "ABCDEF1234"}}

    assert _extract("UpdateAgent", detail) == "ABCDEF1234"
    assert _extract("DeleteAgent", detail) == "ABCDEF1234"


def test_create_extracts_agent_id_from_response() -> None:
    detail: CloudTrailDetail = {
        "requestParameters": {"agentName": "my-agent"},
        "responseElements": {"agent": {"agentId": "ABCDEF1234"}},
    }

    assert _extract("CreateAgent", detail) == "ABCDEF1234"


def test_returns_none_without_agent_id() -> None:
    detail: CloudTrailDetail = {"requestParameters": {}, "responseElements": {}}

    assert _extract("CreateAgent", detail) is None


def test_request_factory() -> None:
    request = BEDROCK_AGENT_LIVE_EVENTS.request_factory(
        _context("ABCDEF1234"), ["ListAgentTagsAction"]
    )

    assert isinstance(request, SingleAgentRequest)
    assert request.agent_id == "ABCDEF1234"
    assert request.region == _REGION
    assert request.account_id == _ACCOUNT_ID
    assert request.include == ["ListAgentTagsAction"]


def test_deletion_identifier_properties_match_the_arn_identifier() -> None:
    properties = BEDROCK_AGENT_LIVE_EVENTS.deletion_identifier_properties_factory(
        _context("ABCDEF1234")
    )

    assert properties == {
        "AgentArn": f"arn:aws:bedrock:{_REGION}:{_ACCOUNT_ID}:agent/ABCDEF1234",
        "AgentId": "ABCDEF1234",
    }
