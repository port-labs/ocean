import base64
import json
from collections.abc import MutableSequence
from typing import Any, TypeVar

import proto  # type: ignore
from fastapi import Request
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from gcp_core.gcp_client import GCPClient
from gcp_core.types import CloudAssetInventoryFeed, SubscriptionMessage

T = TypeVar("T", bound=proto.Message)


class GotFeedCreatedSuccessfullyMessage(Exception):
    pass


def parse_protobuf_messages(messages: MutableSequence[T]) -> list[dict[str, Any]]:
    return [proto.Message.to_dict(message) for message in messages]


async def parse_subscription_message_from_request(request: Request) -> SubscriptionMessage:
    # The message schema: https://cloud.google.com/pubsub/docs/push?_gl=1*thv8i4*_ga*NDQwMTA2MzM5LjE3MTEyNzQ2MDY.*_ga_WH2QY8WWF5*MTcxMzA3NzU3Ni40My4xLjE3MTMwNzgxMjUuMC4wLjA.&_ga=2.161162040.-440106339.1711274606&_gac=1.184150868.1711468720.CjwKCAjw5ImwBhBtEiwAFHDZx1mm-z19UdKpEARcG2-F_TXXbXw7j7_gVPKiQ9Z5KcpsvXF1fFb_MBoCUFkQAvD_BwE#receive_push
    # The Asset schema: https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#creating_feeds
    request_json = await request.json()
    message_id = request_json["message"]["messageId"]
    try:
        data = json.loads(base64.b64decode(request_json["message"]["data"]))
    except json.JSONDecodeError:
        if (
            base64.b64decode(request_json["message"]["data"])
            .decode("utf-8")
            .startswith("You have successfully configured real time feed ")
        ):
            raise GotFeedCreatedSuccessfullyMessage()
    asset_type = data["asset"]["assetType"]
    asset_name = data["asset"]["name"]
    message = SubscriptionMessage(
        message_id=message_id, asset_name=asset_name, asset_type=asset_type, data=data
    )
    return message


def create_feed_from_ocean_config() -> CloudAssetInventoryFeed:
    feed = CloudAssetInventoryFeed()
    feed.id = ocean.integration_config["assets_feed_id"]
    feed.asset_types = (ocean.integration_config["assets_feed_asset_types"]).split(",")
    feed.topic_name = ocean.integration_config["assets_feed_topic_name"]
    return feed


def create_gcp_client_from_ocean_config() -> GCPClient:
    if cache := event.attributes.get("gcp_client"):
        return cache
    try:
        parent = ocean.integration_config["parent"]
        service_account = ocean.integration_config["service_account_file_location"]
    except KeyError as e:
        raise KeyError(f"Missing required integration key: {str(e)}")
    gcp_client = GCPClient(parent, service_account)
    event.attributes["gcp_client"] = gcp_client
    return gcp_client
