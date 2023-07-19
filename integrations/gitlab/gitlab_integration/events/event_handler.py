import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Any


class SingletonMeta(type):
    """
    The Singleton class can be implemented in different ways in Python. Some
    possible methods include: base class, decorator, metaclass. We will use the
    metaclass because it is best suited for this purpose.
    """

    _instances: dict["SingletonMeta", "SingletonMeta"] = {}

    def __call__(cls, *args: list[Any], **kwargs: dict[str, Any]) -> "SingletonMeta":
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


Observer = Callable[[str, str, dict[str, Any]], Awaitable[Any]]


class EventHandler(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._observers: dict[str, list[Observer]] = defaultdict(list)

    def on(self, events: list[str], observer: Observer) -> None:
        for event in events:
            self._observers[event].append(observer)

    async def notify(
        self, event: str, group_id: str, body: dict[str, Any]
    ) -> Awaitable[Any]:
        return asyncio.gather(
            *(observer(event, group_id, body) for observer in self._observers[event])
        )
