from collections.abc import MutableSequence
import enum
from typing import Any, TypeVar
import proto  # type: ignore

T = TypeVar("T", bound=proto.Message)


def parse_protobuf_message(message: T) -> dict[str, Any]:
    return proto.Message.to_dict(message)


def parse_protobuf_messages(messages: MutableSequence[T]) -> list[dict[str, Any]]:
    return [parse_protobuf_message(message) for message in messages]


EXTRA_PROJECT_FIELD = "__project"


class AssetTypesWithSpecialHandling(enum.StrEnum):
    TOPIC = "pubsub.googleapis.com/Topic"
    PROJECT = "cloudresourcemanager.googleapis.com/Project"
    ORGANIZATION = "cloudresourcemanager.googleapis.com/Organization"
    FOLDER = "cloudresourcemanager.googleapis.com/Folder"
