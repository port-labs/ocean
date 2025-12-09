from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MappedEntity:
    """Represents the entity after applying the mapping

    This class holds the mapping entity along with the selector boolean value and optionally the raw data.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    did_entity_pass_selector: bool = False
    raw_data: Optional[dict[str, Any] | tuple[dict[str, Any], str]] = None
    raw_data_index: Optional[int] = None
    misconfigurations: dict[str, str] = field(default_factory=dict)
