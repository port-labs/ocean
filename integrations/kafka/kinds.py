from enum import StrEnum


class ObjectKind(StrEnum):
    CLUSTER = "cluster"
    BROKER = "broker"
    TOPIC = "topic"
    CONSUMER_GROUP = "consumer_group"
