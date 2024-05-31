import enum
from port_ocean.context.event import event


class CustomProperties(enum.StrEnum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class ResourceKinds(enum.StrEnum):
    ACCOUNT = "AWS::Organizations::Account"


def get_matching_kinds_and_blueprints_from_config(
    kind: str,
) -> dict[str, list[str]]:
    kinds: dict[str, list[str]] = {}
    resources = event.port_app_config.resources

    for resource in resources:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        if resource.kind in kinds:
            kinds[resource.kind].append(blueprint)
        elif kind == resource.kind:
            kinds[resource.kind] = [blueprint]

    return kinds
