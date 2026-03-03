import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from aioboto3 import Session


def _make_session(region: str = "eu-west-3") -> MagicMock:
    session = MagicMock(spec=Session)
    session.region_name = region
    return session


def _access_denied_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        "ListResources",
    )


def _type_not_found_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "TypeNotFoundException", "Message": "Type not found"}},
        "ListResources",
    )


def _real_error(code: str = "InternalServiceError") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "Something went wrong"}},
        "ListResources",
    )


class MockCredentials:
    def __init__(self, regions: list[str], account_id: str = "123456789012") -> None:
        self._regions = regions
        self.account_id = account_id
        self.enabled_regions = regions

    async def create_session_for_each_region(
        self, allowed_regions: list[str] | None = None
    ) -> AsyncGenerator[MagicMock, None]:
        regions = allowed_regions or self._regions
        for r in regions:
            yield _make_session(r)


async def test_global_resync_succeeds_first_region() -> None:
    from main import _handle_global_resource_resync

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"id": "from-" + session.region_name}]

    credentials = MockCredentials(["us-east-1", "eu-west-1"])
    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert results == [[{"id": "from-us-east-1"}]]


async def test_global_resync_skips_access_denied_tries_next() -> None:
    from main import _handle_global_resource_resync

    call_log: list[str] = []

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        call_log.append(region)
        if region == "us-east-1":
            raise _access_denied_error()
        yield [{"id": "from-" + region}]

    credentials = MockCredentials(["us-east-1", "eu-west-1"])
    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert call_log == ["us-east-1", "eu-west-1"]
    assert results == [[{"id": "from-eu-west-1"}]]


async def test_global_resync_skips_type_not_found() -> None:
    """TypeNotFoundException is benign — region is skipped without raising."""
    from main import _handle_global_resource_resync

    call_log: list[str] = []

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        call_log.append(region)
        if region == "us-east-1":
            raise _type_not_found_error()
        yield [{"id": "from-" + region}]

    credentials = MockCredentials(["us-east-1", "eu-west-1"])
    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert "us-east-1" in call_log
    assert results == [[{"id": "from-eu-west-1"}]]


async def test_global_resync_all_type_not_found_completes_empty() -> None:
    """All regions hit TypeNotFoundException — completes with no data and no exception."""
    from main import _handle_global_resource_resync

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _type_not_found_error()
        yield  # noqa: unreachable

    credentials = MockCredentials(["us-east-1", "eu-west-1"])
    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert results == []


async def test_global_resync_real_error_raises() -> None:
    """A real error (not access-denied, not type-not-found) propagates immediately."""
    from main import _handle_global_resource_resync

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _real_error()
        yield  # noqa: unreachable

    credentials = MockCredentials(["us-east-1", "eu-west-1"])
    with pytest.raises(ClientError):
        async for _ in _handle_global_resource_resync(
            "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
        ):
            pass
