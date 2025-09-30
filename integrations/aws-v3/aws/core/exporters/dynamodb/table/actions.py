from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetTableDetailsAction(Action):
    """Fetches detailed information about DynamoDB tables."""

    async def _execute(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tables:
            return []

        # Use asyncio.gather for concurrent API calls
        details = await asyncio.gather(
            *(self._fetch_table_details(table) for table in tables),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                table_name = tables[idx].get("TableName", "unknown")
                logger.error(f"Error fetching details for table '{table_name}': {detail_result}")
                continue
            results.append(cast(Dict[str, Any], detail_result))
        return results

    async def _fetch_table_details(self, table: Dict[str, Any]) -> Dict[str, Any]:
        # Implement DynamoDB describe_table API call
        response = await self.client.describe_table(
            TableName=table["TableName"]
        )

        table_data = response.get("Table", {})
        
        logger.info(f"Successfully fetched details for table {table['TableName']}")

        # Transform AWS response to our model format
        return {
            "TableName": table_data.get("TableName", ""),
            "TableArn": table_data.get("TableArn", ""),
            "TableId": table_data.get("TableId", ""),
            "TableStatus": table_data.get("TableStatus", ""),
            "CreationDateTime": table_data.get("CreationDateTime"),
            "AttributeDefinitions": table_data.get("AttributeDefinitions", []),
            "KeySchema": table_data.get("KeySchema", []),
            "BillingModeSummary": table_data.get("BillingModeSummary"),
            "ProvisionedThroughput": table_data.get("ProvisionedThroughput"),
            "TableSizeBytes": table_data.get("TableSizeBytes"),
            "ItemCount": table_data.get("ItemCount"),
            "GlobalSecondaryIndexes": table_data.get("GlobalSecondaryIndexes"),
            "LocalSecondaryIndexes": table_data.get("LocalSecondaryIndexes"),
            "StreamSpecification": table_data.get("StreamSpecification"),
            "LatestStreamLabel": table_data.get("LatestStreamLabel"),
            "LatestStreamArn": table_data.get("LatestStreamArn"),
            "RestoreSummary": table_data.get("RestoreSummary"),
            "SSEDescription": table_data.get("SSEDescription"),
            "ArchivalSummary": table_data.get("ArchivalSummary"),
            "DeletionProtectionEnabled": table_data.get("DeletionProtectionEnabled"),
        }


class GetTableTagsAction(Action):
    """Fetches tags for DynamoDB tables."""

    async def _execute(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tables:
            return []

        tags = await asyncio.gather(
            *(self._fetch_table_tags(table) for table in tables),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                table_name = tables[idx].get("TableName", "unknown")
                logger.error(f"Error fetching tags for table '{table_name}': {tag_result}")
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_table_tags(self, table: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_of_resource(
                ResourceArn=table.get("TableArn", "")
            )
            logger.info(f"Successfully fetched tags for table {table['TableName']}")
            return {"Tags": response.get("Tags", [])}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                logger.info(f"No tags found for table {table['TableName']}")
                return {"Tags": []}
            else:
                raise


class GetTableBackupStatusAction(Action):
    """Fetches backup status and point-in-time recovery settings for DynamoDB tables."""

    async def _execute(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tables:
            return []

        backup_statuses = await asyncio.gather(
            *(self._fetch_backup_status(table) for table in tables),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, backup_result in enumerate(backup_statuses):
            if isinstance(backup_result, Exception):
                table_name = tables[idx].get("TableName", "unknown")
                logger.error(f"Error fetching backup status for table '{table_name}': {backup_result}")
                continue
            results.append(cast(Dict[str, Any], backup_result))
        return results

    async def _fetch_backup_status(self, table: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.describe_continuous_backups(
                TableName=table["TableName"]
            )
            
            continuous_backups = response.get("ContinuousBackupsDescription", {})
            point_in_time = continuous_backups.get("PointInTimeRecoveryDescription", {})
            
            logger.info(f"Successfully fetched backup status for table {table['TableName']}")
            return {
                "ContinuousBackupsDescription": continuous_backups,
                "PointInTimeRecoveryDescription": point_in_time,
            }
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["ResourceNotFoundException", "TableNotFoundException"]:
                logger.info(f"No backup configuration found for table {table['TableName']}")
                return {
                    "ContinuousBackupsDescription": {},
                    "PointInTimeRecoveryDescription": {},
                }
            else:
                raise


class ListTablesAction(Action):
    """Processes the initial list of DynamoDB tables from AWS."""

    async def _execute(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for table in tables:
            # table here is just the table name from list_tables
            table_name = table if isinstance(table, str) else table.get("TableName", "")
            data = {
                "TableName": table_name,
                # We'll get more details from other actions
            }
            results.append(data)
        return results


class DynamoDBTableActionsMap(ActionMap):
    """Groups all actions for DynamoDB table resource type."""
    defaults: List[Type[Action]] = [
        ListTablesAction,
        GetTableDetailsAction,
        GetTableTagsAction,
    ]
    options: List[Type[Action]] = [
        GetTableBackupStatusAction,
    ]