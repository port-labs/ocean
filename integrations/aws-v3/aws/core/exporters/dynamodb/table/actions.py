from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations


@dataclass
class TableIdentifier:
    table_name: str
    table_arn: str


@dataclass
class DynamoDBTableActionInput(BaseActionInput[TableIdentifier]):
    region: str
    account_id: str


class ListTablesAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return [
            {"TableName": table.table_name, "TableArn": table.table_arn}
            for table in resources.items
        ]


class GetTableDetailsAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_table_details,
            get_resource_identifier=lambda table: table.table_name,
            operation_name="table details",
        )

    async def _fetch_table_details(self, table: TableIdentifier) -> dict[str, Any]:
        response = await self.client.describe_table(TableName=table.table_name)
        return response["Table"]


class GetTableTagsAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_table_tags,
            get_resource_identifier=lambda table: table.table_name,
            operation_name="table tags",
        )

    async def _fetch_table_tags(self, table: TableIdentifier) -> dict[str, Any]:
        response = await self.client.list_tags_of_resource(ResourceArn=table.table_arn)
        return {"Tags": response["Tags"]}


class GetTableBackupStatusAction(Action[DynamoDBTableActionInput]):
    async def _execute(
        self, resources: DynamoDBTableActionInput
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_backup_status,
            get_resource_identifier=lambda table: table.table_name,
            operation_name="table backup status",
        )

    async def _fetch_backup_status(self, table: TableIdentifier) -> dict[str, Any]:
        response = await self.client.describe_continuous_backups(
            TableName=table.table_name
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
