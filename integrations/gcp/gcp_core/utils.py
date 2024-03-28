from typing import Any, TypeVar
from collections.abc import MutableSequence
import proto # type: ignore

T = TypeVar("T", bound=proto.Message)


def parseProtobufMessages(messages: MutableSequence[T]) -> list[dict[str, Any]]:
    return [
        proto.Message.to_dict(message)
        for message in messages
    ]
