from abc import ABC, abstractmethod


class BaseConsumer(ABC):
    @abstractmethod
    def start(self) -> None:
        pass
