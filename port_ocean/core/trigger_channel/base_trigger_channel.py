from abc import ABC, abstractmethod


class BaseTriggerChannel:
    @abstractmethod
    def __init__(self, config: dict, on_resync: callable, on_changelog_event: callable):
        self.config = config

    @abstractmethod
    def start(self) -> None:
        pass
