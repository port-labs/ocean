from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListRestApisAction(Action):
    """Processes the initial list of REST APIs from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            data = {
                "Id": resource["id"],
                "Name": resource.get("name", ""),
                "Description": resource.get("description"),
                "CreatedDate": resource.get("createdDate"),
                "Version": resource.get("version"),
                "BinaryMediaTypes": resource.get("binaryMediaTypes", []),
                "MinimumCompressionSize": resource.get("minimumCompressionSize"),
                "ApiKeySource": resource.get("apiKeySource"),
                "EndpointConfiguration": resource.get("endpointConfiguration"),
                "Policy": resource.get("policy"),
                "DisableExecuteApiEndpoint": resource.get("disableExecuteApiEndpoint"),
            }
            results.append(data)
        return results


class GetRestApiDetailsAction(Action):
    """Fetches detailed information about REST APIs."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        details = await asyncio.gather(
            *(self._fetch_rest_api_details(resource) for resource in resources),
            return_exceptions=True,  # Don't fail entire batch if one fails
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                resource_id = resources[idx].get("Id", "unknown")
                logger.error(f"Error fetching details for REST API '{resource_id}': {detail_result}")
                continue
            results.append(cast(Dict[str, Any], detail_result))
        return results

    async def _fetch_rest_api_details(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        # Get detailed information for the REST API
        response = await self.client.get_rest_api(
            restApiId=resource["Id"]
        )

        logger.info(f"Successfully fetched details for REST API {resource['Id']}")

        # Transform AWS response to our model format
        return {
            "Id": response.get("id", ""),
            "Name": response.get("name", ""),
            "Description": response.get("description"),
            "Version": response.get("version"),
            "CreatedDate": response.get("createdDate").isoformat() if response.get("createdDate") else None,
            "BinaryMediaTypes": response.get("binaryMediaTypes", []),
            "MinimumCompressionSize": response.get("minimumCompressionSize"),
            "ApiKeySource": response.get("apiKeySource"),
            "EndpointConfiguration": response.get("endpointConfiguration"),
            "Policy": response.get("policy"),
            "DisableExecuteApiEndpoint": response.get("disableExecuteApiEndpoint"),
        }


class GetRestApiTagsAction(Action):
    """Fetches tags for REST APIs."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(self._fetch_rest_api_tags(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                resource_id = resources[idx].get("Id", "unknown")
                logger.error(f"Error fetching tags for REST API '{resource_id}': {tag_result}")
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_rest_api_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Get the ARN for the REST API
            rest_api_arn = f"arn:aws:apigateway:{self.context.get('Region', '')}::/restapis/{resource['Id']}"
            
            response = await self.client.get_tags(
                resourceArn=rest_api_arn
            )
            return {"Tags": response.get("tags", {})}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["NotFoundException", "BadRequestException"]:
                logger.info(f"No tags found for REST API {resource['Id']}")
                return {"Tags": {}}
            else:
                raise


class RestApiActionsMap(ActionMap):
    """Groups all actions for REST API resource type."""
    defaults: List[Type[Action]] = [
        ListRestApisAction,
        GetRestApiDetailsAction,
        GetRestApiTagsAction,
    ]
    options: List[Type[Action]] = [
        # Add optional actions here if needed
    ]