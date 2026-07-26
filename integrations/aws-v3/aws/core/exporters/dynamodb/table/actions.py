from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations


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
            get_resource_identifier=lambda t: t["TableName"],
            operation_name="table details",
        )

    async def _fetch_table_details(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_table(TableName=table["TableName"])
        return response["Table"]


class GetTableTagsAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_table_tags,
            get_resource_identifier=lambda t: t["TableArn"],
            operation_name="table tags",
        )

    async def _fetch_table_tags(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.list_tags_of_resource(
            ResourceArn=table["TableArn"]
        )
        return {"Tags": response["Tags"]}


class GetTableBackupStatusAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_backup_status,
            get_resource_identifier=lambda t: t["TableName"],
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
