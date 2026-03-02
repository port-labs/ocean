import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from aioboto3 import Session


def _make_session(region: str = "eu-west-3") -> MagicMock:
    """Create a mock session with the given region name."""
    session = MagicMock(spec=Session)
    session.region_name = region
    return session


def _access_denied_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        "ListResources",
    )


def _type_not_found_error() -> ClientError:
    """Benign: the resource type is not registered in this region."""
    return ClientError(
        {"Error": {"Code": "TypeNotFoundException", "Message": "Type not found"}},
        "ListResources",
    )


def _real_error(code: str = "InternalServiceError") -> ClientError:
    """Non-benign: a genuine service error that should block reconciliation."""
    return ClientError(
        {"Error": {"Code": code, "Message": "Something went wrong"}},
        "ListResources",
    )


class MockCredentials:
    """Minimal mock for AwsCredentials that yields sessions for given regions."""

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


# ---------- _safe_region_generator tests ----------


@pytest.mark.asyncio
async def test_safe_region_generator_passes_through_batches() -> None:
    """On success, batches are yielded unchanged."""
    from main import _safe_region_generator

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"id": "1"}]
        yield [{"id": "2"}]

    session = _make_session("us-east-1")
    failed_regions: list[str] = []
    errors: list[Exception] = []

    results = []
    async for batch in _safe_region_generator(
        resync_func, "AWS::S3::Bucket", session, failed_regions, errors
    ):
        results.append(batch)

    assert results == [[{"id": "1"}], [{"id": "2"}]]
    assert failed_regions == []
    assert errors == []


@pytest.mark.asyncio
async def test_safe_region_generator_tracks_real_errors() -> None:
    """Real errors (e.g. InternalServiceError) are caught and recorded as failures."""
    from main import _safe_region_generator

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _real_error("InternalServiceError")
        yield  # make this an async generator

    session = _make_session("eu-west-3")
    failed_regions: list[str] = []
    errors: list[Exception] = []

    results = []
    async for batch in _safe_region_generator(
        resync_func, "AWS::EC2::Instance", session, failed_regions, errors
    ):
        results.append(batch)

    assert results == []
    assert failed_regions == ["eu-west-3"]
    assert len(errors) == 1
    assert isinstance(errors[0], ClientError)


@pytest.mark.asyncio
async def test_safe_region_generator_suppresses_type_not_found() -> None:
    """TypeNotFoundException is benign — suppressed without recording a failure."""
    from main import _safe_region_generator

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _type_not_found_error()
        yield

    session = _make_session("eu-west-3")
    failed_regions: list[str] = []
    errors: list[Exception] = []

    results = []
    async for batch in _safe_region_generator(
        resync_func, "AWS::ResourceGroups::Group", session, failed_regions, errors
    ):
        results.append(batch)

    assert results == []
    assert failed_regions == []
    assert errors == []


@pytest.mark.asyncio
async def test_safe_region_generator_ignores_access_denied() -> None:
    """Access-denied errors are swallowed and NOT recorded as failures."""
    from main import _safe_region_generator

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _access_denied_error()
        yield

    session = _make_session("eu-west-3")
    failed_regions: list[str] = []
    errors: list[Exception] = []

    results = []
    async for batch in _safe_region_generator(
        resync_func, "AWS::ResourceGroups::Group", session, failed_regions, errors
    ):
        results.append(batch)

    assert results == []
    assert failed_regions == []
    assert errors == []


@pytest.mark.asyncio
async def test_safe_region_generator_yields_partial_then_fails() -> None:
    """If some batches succeed before a real error, they are yielded and error is tracked."""
    from main import _safe_region_generator

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"id": "good-1"}]
        raise _real_error("InternalServiceError")

    session = _make_session("eu-west-3")
    failed_regions: list[str] = []
    errors: list[Exception] = []

    results = []
    async for batch in _safe_region_generator(
        resync_func, "AWS::EC2::Instance", session, failed_regions, errors
    ):
        results.append(batch)

    assert results == [[{"id": "good-1"}]]
    assert failed_regions == ["eu-west-3"]
    assert len(errors) == 1


# ---------- _handle_global_resource_resync tests ----------


@pytest.mark.asyncio
async def test_global_resync_tries_next_region_on_non_access_denied() -> None:
    """Non-access-denied error in first region -> try next region instead of raising."""
    from main import _handle_global_resource_resync

    call_log: list[str] = []

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        call_log.append(region)
        if region == "us-east-1":
            raise _real_error("InternalServiceError")
        yield [{"id": "from-" + region}]

    credentials = MockCredentials(["us-east-1", "eu-west-1", "ap-southeast-1"])

    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role",
        credentials,  # type: ignore[arg-type]
        resync_func,
        ["us-east-1", "eu-west-1", "ap-southeast-1"],
    ):
        results.append(batch)

    # Should have tried us-east-1 (failed), then succeeded on eu-west-1
    assert call_log == ["us-east-1", "eu-west-1"]
    assert results == [[{"id": "from-eu-west-1"}]]


@pytest.mark.asyncio
async def test_global_resync_tries_next_region_on_access_denied() -> None:
    """Access-denied in first region -> try next region."""
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


@pytest.mark.asyncio
async def test_global_resync_all_regions_fail_gracefully() -> None:
    """If ALL regions fail, the generator completes empty -- no exception raised."""
    from main import _handle_global_resource_resync

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _real_error("InternalServiceError")
        yield

    credentials = MockCredentials(["us-east-1", "eu-west-1"])

    results = []
    async for batch in _handle_global_resource_resync(
        "AWS::IAM::Role", credentials, resync_func, ["us-east-1", "eu-west-1"]  # type: ignore[arg-type]
    ):
        results.append(batch)

    assert results == []
    # No exception raised -- this is the key assertion (implicit by reaching here)


# ---------- resync_resources_for_account tests ----------


@pytest.mark.asyncio
async def test_resync_benign_errors_do_not_block_reconciliation() -> None:
    """TypeNotFoundException in some regions is benign — no ExceptionGroup raised."""
    from main import resync_resources_for_account

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        if region == "eu-west-3":
            raise _type_not_found_error()
        yield [{"id": f"from-{region}"}]

    credentials = MockCredentials(["us-east-1", "eu-west-3", "ap-southeast-1"])

    mock_event = MagicMock()
    mock_event.resource_config.selector.is_region_allowed = lambda r: True

    results = []
    with (
        patch("main.event", new=mock_event),
        patch("main.is_global_resource", return_value=False),
    ):
        async for batch in resync_resources_for_account(
            credentials, "AWS::ResourceGroups::Group", resync_func  # type: ignore[arg-type]
        ):
            results.append(batch)

    # Healthy regions yielded, no exception → reconciliation will run
    ids = {item["id"] for batch in results for item in batch}
    assert "from-us-east-1" in ids
    assert "from-ap-southeast-1" in ids
    assert len(results) == 2


@pytest.mark.asyncio
async def test_resync_real_errors_raise_exception_group() -> None:
    """Real errors (InternalServiceError) raise ExceptionGroup to block reconciliation."""
    from main import resync_resources_for_account

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        region = session.region_name
        if region == "eu-west-1":
            raise _real_error("InternalServiceError")
        yield [{"id": f"from-{region}"}]

    credentials = MockCredentials(["us-east-1", "eu-west-1", "ap-southeast-1"])

    mock_event = MagicMock()
    mock_event.resource_config.selector.is_region_allowed = lambda r: True

    results = []
    with pytest.raises(ExceptionGroup) as exc_info:
        with (
            patch("main.event", new=mock_event),
            patch("main.is_global_resource", return_value=False),
        ):
            async for batch in resync_resources_for_account(
                credentials, "AWS::EC2::Instance", resync_func  # type: ignore[arg-type]
            ):
                results.append(batch)

    # Healthy regions still yielded before the raise
    ids = {item["id"] for batch in results for item in batch}
    assert "from-us-east-1" in ids
    assert "from-ap-southeast-1" in ids

    # ExceptionGroup contains the real error
    assert len(exc_info.value.exceptions) == 1
    assert "eu-west-1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resync_all_benign_errors_complete_normally() -> None:
    """All regions hit TypeNotFoundException — completes empty, no exception."""
    from main import resync_resources_for_account

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _type_not_found_error()
        yield

    credentials = MockCredentials(["us-east-1", "eu-west-1"])

    mock_event = MagicMock()
    mock_event.resource_config.selector.is_region_allowed = lambda r: True

    results = []
    with (
        patch("main.event", new=mock_event),
        patch("main.is_global_resource", return_value=False),
    ):
        async for batch in resync_resources_for_account(
            credentials, "AWS::ResourceGroups::Group", resync_func  # type: ignore[arg-type]
        ):
            results.append(batch)

    assert results == []


@pytest.mark.asyncio
async def test_resync_all_real_errors_raise_exception_group() -> None:
    """All regions fail with real errors — ExceptionGroup raised."""
    from main import resync_resources_for_account

    async def resync_func(kind: str, session: Any) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise _real_error("InternalServiceError")
        yield

    credentials = MockCredentials(["us-east-1", "eu-west-1"])

    mock_event = MagicMock()
    mock_event.resource_config.selector.is_region_allowed = lambda r: True

    with pytest.raises(ExceptionGroup):
        with (
            patch("main.event", new=mock_event),
            patch("main.is_global_resource", return_value=False),
        ):
            async for batch in resync_resources_for_account(
                credentials, "AWS::EC2::Instance", resync_func  # type: ignore[arg-type]
            ):
                pass


# ---------- _process_tasks tests ----------


@pytest.mark.asyncio
async def test_process_tasks_catches_unexpected_error() -> None:
    """If a generator raises after yielding, _process_tasks catches it and tracks the error."""
    from main import _process_tasks

    async def failing_generator() -> AsyncGenerator[list[dict[str, str]], None]:
        yield [{"id": "ok"}]
        raise RuntimeError("unexpected merge failure")

    failed_regions: list[str] = []
    errors: list[Exception] = []
    tasks: list[Any] = [failing_generator()]

    results = []
    async for batch in _process_tasks(tasks, failed_regions, errors, "us-east-1"):
        results.append(batch)

    assert results == [[{"id": "ok"}]]
    assert "us-east-1" in failed_regions
    assert len(errors) == 1
    assert tasks == []  # cleared in finally block
