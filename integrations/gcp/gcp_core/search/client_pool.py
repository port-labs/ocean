from typing import Type, Optional, Dict
import asyncio
from loguru import logger


class ClientPool[T]:
    _instances: Dict[Type[T], "ClientPool[T]"] = {}

    def __new__(cls, client_class: Type[T]) -> "ClientPool[T]":
        if client_class not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[client_class] = instance
            instance._initialized = False
        return cls._instances[client_class]

    def __init__(self, client_class: Type[T]) -> None:
        if getattr(self, "_initialized", False):
            return
        self.client_class = client_class
        self.client: Optional[T] = None
        self._lock = asyncio.Lock()
        self._initialized = True

    async def __call__(self) -> T:
        async with self._lock:
            if self.client is None:
                logger.debug(f"Creating new {self.client_class.__name__} client")
                self.client = self.client_class()
            return self.client

    async def cleanup(self) -> None:
        async with self._lock:
            if self.client is not None:
                close_method = getattr(self.client, "close", None)
                if callable(close_method):
                    try:
                        if asyncio.iscoroutinefunction(close_method):
                            await close_method()
                        else:
                            close_method()  # For sync close methods, if any
                    except Exception as e:
                        logger.warning(
                            f"Error while closing {type(self.client).__name__}: {e}"
                        )
                self.client = None

    @classmethod
    async def cleanup_all(cls) -> None:
        await asyncio.gather(
            *(instance.cleanup() for instance in cls._instances.values())
        )
        cls._instances.clear()


async def cleanup_all_client_pools() -> None:
    """Cleanup all client pools when the application shuts down"""
    await ClientPool.cleanup_all()
