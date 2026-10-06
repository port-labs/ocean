from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from wiz.options import ParallelismConfig


@dataclass(frozen=True)
class PaginationPartition:
    label: str
    filter_overlay: dict[str, Any]


class PartitionStrategy(ABC):
    @property
    @abstractmethod
    def resource_name(self) -> str:
        pass

    @abstractmethod
    def build_partitions(
        self,
        variables: dict[str, Any],
        config: ParallelismConfig,
    ) -> list[PaginationPartition]:
        pass
