from typing import Any, AsyncGenerator
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import patch, MagicMock
import httpx
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.user_exporter import GraphQLUserExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleUserOptions
from github.helpers.gql_queries import LIST_ORG_MEMBER_GQL


TEST_USERS = [
    {
        "login": "user1",
        "email": "johndoe@email.com",
    },
    {
        "login": "user2",
        "email": "johndoe2@email.com",
    },
]


@pytest.fixture
def mock_port_app_config() -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[
            ResourceConfig(
                kind="user",
                selector=Selector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".login",
                            title=".login",
                            blueprint='"githubUser"',
                            properties={},
                        )
                    )
                ),
            )
        ],
    )


@pytest.mark.asyncio
class TestGraphQLUserExporter:
    async def test_get_resource(self, graphql_client: GithubGraphQLClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"user": TEST_USERS[0]}}

        exporter = GraphQLUserExporter(graphql_client)

        with patch.object(
            graphql_client, "send_api_request", return_value=mock_response
        ) as mock_request:
            user = await exporter.get_resource(SingleUserOptions(login="user1"))

            assert user == TEST_USERS[0]

            expected_query = """
        query ($login: String!) {
            user(login: $login) {
                login
                email
            }
        }
        """
            expected_variables = {"login": "user1"}
            expected_payload = graphql_client.build_graphql_payload(
                query=expected_query, variables=expected_variables
            )
            mock_request.assert_called_once_with(
                graphql_client.base_url, method="POST", json_data=expected_payload
            )

    async def test_get_paginated_resources(
        self,
        graphql_client: GithubGraphQLClient,
    ) -> None:
        # Create an async mock to return the test users
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_USERS

        with patch.object(
            graphql_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = GraphQLUserExporter(graphql_client)

                users: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert len(users) == 1
                assert len(users[0]) == 2
                assert users[0] == TEST_USERS

                expected_variables = {
                    "organization": graphql_client.organization,
                    "__path": "organization.membersWithRole",
                }
                mock_request.assert_called_once_with(
                    LIST_ORG_MEMBER_GQL, expected_variables
                )
