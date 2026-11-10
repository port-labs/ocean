"""Parser for live-event payloads shaped by an EventBridge input transformer.

The customer's rule names the resource type and identifier explicitly, which is
how custom kinds (with no CloudTrail event mapping) receive live events.
"""

from typing import TypedDict

from aws.core.helpers.metadata.types import CloudTrailEventAction, NormalizedEvent


class InputTransformerPayload(TypedDict, total=False):
    resource_type: str
    identifier: str
    accountId: str
    awsRegion: str
    eventName: str


def is_input_transformer_event(payload: InputTransformerPayload) -> bool:
    return "resource_type" in payload and "detail" not in payload


def parse_input_transformer_event(
    payload: InputTransformerPayload,
) -> NormalizedEvent | None:
    """Parse an input-transformer payload into a normalized upsert event.

    Deletions are detected downstream: the resource is fetched and a not-found
    response is treated as deleted.
    """
    kind = payload.get("resource_type")
    identifier = payload.get("identifier")
    account_id = payload.get("accountId")
    region = payload.get("awsRegion")

    if not kind or not identifier or not account_id or not region:
        return None

    return NormalizedEvent(
        kind=kind,
        identifier=identifier,
        account_id=account_id,
        region=region,
        action=CloudTrailEventAction.UPSERT,
        event_name=payload.get("eventName", ""),
    )
