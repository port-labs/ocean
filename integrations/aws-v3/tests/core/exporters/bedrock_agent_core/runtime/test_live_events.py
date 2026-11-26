from unittest.mock import patch

from aws.core.exporters.bedrock_agent_core.runtime.live_events import (
    BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS,
    CLOUDTRAIL_EVENT_SOURCE,
)
from aws.core.exporters.bedrock_agent_core.runtime.models import (
    SingleBedrockAgentCoreRuntimeRequest,
)
from aws.core.helpers.metadata.types import (
    CloudTrailDetail,
    CloudTrailEventAction,
    LiveEventContext,
)

_ACCOUNT_ID = "123456789012"
_REGION = "us-east-1"
_RUNTIME_ID = "my_runtime-Ab1Cd2Ef3G"
_RUNTIME_ARN = (
    f"arn:aws:bedrock-agentcore:{_REGION}:{_ACCOUNT_ID}:runtime/{_RUNTIME_ID}"
)


def _context(identifier: str) -> LiveEventContext:
    return LiveEventContext(
        identifier=identifier, account_id=_ACCOUNT_ID, region=_REGION
    )


def _extract(event_name: str, detail: CloudTrailDetail) -> str | None:
    mapping = BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS.cloudtrail_mappings[event_name]
    return mapping.extract_identifier(detail)


def test_mapped_events() -> None:
    mappings = BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS.cloudtrail_mappings

    assert {name: mapping.action for name, mapping in mappings.items()} == {
        "CreateAgentRuntime": CloudTrailEventAction.UPSERT,
        "UpdateAgentRuntime": CloudTrailEventAction.UPSERT,
        "DeleteAgentRuntime": CloudTrailEventAction.DELETE,
    }
    assert all(
        mapping.event_source == CLOUDTRAIL_EVENT_SOURCE for mapping in mappings.values()
    )
    assert CLOUDTRAIL_EVENT_SOURCE == "bedrock-agentcore.amazonaws.com"


def test_update_and_delete_extract_id_from_request() -> None:
    detail: CloudTrailDetail = {"requestParameters": {"agentRuntimeId": _RUNTIME_ID}}

    assert _extract("UpdateAgentRuntime", detail) == _RUNTIME_ID
    assert _extract("DeleteAgentRuntime", detail) == _RUNTIME_ID


def test_create_extracts_id_from_response() -> None:
    detail: CloudTrailDetail = {
        "requestParameters": {"agentRuntimeName": "my_runtime"},
        "responseElements": {
            "agentRuntimeId": _RUNTIME_ID,
            "agentRuntimeArn": _RUNTIME_ARN,
        },
    }

    assert _extract("CreateAgentRuntime", detail) == _RUNTIME_ID


def test_create_falls_back_to_response_arn() -> None:
    detail: CloudTrailDetail = {
        "requestParameters": {"agentRuntimeName": "my_runtime"},
        "responseElements": {"agentRuntimeArn": _RUNTIME_ARN},
    }

    assert _extract("CreateAgentRuntime", detail) == _RUNTIME_ID


def test_returns_none_without_runtime_id() -> None:
    detail: CloudTrailDetail = {"requestParameters": {}, "responseElements": {}}

    assert _extract("CreateAgentRuntime", detail) is None


def test_request_factory() -> None:
    request = BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS.request_factory(
        _context(_RUNTIME_ID), ["ListAgentRuntimeTagsAction"]
    )

    assert isinstance(request, SingleBedrockAgentCoreRuntimeRequest)
    assert request.agent_runtime_id == _RUNTIME_ID
    assert request.region == _REGION
    assert request.account_id == _ACCOUNT_ID
    assert request.include == ["ListAgentRuntimeTagsAction"]


@patch(
    "aws.core.exporters.bedrock_agent_core.runtime.utils.RegionHelper.get_partition",
    return_value="aws",
)
def test_deletion_identifier_properties_match_the_arn_identifier(_: object) -> None:
    properties = (
        BEDROCK_AGENT_CORE_RUNTIME_LIVE_EVENTS.deletion_identifier_properties_factory(
            _context(_RUNTIME_ID)
        )
    )

    assert properties == {
        "AgentRuntimeArn": _RUNTIME_ARN,
        "AgentRuntimeId": _RUNTIME_ID,
    }
