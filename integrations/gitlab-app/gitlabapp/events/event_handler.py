import asyncio
from collections import defaultdict
from typing import List, Dict, Awaitable, Callable


class SingletonMeta(type):
    """
    The Singleton class can be implemented in different ways in Python. Some
    possible methods include: base class, decorator, metaclass. We will use the
    metaclass because it is best suited for this purpose.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class EventHandler(metaclass=SingletonMeta):
    def __init__(self):
        self._observers: Dict[
            str, List[Callable[[str, str, dict], Awaitable]]
        ] = defaultdict(list)

    def on(self, events: List[str], observer):
        for event in events:
            self._observers[event].append(observer)

    async def notify(self, event: str, group_id: str, data):
        return asyncio.gather(
            *[observer(event, group_id, data) for observer in self._observers[event]]
        )
