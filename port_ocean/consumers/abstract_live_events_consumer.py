from abc import ABC, abstractmethod


class AbstractLiveEventsConsumer(ABC):
    """Abstract base class for live-events stream consumers.

    Concrete implementations connect to a specific transport backend
    (Redis Streams, Kafka, SQS, …) and call their ``on_message`` callback
    for every incoming event.  Transport details stay inside the
    implementation; ``LiveEventsProcessorManager`` only depends on this
    interface.
    """

    @abstractmethod
    async def start(self) -> None:
        """Connect to the backend and begin consuming messages."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully disconnect and release all resources."""
        ...
