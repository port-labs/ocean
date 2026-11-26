from concurrent.futures import Future
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from confluent_kafka import ConsumerGroupTopicPartitions, TopicPartition

from kafka_integration.client import KafkaClient


def _make_future(value: Any = None, exc: Exception | None = None) -> Future[Any]:
    future: Future[Any] = Future()
    if exc is not None:
        future.set_exception(exc)
    else:
        future.set_result(value)
    return future


def _make_client(mock_admin: MagicMock) -> KafkaClient:
    with patch("kafka_integration.client.AdminClient", return_value=mock_admin):
        return KafkaClient("kafka-staging", {"bootstrap.servers": "localhost:9092"})


@pytest.mark.asyncio
async def test_describe_consumer_groups_includes_committed_offsets_for_empty_group() -> (
    None
):
    mock_admin = MagicMock()
    mock_admin.list_topics.return_value = MagicMock(
        controller_id=1, brokers={}, topics={}
    )

    group_listing = SimpleNamespace(group_id="cg-group-name")
    mock_admin.list_consumer_groups.return_value = _make_future(
        SimpleNamespace(valid=[group_listing])
    )

    group_description = SimpleNamespace(
        state=SimpleNamespace(name="EMPTY"),
        members=[],
        coordinator=SimpleNamespace(id=5),
        partition_assignor="",
        is_simple_consumer_group=False,
        authorized_operations=None,
    )
    mock_admin.describe_consumer_groups.return_value = {
        "cg-group-name": _make_future(group_description)
    }

    offsets_result = ConsumerGroupTopicPartitions(
        "cg-group-name",
        [
            TopicPartition("payments-topic", 0, 18200),
            TopicPartition("payments-topic", 1, 17543),
            TopicPartition("orders-topic", 0, 4321),
        ],
    )
    mock_admin.list_consumer_group_offsets.return_value = {
        "cg-group-name": _make_future(offsets_result)
    }

    client = _make_client(mock_admin)
    batches = [batch async for batch in client.describe_consumer_groups()]

    assert len(batches) == 1
    assert len(batches[0]) == 1
    group = batches[0][0]
    assert group["group_id"] == "cg-group-name"
    assert group["state"] == "EMPTY"
    assert group["members"] == []
    assert group["offsets"] == {
        "payments-topic": {"0": 18200, "1": 17543},
        "orders-topic": {"0": 4321},
    }

    mock_admin.list_consumer_group_offsets.assert_called_once()
    call_args = mock_admin.list_consumer_group_offsets.call_args[0][0]
    assert len(call_args) == 1
    assert isinstance(call_args[0], ConsumerGroupTopicPartitions)
    assert call_args[0].group_id == "cg-group-name"


@pytest.mark.asyncio
async def test_describe_consumer_groups_skips_invalid_and_errored_offsets() -> None:
    mock_admin = MagicMock()
    mock_admin.list_topics.return_value = MagicMock(
        controller_id=1, brokers={}, topics={}
    )

    group_listing = SimpleNamespace(group_id="cg-partial")
    mock_admin.list_consumer_groups.return_value = _make_future(
        SimpleNamespace(valid=[group_listing])
    )

    group_description = SimpleNamespace(
        state=SimpleNamespace(name="DEAD"),
        members=[],
        coordinator=SimpleNamespace(id=2),
        partition_assignor="range",
        is_simple_consumer_group=False,
        authorized_operations=[],
    )
    mock_admin.describe_consumer_groups.return_value = {
        "cg-partial": _make_future(group_description)
    }

    errored_tp = SimpleNamespace(
        topic="broken-topic", partition=0, offset=10, error="UNKNOWN_TOPIC_OR_PART"
    )
    invalid_tp = TopicPartition("uncommitted-topic", 0, -1001)
    valid_tp = TopicPartition("valid-topic", 2, 99)

    offsets_result = SimpleNamespace(
        group_id="cg-partial",
        topic_partitions=[errored_tp, invalid_tp, valid_tp],
    )
    mock_admin.list_consumer_group_offsets.return_value = {
        "cg-partial": _make_future(offsets_result)
    }

    client = _make_client(mock_admin)
    batches = [batch async for batch in client.describe_consumer_groups()]

    assert batches[0][0]["offsets"] == {"valid-topic": {"2": 99}}


@pytest.mark.asyncio
async def test_describe_consumer_groups_returns_empty_offsets_on_offset_fetch_error() -> (
    None
):
    mock_admin = MagicMock()
    mock_admin.list_topics.return_value = MagicMock(
        controller_id=1, brokers={}, topics={}
    )

    group_listing = SimpleNamespace(group_id="cg-error")
    mock_admin.list_consumer_groups.return_value = _make_future(
        SimpleNamespace(valid=[group_listing])
    )

    group_description = SimpleNamespace(
        state=SimpleNamespace(name="EMPTY"),
        members=[],
        coordinator=SimpleNamespace(id=1),
        partition_assignor="range",
        is_simple_consumer_group=False,
        authorized_operations=None,
    )
    mock_admin.describe_consumer_groups.return_value = {
        "cg-error": _make_future(group_description)
    }
    mock_admin.list_consumer_group_offsets.side_effect = RuntimeError("broker error")

    client = _make_client(mock_admin)
    batches = [batch async for batch in client.describe_consumer_groups()]

    assert len(batches) == 1
    assert batches[0][0]["group_id"] == "cg-error"
    assert batches[0][0]["offsets"] == {}
