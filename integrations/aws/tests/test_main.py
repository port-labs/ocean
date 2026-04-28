import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from aioboto3 import Session

from utils.misc import safe_iterate


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


def _region_not_enabled_error(
    code: str = "InvalidClientTokenId",
) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "Token is not valid"}},
        "AssumeRole",
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


async def test_safe_iterate_yields_all_items() -> None:
    """Normal iteration passes through all items."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"a": 1}]
        yield [{"b": 2}]

    results = []
    async for batch in safe_iterate(gen(), "us-east-1", "TestKind", [], []):
        results.append(batch)
    assert results == [[{"a": 1}], [{"b": 2}]]


async def test_safe_iterate_suppresses_access_denied() -> None:
    """Access denied errors are logged and suppressed."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"a": 1}]
        raise _access_denied_error()

    errors: list[Exception] = []
    results = []
    async for batch in safe_iterate(gen(), "us-east-1", "TestKind", errors, []):
        results.append(batch)
    assert results == [[{"a": 1}]]
    assert errors == []


async def test_safe_iterate_suppresses_type_not_found() -> None:
    """TypeNotFoundException is suppressed."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _type_not_found_error()

    errors: list[Exception] = []
    results = []
    async for batch in safe_iterate(gen(), "us-east-1", "TestKind", errors, []):
        results.append(batch)
    assert results == []
    assert errors == []


async def test_safe_iterate_collects_real_errors() -> None:
    """Real errors are collected, not re-raised, when errors list is provided."""
    real_err = _real_error()

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise real_err

    errors: list[Exception] = []
    failed_regions: list[str] = []
    results = []
    async for batch in safe_iterate(
        gen(), "us-east-1", "TestKind", errors, failed_regions
    ):
        results.append(batch)
    assert results == []
    assert len(errors) == 1
    assert errors[0] is real_err
    assert failed_regions == ["us-east-1"]


async def test_region_error_isolation_in_merge() -> None:
    """One iterator failing does not prevent other iterators from completing."""
    errors: list[Exception] = []
    failed: list[str] = []

    async def good_region() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"region": "us-west-2", "data": "ok"}]

    async def bad_region() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _real_error()

    tasks = [
        safe_iterate(
            good_region(),
            "us-west-2",
            "TestKind",
            errors,
            failed,
        ),
        safe_iterate(
            bad_region(),
            "us-east-1",
            "TestKind",
            errors,
            failed,
        ),
    ]

    results = []
    async for batch in stream_async_iterators_tasks(*tasks):
        results.append(batch)

    # Good iterator's data should come through
    assert [{"region": "us-west-2", "data": "ok"}] in results
    # Bad iterator's error should be collected
    assert len(errors) == 1
    assert failed == ["us-east-1"]


async def test_multiple_failures_collected_across_merge() -> None:
    """Multiple failing iterators each have their errors collected independently."""
    errors: list[Exception] = []
    failed: list[str] = []

    async def good_region() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"region": "eu-west-1", "data": "ok"}]

    async def bad_region_1() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _real_error("InternalServiceError")

    async def bad_region_2() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _real_error("ThrottlingException")

    tasks = [
        safe_iterate(
            good_region(),
            "eu-west-1",
            "TestKind",
            errors,
            failed,
        ),
        safe_iterate(
            bad_region_1(),
            "us-east-1",
            "TestKind",
            errors,
            failed,
        ),
        safe_iterate(
            bad_region_2(),
            "ap-south-1",
            "TestKind",
            errors,
            failed,
        ),
    ]

    results = []
    async for batch in stream_async_iterators_tasks(*tasks):
        results.append(batch)

    assert [{"region": "eu-west-1", "data": "ok"}] in results
    assert len(errors) == 2
    assert set(failed) == {"us-east-1", "ap-south-1"}


async def test_safe_iterate_suppresses_region_not_enabled() -> None:
    """InvalidClientTokenId from opt-in regions is suppressed."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"a": 1}]
        raise _region_not_enabled_error("InvalidClientTokenId")

    errors: list[Exception] = []
    failed: list[str] = []
    results = []
    async for batch in safe_iterate(gen(), "af-south-1", "TestKind", errors, failed):
        results.append(batch)
    assert results == [[{"a": 1}]]
    assert errors == []
    assert failed == []


async def test_safe_iterate_suppresses_region_disabled() -> None:
    """RegionDisabledException is suppressed."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _region_not_enabled_error("RegionDisabledException")

    errors: list[Exception] = []
    failed: list[str] = []
    results = []
    async for batch in safe_iterate(
        gen(), "ap-southeast-4", "TestKind", errors, failed
    ):
        results.append(batch)
    assert results == []
    assert errors == []
    assert failed == []


async def test_global_resync_skips_region_not_enabled() -> None:
    """Global resync skips a region that raises InvalidClientTokenId."""
    from main import _handle_global_resource_resync

    call_log: list[str] = []

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        call_log.append(region)
        if region == "af-south-1":
            raise _region_not_enabled_error("InvalidClientTokenId")
        yield [{"id": "from-" + region}]

    credentials = MockCredentials(["af-south-1", "eu-west-1"])
    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["af-south-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert call_log == ["af-south-1", "eu-west-1"]
    assert results == [[{"id": "from-eu-west-1"}]]


async def test_safe_iterate_suppresses_unrecognized_client_in_opt_in_region() -> None:
    """UnrecognizedClientException from opt-in regions is suppressed as region-not-supported."""

    async def gen() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []
        raise _region_not_enabled_error("UnrecognizedClientException")

    errors: list[Exception] = []
    failed: list[str] = []
    results = []
    async for batch in safe_iterate(
        gen(), "ap-southeast-4", "AWS::ResourceGroups::Group", errors, failed
    ):
        results.append(batch)
    assert results == []
    assert errors == []
    assert failed == []
