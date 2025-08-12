from port_ocean.core.event_listener.kafka import KafkaEventListenerSettings
import pytest
from pydantic import ValidationError


def test_default_kafka_settings() -> None:
    """Test default values are properly set"""
    config = KafkaEventListenerSettings(type="KAFKA")
    assert config.type == "KAFKA"
    assert config.security_protocol == "SASL_SSL"
    assert config.authentication_mechanism == "SCRAM-SHA-512"
    assert config.kafka_security_enabled is True
    assert config.consumer_poll_timeout == 1
    assert "b-1-public.publicclusterprod" in config.brokers


def test_brokers_json_array_parsing() -> None:
    """Test that JSON array strings get converted to comma-separated"""
    json_brokers = '["broker1:9092", "broker2:9092", "broker3:9092"]'
    config = KafkaEventListenerSettings(type="KAFKA", brokers=json_brokers)
    assert config.brokers == "broker1:9092,broker2:9092,broker3:9092"


def test_brokers_regular_string_unchanged() -> None:
    """Test that regular comma-separated strings pass through unchanged"""
    regular_brokers = "broker1:9092,broker2:9092"
    config = KafkaEventListenerSettings(type="KAFKA", brokers=regular_brokers)
    assert config.brokers == regular_brokers


def test_brokers_malformed_json_unchanged() -> None:
    """Test that malformed JSON strings don't break validation"""
    bad_json = "[broker1:9092, broker2:9092"
    config = KafkaEventListenerSettings(type="KAFKA", brokers=bad_json)
    assert config.brokers == bad_json


def test_custom_values() -> None:
    """Test overriding default values"""
    config = KafkaEventListenerSettings(
        type="KAFKA",
        brokers="custom:9092",
        security_protocol="PLAINTEXT",
        authentication_mechanism="PLAIN",
        kafka_security_enabled=False,
        consumer_poll_timeout=5,
    )
    assert config.brokers == "custom:9092"
    assert config.security_protocol == "PLAINTEXT"
    assert config.authentication_mechanism == "PLAIN"
    assert config.kafka_security_enabled is False
    assert config.consumer_poll_timeout == 5


def test_type_literal_validation() -> None:
    """Test that type field only accepts KAFKA"""
    with pytest.raises(ValidationError):
        KafkaEventListenerSettings(type="RABBITMQ")  # type: ignore[arg-type]


def test_empty_brokers_array() -> None:
    """Test empty JSON array becomes empty string"""
    config = KafkaEventListenerSettings(type="KAFKA", brokers="[]")
    assert config.brokers == ""


def test_single_broker_array() -> None:
    """Test single broker in JSON array"""
    config = KafkaEventListenerSettings(type="KAFKA", brokers='["single:9092"]')
    assert config.brokers == "single:9092"
