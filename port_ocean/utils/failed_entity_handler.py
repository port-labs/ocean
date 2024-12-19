from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.models import Entity
from port_ocean.clients.port.types import RequestOptions
from port_ocean.core.handlers.entities_state_applier.port.order_by_entities_dependencies import (
    order_by_entities_dependencies,
)
from typing import (
    Any,
    Callable,
    Tuple,
)
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class FailedEntityHandler:
    _failed_entity_callback_list: list[
        Tuple[
            Entity,
            Tuple[
                Tuple[Entity, RequestOptions, UserAgentType],
                Callable[[Entity, RequestOptions, UserAgentType], Any],
            ],
        ]
    ] = field(default_factory=list)

    def register_failed_upsert_call_arguments(
        self,
        entity: Entity,
        get_port_request_options: RequestOptions,
        user_agent_type: UserAgentType,
        func: Callable[[Entity, RequestOptions, UserAgentType], Any],
    ) -> None:
        logger.debug(
            f"Will retry upserting entity - {entity.identifier} at the end of resync"
        )
        self._failed_entity_callback_list.append(
            (entity, ((entity, get_port_request_options, user_agent_type), func))
        )

    async def handle_failed(self) -> None:
        entity_map: dict[
            str,
            Tuple[
                Tuple[Entity, RequestOptions, UserAgentType],
                Callable[[Entity, RequestOptions, UserAgentType], Any],
            ],
        ] = {
            f"{obj.identifier}-{obj.blueprint}": call
            for obj, call in self._failed_entity_callback_list
        }
        entity_list: list[Entity] = [
            obj for obj, call in self._failed_entity_callback_list
        ]

        sorted_and_mapped = order_by_entities_dependencies(entity_list)
        for obj in sorted_and_mapped:
            call = entity_map.get(f"{obj.identifier}-{obj.blueprint}")
            if call is not None:
                args, func = call
                await func(*args, **{"should_raise": False})

    async def handle_failed_no_sort(self) -> None:
        for obj, call in self._failed_entity_callback_list:
            args, func = call
            await func(*args, **{"should_raise": False})
