from collections import OrderedDict
import time
from typing import Optional


class InMemoryDeduper:
    """Simple fixed-size in-memory dedupe store keyed by message id with TTL."""

    def __init__(self, max_items: int = 1000, ttl_seconds: int = 300):
        self.max_items = max_items
        self.ttl = ttl_seconds
        self.store = OrderedDict()  # message_id -> expiry_ts

    def _evict_if_needed(self):
        while len(self.store) > self.max_items:
            self.store.popitem(last=False)

    def add(self, message_id: str) -> None:
        expiry = time.time() + self.ttl
        if message_id in self.store:
            # update expiry and move to end
            self.store.pop(message_id, None)
        self.store[message_id] = expiry
        self._evict_if_needed()

    def contains(self, message_id: str) -> bool:
        expiry = self.store.get(message_id)
        if not expiry:
            return False
        if expiry < time.time():
            # expired
            self.store.pop(message_id, None)
            return False
        return True
