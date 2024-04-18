from collections.abc import MutableSequence
import enum
from typing import Any

import proto  # type: ignore

EXTRA_PROJECT_FIELD = "__project"


def parse_protobuf_message(message: proto.Message) -> dict[str, Any]:
    return proto.Message.to_dict(message)


def parse_protobuf_messages(
    messages: MutableSequence[proto.Message],
) -> list[dict[str, Any]]:
    return [parse_protobuf_message(message) for message in messages]


class AssetTypesWithSpecialHandling(enum.StrEnum):
    TOPIC = "pubsub.googleapis.com/Topic"
    PROJECT = "cloudresourcemanager.googleapis.com/Project"
    ORGANIZATION = "cloudresourcemanager.googleapis.com/Organization"
    FOLDER = "cloudresourcemanager.googleapis.com/Folder"
