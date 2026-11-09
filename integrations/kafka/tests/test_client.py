from unittest.mock import MagicMock
import pytest
from confluent_kafka import TopicPartition, ConsumerGroupTopicPartitions
from kafka_integration.client import KafkaClient


class DummyState:
    def __init__(self, name: str):
        self.name = name


class DummyCoordinator:
    def __init__(self, coord_id: int):
        self.id = coord_id


class DummyGroupDescription:
    def __init__(self, state_name: str = "EMPTY"):
        self.state = DummyState(state_name)
        self.members = []
        self.coordinator = DummyCoordinator(5)
        self.partition_assignor = ""
        self.is_simple_consumer_group = False
        self.authorized_operations = None


@pytest.fixture
def mock_kafka_client(monkeypatch: pytest.MonkeyPatch) -> KafkaClient:
    monkeypatch.setattr(
        "kafka_integration.client.AdminClient",
        lambda conf: MagicMock(
            list_topics=MagicMock(return_value=MagicMock(controller_id=1, brokers={}))
        ),
    )
    client = KafkaClient(
        cluster_name="test-cluster", conf={"bootstrap.servers": "localhost:9092"}
    )
    return client


@pytest.mark.asyncio
async def test_process_consumer_group_includes_committed_offsets(
    mock_kafka_client: KafkaClient,
) -> None:
    group_id = "test-group"
    group_future = MagicMock()
    group_future.result.return_value = DummyGroupDescription(state_name="EMPTY")

    # Mock list_consumer_group_offsets response
    offsets_future = MagicMock()
    mock_partitions = [
        TopicPartition("payments-topic", 0, 18200),
        TopicPartition("payments-topic", 1, 17543),
        TopicPartition("orders-topic", 0, 4321),
        TopicPartition(
            "orders-topic", 1, -1001
        ),  # negative / uncommitted offset should be ignored
    ]
    offsets_future.result.return_value = ConsumerGroupTopicPartitions(
        group_id, mock_partitions
    )
    mock_kafka_client.kafka_admin_client.list_consumer_group_offsets = MagicMock(
        return_value={group_id: offsets_future}
    )

    result = await mock_kafka_client._process_consumer_group(group_id, group_future)

    assert result is not None
    assert result["group_id"] == group_id
    assert result["state"] == "EMPTY"
    assert result["cluster_name"] == "test-cluster"
    assert result["members"] == []
    assert result["offsets"] == {
        "payments-topic": {"0": 18200, "1": 17543},
        "orders-topic": {"0": 4321},
    }


@pytest.mark.asyncio
async def test_process_consumer_group_handles_offset_fetch_failure(
    mock_kafka_client: KafkaClient,
) -> None:
    group_id = "failing-group"
    group_future = MagicMock()
    group_future.result.return_value = DummyGroupDescription(state_name="DEAD")

    # Mock list_consumer_group_offsets throwing exception
    mock_kafka_client.kafka_admin_client.list_consumer_group_offsets = MagicMock(
        side_effect=RuntimeError("Kafka broker timeout")
    )

    result = await mock_kafka_client._process_consumer_group(group_id, group_future)

    assert result is not None
    assert result["group_id"] == group_id
    assert result["state"] == "DEAD"
    assert result["offsets"] == {}
