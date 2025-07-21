from .abstract_queue import AbstractQueue
from .memory_queue import MemoryQueue
from .disk_queue import DiskQueue
from enum import Enum


class QueueType(Enum):
    MEMORY = "MEMORY"
    DISK = "DISK"


__all__ = ["AbstractQueue", "MemoryQueue", "DiskQueue", "QueueType"]
