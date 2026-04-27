from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.core.exporters.memorydb.user.exporter import MemoryDbUserExporter
from aws.core.exporters.memorydb.user.models import (
    PaginatedMemoryDbUserRequest,
    SingleMemoryDbUserRequest,
)


SAMPLE_USERS = [
    {
        "UserName": "alice",
        "Status": "active",
        "AccessString": "on ~* &* +@all",
        "ACLNames": ["my-acl"],
        "MinimumEngineVersion": "6.2",
        "ARN": "arn:aws:memorydb:us-east-1:123456789012:user/alice",
        "Authentication": {"Type": "password", "PasswordCount": 1},
    }
]


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def paginated_options() -> PaginatedMemoryDbUserRequest:
    return PaginatedMemoryDbUserRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[],
    )


@pytest.fixture
def single_options() -> SingleMemoryDbUserRequest:
    return SingleMemoryDbUserRequest(
        region="us-east-1",
        account_id="123456789012",
        include=[],
        user_name="alice",
    )


async def test_get_paginated_resources_yields_batch(
    mock_session: MagicMock,
    paginated_options: PaginatedMemoryDbUserRequest,
) -> None:
    exporter = MemoryDbUserExporter(mock_session)

    async def fake_paginate(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield SAMPLE_USERS

    mock_paginator = MagicMock()
    mock_paginator.paginate = fake_paginate

    mock_proxy = MagicMock()
    mock_proxy.__aenter__ = AsyncMock(return_value=mock_proxy)
    mock_proxy.__aexit__ = AsyncMock(return_value=None)
    mock_proxy.get_paginator.return_value = mock_paginator

    async def fake_inspect(
        identifiers: Any, include: Any, extra_context: Any = None
    ) -> list[dict[str, Any]]:
        return [{"Type": "AWS::MemoryDB::User", "Properties": u} for u in identifiers]

    mock_inspector = MagicMock()
    mock_inspector.inspect = fake_inspect

    with (
        patch(
            "aws.core.exporters.memorydb.user.exporter.AioBaseClientProxy",
            return_value=mock_proxy,
        ),
        patch(
            "aws.core.exporters.memorydb.user.exporter.ResourceInspector",
            return_value=mock_inspector,
        ),
    ):
        batches = []
        async for batch in exporter.get_paginated_resources(paginated_options):
            batches.append(batch)

    assert len(batches) == 1
    assert batches[0][0]["Properties"]["UserName"] == "alice"


async def test_get_paginated_resources_empty_page_yields_empty(
    mock_session: MagicMock,
    paginated_options: PaginatedMemoryDbUserRequest,
) -> None:
    exporter = MemoryDbUserExporter(mock_session)

    async def fake_paginate(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield []

    mock_paginator = MagicMock()
    mock_paginator.paginate = fake_paginate

    mock_proxy = MagicMock()
    mock_proxy.__aenter__ = AsyncMock(return_value=mock_proxy)
    mock_proxy.__aexit__ = AsyncMock(return_value=None)
    mock_proxy.get_paginator.return_value = mock_paginator

    with (
        patch(
            "aws.core.exporters.memorydb.user.exporter.AioBaseClientProxy",
            return_value=mock_proxy,
        ),
        patch(
            "aws.core.exporters.memorydb.user.exporter.ResourceInspector",
            return_value=MagicMock(),
        ),
    ):
        batches = []
        async for batch in exporter.get_paginated_resources(paginated_options):
            batches.append(batch)

    assert batches == [[]]


async def test_get_resource_returns_single_user(
    mock_session: MagicMock,
    single_options: SingleMemoryDbUserRequest,
) -> None:
    exporter = MemoryDbUserExporter(mock_session)

    expected = {"Type": "AWS::MemoryDB::User", "Properties": SAMPLE_USERS[0]}

    mock_client = MagicMock()
    mock_client.describe_users = AsyncMock(return_value={"Users": SAMPLE_USERS})

    mock_proxy = MagicMock()
    mock_proxy.__aenter__ = AsyncMock(return_value=mock_proxy)
    mock_proxy.__aexit__ = AsyncMock(return_value=None)
    mock_proxy.client = mock_client

    async def fake_inspect(
        identifiers: Any, include: Any, extra_context: Any = None
    ) -> list[dict[str, Any]]:
        return [expected]

    mock_inspector = MagicMock()
    mock_inspector.inspect = fake_inspect

    with (
        patch(
            "aws.core.exporters.memorydb.user.exporter.AioBaseClientProxy",
            return_value=mock_proxy,
        ),
        patch(
            "aws.core.exporters.memorydb.user.exporter.ResourceInspector",
            return_value=mock_inspector,
        ),
    ):
        result = await exporter.get_resource(single_options)

    assert result == expected
    mock_client.describe_users.assert_awaited_once_with(UserName="alice")


async def test_get_resource_returns_empty_when_no_users(
    mock_session: MagicMock,
    single_options: SingleMemoryDbUserRequest,
) -> None:
    exporter = MemoryDbUserExporter(mock_session)

    mock_client = MagicMock()
    mock_client.describe_users = AsyncMock(return_value={"Users": []})

    mock_proxy = MagicMock()
    mock_proxy.__aenter__ = AsyncMock(return_value=mock_proxy)
    mock_proxy.__aexit__ = AsyncMock(return_value=None)
    mock_proxy.client = mock_client

    async def fake_inspect(
        identifiers: Any, include: Any, extra_context: Any = None
    ) -> list[dict[str, Any]]:
        return []

    mock_inspector = MagicMock()
    mock_inspector.inspect = fake_inspect

    with (
        patch(
            "aws.core.exporters.memorydb.user.exporter.AioBaseClientProxy",
            return_value=mock_proxy,
        ),
        patch(
            "aws.core.exporters.memorydb.user.exporter.ResourceInspector",
            return_value=mock_inspector,
        ),
    ):
        result = await exporter.get_resource(single_options)

    assert result == {}
