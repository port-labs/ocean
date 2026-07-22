from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class GetTableDetailsAction(Action[list[dict[str, Any]]]):
    async def _execute(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=tables,
            operation_func=self._fetch_table_details,
            get_resource_identifier=lambda t: t["TableName"],
            operation_name="table details",
        )

    async def _fetch_table_details(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.describe_table(TableName=table["TableName"])
        return response["Table"]


class GetTableTagsAction(Action[list[dict[str, Any]]]):
    async def _execute(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=tables,
            operation_func=self._fetch_table_tags,
            get_resource_identifier=lambda t: t["TableArn"],
            operation_name="table tags",
        )

    async def _fetch_table_tags(self, table: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.list_tags_of_resource(
            ResourceArn=table["TableArn"]
        )
        return {"Tags": response["Tags"]}


class GetTableBackupStatusAction(Action[list[dict[str, Any]]]):
    async def _execute(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=tables,
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


class DynamoDBTableActionsMap(ActionMap[list[dict[str, Any]]]):
    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        GetTableDetailsAction,
        GetTableTagsAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = [GetTableBackupStatusAction]
