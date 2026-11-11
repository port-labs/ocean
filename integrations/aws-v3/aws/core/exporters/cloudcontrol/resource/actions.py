from dataclasses import dataclass
from typing import Any, Type

from aws.core.helpers.utils import (
    execute_concurrent_aws_operations,
    parse_json_object_dict,
)
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput

GET_RESOURCE_CONCURRENCY_LIMIT = 10


@dataclass
class CloudControlResourceIdentifier:
    identifier: str
    properties: dict[str, Any]


@dataclass
class CloudControlActionInput(BaseActionInput[CloudControlResourceIdentifier]):
    type_name: str


class ListResourcesAction(Action[CloudControlActionInput]):
    async def _execute(
        self, resources: CloudControlActionInput
    ) -> list[dict[str, Any]]:
        return [
            {**item.properties, "Identifier": item.identifier}
            for item in resources.items
        ]


class GetResourceAction(Action[CloudControlActionInput]):
    async def _execute(
        self, resources: CloudControlActionInput
    ) -> list[dict[str, Any]]:
        type_name = resources.type_name

        async def fetch_resource(
            item: CloudControlResourceIdentifier,
        ) -> dict[str, Any]:
            response = await self.client.get_resource(
                TypeName=type_name, Identifier=item.identifier
            )
            description = response["ResourceDescription"]
            return {
                **parse_json_object_dict(description.get("Properties")),
                "Identifier": description.get("Identifier", item.identifier),
            }

        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=fetch_resource,
            get_resource_identifier=lambda item: item.identifier,
            operation_name="Cloud Control GetResource",
            concurrency_limit=GET_RESOURCE_CONCURRENCY_LIMIT,
        )


class CloudControlActionsMap(ActionMap[CloudControlActionInput]):
    defaults: list[Type[Action[CloudControlActionInput]]] = [ListResourcesAction]
    options: list[Type[Action[CloudControlActionInput]]] = [GetResourceAction]
