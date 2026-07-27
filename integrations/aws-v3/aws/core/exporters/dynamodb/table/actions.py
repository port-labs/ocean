from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations
from aws.utils import RegionHelper


@dataclass
class DynamoDBTableActionInput(BaseActionInput[dict[str, Any]]):
    region: str
    account_id: str


class ListTablesAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return resources.items


class GetTableDetailsAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_table_details,
            get_resource_identifier=lambda table: table["TableName"],
            operation_name="table details",
        )

    async def _fetch_table_details(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_table(TableName=table["TableName"])
        return response["Table"]


class GetTableTagsAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        partition = RegionHelper.get_partition()

        async def fetch_tags(table: dict[str, Any]) -> dict[str, Any]:
            arn = f"arn:{partition}:dynamodb:{resources.region}:{resources.account_id}:table/{table['TableName']}"
            response = await self.client.list_tags_of_resource(ResourceArn=arn)
            return {"Tags": response["Tags"]}

        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=fetch_tags,
            get_resource_identifier=lambda table: table["TableName"],
            operation_name="table tags",
        )


class GetTableBackupStatusAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_backup_status,
            get_resource_identifier=lambda table: table["TableName"],
            operation_name="table backup status",
        )

    async def _fetch_backup_status(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_continuous_backups(
            TableName=table["TableName"]
        )
        return {
            "ContinuousBackupsDescription": response["ContinuousBackupsDescription"]
        }


class DynamoDBTableActionsMap(ActionMap[DynamoDBTableActionInput]):
    defaults: list[Type[Action[DynamoDBTableActionInput]]] = [
        ListTablesAction,
        GetTableDetailsAction,
    ]
    options: list[Type[Action[DynamoDBTableActionInput]]] = [
        GetTableTagsAction,
        GetTableBackupStatusAction,
    ]
