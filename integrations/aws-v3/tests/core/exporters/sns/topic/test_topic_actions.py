from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.sns.topic.actions import (
    GetTopicAttributesAction,
    GetTopicTagsAction,
    ListTopicsAction,
    SNSTopicActionsMap,
    SNSTopicActionInput,
    TopicIdentifier,
)
from aws.core.interfaces.action import Action


def _make_input(
    arns: list[str],
    region: str = "us-east-1",
    account_id: str = "123456789012",
) -> SNSTopicActionInput:
    return SNSTopicActionInput(
        items=[TopicIdentifier(topic_arn=arn) for arn in arns],
        region=region,
        account_id=account_id,
    )


class TestListTopicsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTopicsAction:
        return ListTopicsAction(mock_client)

    def test_inheritance(self, action: ListTopicsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListTopicsAction) -> None:
        action_input = _make_input(
            [
                "arn:aws:sns:us-east-1:123456789012:my-topic",
                "arn:aws:sns:us-east-1:123456789012:my-topic.fifo",
            ]
        )

        result = await action._execute(action_input)

        assert len(result) == 2
        assert result[0] == {"TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic"}
        assert result[1] == {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic.fifo"
        }

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListTopicsAction) -> None:
        action_input = _make_input([])
        result = await action._execute(action_input)
        assert result == []


class TestGetTopicAttributesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.get_topic_attributes = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetTopicAttributesAction:
        return GetTopicAttributesAction(mock_client)

    def test_inheritance(self, action: GetTopicAttributesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetTopicAttributesAction) -> None:
        action.client.get_topic_attributes.return_value = {
            "Attributes": {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
                "Owner": "123456789012",
                "DisplayName": "My Topic",
                "SubscriptionsConfirmed": "3",
                "SubscriptionsDeleted": "0",
                "SubscriptionsPending": "1",
                "SignatureVersion": "1",
                "TracingConfig": "PassThrough",
            }
        }

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])
        result = await action._execute(action_input)

        assert len(result) == 1
        assert result[0]["Owner"] == "123456789012"
        assert result[0]["SubscriptionsConfirmed"] == "3"
        assert result[0]["TracingConfig"] == "PassThrough"

        action.client.get_topic_attributes.assert_called_once_with(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic"
        )

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetTopicAttributesAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFound"}},
            operation_name="GetTopicAttributes",
        )
        action.client.get_topic_attributes.side_effect = error

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])
        result = await action._execute(action_input)

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetTopicAttributesAction
    ) -> None:
        def mock_get_attributes(TopicArn: str, **kwargs: Any) -> dict[str, Any]:
            if TopicArn.endswith("topic-2"):
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDenied"}},
                    operation_name="GetTopicAttributes",
                )
            return {"Attributes": {"TopicArn": TopicArn, "Owner": "123456789012"}}

        action.client.get_topic_attributes.side_effect = mock_get_attributes

        action_input = _make_input(
            [
                "arn:aws:sns:us-east-1:123456789012:topic-1",
                "arn:aws:sns:us-east-1:123456789012:topic-2",
                "arn:aws:sns:us-east-1:123456789012:topic-3",
            ]
        )

        result = await action._execute(action_input)

        assert len(result) == 3
        assert result[0]["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:topic-1"
        assert result[1] == {}
        assert result[2]["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:topic-3"

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetTopicAttributesAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="GetTopicAttributes",
        )
        action.client.get_topic_attributes.side_effect = error

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])

        with pytest.raises(ClientError):
            await action._execute(action_input)


class TestGetTopicTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetTopicTagsAction:
        return GetTopicTagsAction(mock_client)

    def test_inheritance(self, action: GetTopicTagsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetTopicTagsAction) -> None:
        action.client.list_tags_for_resource.return_value = {
            "Tags": [
                {"Key": "Environment", "Value": "Production"},
                {"Key": "Team", "Value": "Backend"},
            ]
        }

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])
        result = await action._execute(action_input)

        assert len(result) == 1
        assert len(result[0]["Tags"]) == 2
        assert result[0]["Tags"][0]["Key"] == "Environment"

        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceArn="arn:aws:sns:us-east-1:123456789012:my-topic"
        )

    @pytest.mark.asyncio
    async def test_execute_no_tags(self, action: GetTopicTagsAction) -> None:
        action.client.list_tags_for_resource.return_value = {"Tags": []}

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])
        result = await action._execute(action_input)

        assert len(result) == 1
        assert result[0]["Tags"] == []

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetTopicTagsAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "AccessDenied"}},
            operation_name="ListTagsForResource",
        )
        action.client.list_tags_for_resource.side_effect = error

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])
        result = await action._execute(action_input)

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetTopicTagsAction
    ) -> None:
        def mock_list_tags(ResourceArn: str, **kwargs: Any) -> dict[str, Any]:
            if ResourceArn.endswith("topic-2"):
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDenied"}},
                    operation_name="ListTagsForResource",
                )
            return {"Tags": [{"Key": "Name", "Value": ResourceArn.split(":")[-1]}]}

        action.client.list_tags_for_resource.side_effect = mock_list_tags

        action_input = _make_input(
            [
                "arn:aws:sns:us-east-1:123456789012:topic-1",
                "arn:aws:sns:us-east-1:123456789012:topic-2",
                "arn:aws:sns:us-east-1:123456789012:topic-3",
            ]
        )

        result = await action._execute(action_input)

        assert len(result) == 3
        assert result[0] == {"Tags": [{"Key": "Name", "Value": "topic-1"}]}
        assert result[1] == {}
        assert result[2] == {"Tags": [{"Key": "Name", "Value": "topic-3"}]}

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetTopicTagsAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="ListTagsForResource",
        )
        action.client.list_tags_for_resource.side_effect = error

        action_input = _make_input(["arn:aws:sns:us-east-1:123456789012:my-topic"])

        with pytest.raises(ClientError):
            await action._execute(action_input)


class TestSNSTopicActionsMap:

    def test_defaults(self) -> None:
        actions_map = SNSTopicActionsMap()
        assert ListTopicsAction in actions_map.defaults
        assert GetTopicAttributesAction in actions_map.defaults

    def test_options(self) -> None:
        actions_map = SNSTopicActionsMap()
        assert actions_map.options == [GetTopicTagsAction]
