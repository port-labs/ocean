from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)


def port_resource_config() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".guid",
                title=".name",
                blueprint="newRelicService",
                properties={},
            )
        )
    )
