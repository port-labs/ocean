from __future__ import annotations
from enum import StrEnum, EnumMeta
from typing import Any, Set, Type, Protocol, runtime_checkable
from types import NotImplementedType


@runtime_checkable
class HasValues(Protocol):
    @classmethod
    def values(cls) -> Set[str]: ...


class EventEnumMeta(EnumMeta):
    """
    Nothing fancy here, just a custom metaclass util that allows adding multiple enum classes at the class level to combine their unique values.
    """

    def __add__[
        T: HasValues
    ](cls: Type[T], other: Any) -> Set[str] | NotImplementedType:
        if isinstance(other, type) and issubclass(other, HasValues):
            return set(cls.values()) | set(other.values())
        elif isinstance(other, set):
            return set(cls.values()) | other
        return NotImplemented

    def __radd__[
        T: HasValues
    ](cls: Type[T], other: Any) -> Type[T] | Set[str] | NotImplementedType:
        # Handle case where the class is on the right side of the addition
        if isinstance(other, set):
            return other | set(cls.values())
        return NotImplemented


class EventEnum(StrEnum, metaclass=EventEnumMeta):
    """
    Base event enum class that provides a class method to retrieve all member values.
    """

    @classmethod
    def values(cls) -> set[str]:
        return set(cls._value2member_map_.keys())


class PullRequestEvents(EventEnum):
    PULL_REQUEST_CREATED = "pullrequest:created"
    PULL_REQUEST_UPDATED = "pullrequest:updated"
    PULL_REQUEST_APPROVED = "pullrequest:approved"
    PULL_REQUEST_UNAPPROVED = "pullrequest:unapproved"
    PULL_REQUEST_FULFILLED = "pullrequest:fulfilled"
    PULL_REQUEST_REJECTED = "pullrequest:rejected"


class RepositoryEvents(EventEnum):
    REPOSITORY_CREATED = "repo:created"
    REPOSITORY_UPDATED = "repo:updated"
    REPOSITORY_PUSHED = "repo:push"
