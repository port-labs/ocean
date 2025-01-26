from loguru import logger

from port_ocean.utils import http_async_client
from typing import Any


class AmplicationClient:
    def __init__(self, api_url: str, authorization: str):
        self.api_url = api_url
        self.authorization = authorization
        self.client = http_async_client

    @property
    async def auth_headers(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.authorization}",
            "Content-Type": "application/json",
        }

    async def get_templates(self) -> list[dict[str, Any]]:
        logger.info("Getting templates from Amplication")

        # GraphQL query
        query = """
        query searchCatalog($where: ResourceWhereInputWithPropertiesFilter, $take: Int, $skip: Int) {
            catalog(where: $where, take: $take, skip: $skip) {
                totalCount
                data {
                    id
                    name
                    description
                    resourceType
                    project {
                        id
                        name
                    }
                }
                __typename
            }
        }
        """

        # Variables for the query
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["ServiceTemplate"]}},
        }

        payload = {
            "query": query,
            "variables": variables,
        }
        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=await self.auth_headers,
        )
        response.raise_for_status()
        return response.json()["data"]["catalog"]["data"]

    async def get_resources(self) -> list[dict[str, Any]]:
        logger.info("Getting resources from Amplication")

        # GraphQL query
        query = """
        query searchCatalog($where: ResourceWhereInputWithPropertiesFilter, $take: Int, $skip: Int) {
            catalog(where: $where, take: $take, skip: $skip) {
                totalCount
                data {
                    id
                    name
                    description
                    resourceType
                    project {
                        id
                        name
                    }
                    serviceTemplate {
                        id
                        name
                        projectId
                    }
                    gitRepository {
                        name
                        gitOrganization {
                            name
                            provider
                        }
                    }
                }
                __typename
            }
        }
        """

        # Variables for the query
        variables = {
            "take": 100,
            "skip": 0,
            "where": {"resourceType": {"in": ["Service", "ProjectConfiguration"]}},
        }

        payload = {
            "query": query,
            "variables": variables,
        }
        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=await self.auth_headers,
        )
        response.raise_for_status()
        return response.json()["data"]["catalog"]["data"]

    async def get_alerts(self) -> list[dict[str, Any]]:
        logger.info("Getting alerts from Amplication")

        # GraphQL query
        query = """
        fragment OutdatedVersionAlertFields on OutdatedVersionAlert {
          id
          createdAt
          updatedAt
          resourceId
          blockId
          block {
            id
            displayName
          }
          type
          outdatedVersion
          latestVersion
          status
        }
        query getOutdatedVersionAlerts(
          $where: OutdatedVersionAlertWhereInput
          $orderBy: OutdatedVersionAlertOrderByInput
          $take: Int
          $skip: Int
        ) {
          outdatedVersionAlerts(
            where: $where
            orderBy: $orderBy
            take: $take
            skip: $skip
          ) {
            ...OutdatedVersionAlertFields
          }
          _outdatedVersionAlertsMeta(where: $where) {
            count
          }
        }
        """

        # Variables for the query
        variables = {
            "orderBy": {"createdAt": "Desc"},
            "take": 100,
            "skip": 0,
            "where": {
                "status": {"equals": "New"},
            },
        }

        payload = {
            "query": query,
            "variables": variables,
        }
        response = await self.client.post(
            self.api_url,
            json=payload,
            headers=await self.auth_headers,
        )
        response.raise_for_status()
        return response.json()["data"]["outdatedVersionAlerts"]
