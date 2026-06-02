from unittest.mock import AsyncMock, MagicMock

import pytest

from aws.core.exporters.memorydb.user.actions import (
    DescribeMemoryDbUsersAction,
    ListTagsForMemoryDbUserAction,
)


SAMPLE_USERS = [
    {
        "Name": "alice",
        "Status": "active",
        "AccessString": "on ~* &* +@all",
        "ACLNames": ["my-acl"],
        "MinimumEngineVersion": "6.2",
        "ARN": "arn:aws:memorydb:us-east-1:123456789012:user/alice",
        "Authentication": {"Type": "password", "PasswordCount": 1},
    },
    {
        "Name": "bob",
        "Status": "active",
        "AccessString": "off",
        "ACLNames": [],
        "MinimumEngineVersion": "6.2",
        "ARN": "arn:aws:memorydb:us-east-1:123456789012:user/bob",
        "Authentication": {"Type": "iam"},
    },
]


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


async def test_describe_memorydb_users_action_returns_users_as_is(
    mock_client: MagicMock,
) -> None:
    action = DescribeMemoryDbUsersAction(mock_client)
    result = await action._execute(SAMPLE_USERS)
    assert result == SAMPLE_USERS


async def test_describe_memorydb_users_action_empty_list(
    mock_client: MagicMock,
) -> None:
    action = DescribeMemoryDbUsersAction(mock_client)
    result = await action._execute([])
    assert result == []


async def test_list_tags_for_memorydb_user_action_fetches_tags(
    mock_client: MagicMock,
) -> None:
    mock_client.list_tags = AsyncMock(
        side_effect=[
            {"TagList": [{"Key": "env", "Value": "prod"}], "ResponseMetadata": {}},
            {"TagList": [], "ResponseMetadata": {}},
        ]
    )
    action = ListTagsForMemoryDbUserAction(mock_client)
    result = await action._execute(SAMPLE_USERS)

    assert len(result) == 2
    assert result[0]["TagList"] == [{"Key": "env", "Value": "prod"}]
    assert result[1]["TagList"] == []
    assert mock_client.list_tags.call_count == 2
    mock_client.list_tags.assert_any_call(
        ResourceArn="arn:aws:memorydb:us-east-1:123456789012:user/alice"
    )
    mock_client.list_tags.assert_any_call(
        ResourceArn="arn:aws:memorydb:us-east-1:123456789012:user/bob"
    )


async def test_list_tags_for_memorydb_user_action_recoverable_error_is_skipped(
    mock_client: MagicMock,
) -> None:
    from botocore.exceptions import ClientError

    recoverable_error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "ListTags",
    )
    mock_client.list_tags = AsyncMock(side_effect=recoverable_error)

    action = ListTagsForMemoryDbUserAction(mock_client)
    result = await action._execute([SAMPLE_USERS[0]])
    assert result == []


async def test_list_tags_for_memorydb_user_action_non_recoverable_error_raises(
    mock_client: MagicMock,
) -> None:
    from botocore.exceptions import ClientError

    non_recoverable = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "oops"}},
        "ListTags",
    )
    mock_client.list_tags = AsyncMock(side_effect=non_recoverable)

    action = ListTagsForMemoryDbUserAction(mock_client)
    with pytest.raises(ClientError):
        await action._execute([SAMPLE_USERS[0]])
