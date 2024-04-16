import base64
from collections.abc import MutableSequence
import json
from typing import Any, TypeVar, TypedDict
from fastapi import Request
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
import proto  # type: ignore
from gcp_core.gcp_client import GCPClient

T = TypeVar("T", bound=proto.Message)


def parse_protobuf_messages(messages: MutableSequence[T]) -> list[dict[str, Any]]:
    return [proto.Message.to_dict(message) for message in messages]


class FeedEvent(TypedDict):
    message_id: str
    asset_name: str
    asset_type: str
    data: dict[Any, Any]


class GotFeedCreatedSuccessfullyMessage(Exception):
    pass


async def parse_feed_event_from_request(
    request: Request,
) -> FeedEvent:
    # The message schema: https://cloud.google.com/pubsub/docs/push?_gl=1*thv8i4*_ga*NDQwMTA2MzM5LjE3MTEyNzQ2MDY.*_ga_WH2QY8WWF5*MTcxMzA3NzU3Ni40My4xLjE3MTMwNzgxMjUuMC4wLjA.&_ga=2.161162040.-440106339.1711274606&_gac=1.184150868.1711468720.CjwKCAjw5ImwBhBtEiwAFHDZx1mm-z19UdKpEARcG2-F_TXXbXw7j7_gVPKiQ9Z5KcpsvXF1fFb_MBoCUFkQAvD_BwE#receive_push
    request_json = await request.json()
    message_id = request_json["message"]["messageId"]
    try:
        data = base64.b64decode(request_json["message"]["data"])
        asset_data = json.loads(data)
    except json.JSONDecodeError as e:
        if data.decode("utf-8").startswith(
            "You have successfully configured real time feed"
        ):
            raise GotFeedCreatedSuccessfullyMessage()
        raise e
    # The Asset schema: https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#creating_feeds
    asset_type = asset_data["asset"]["assetType"]
    asset_name = asset_data["asset"]["name"]
    feed_event = FeedEvent(
        message_id=message_id,
        asset_name=asset_name,
        asset_type=asset_type,
        data=asset_data,
    )
    return feed_event


def create_gcp_client_from_ocean_config() -> GCPClient:
    if cache := event.attributes.get("gcp_client"):
        return cache
    parent = ocean.integration_config["parent"]
    service_account = ocean.integration_config["service_account_file_location"]
    gcp_client = GCPClient(parent, service_account)
    event.attributes["gcp_client"] = gcp_client
    return gcp_client
