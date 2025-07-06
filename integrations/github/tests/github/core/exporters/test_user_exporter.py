from typing import Any, AsyncGenerator
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import copy
import pytest
from unittest.mock import patch
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.user_exporter import GraphQLUserExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleUserOptions
from github.helpers.gql_queries import (
    LIST_ORG_MEMBER_GQL,
    LIST_EXTERNAL_IDENTITIES_GQL,
    FETCH_GITHUB_USER_GQL,
)


TEST_USERS_NO_EMAIL_INITIAL = [
    {
        "login": "user1",
        "email": "johndoe@email.com",
    },
    {
        "login": "user2",
    },
]

EXTERNAL_IDENTITIES_MOCK = [
    {
        "node": {
            "user": {"login": "user2"},
            "samlIdentity": {"nameId": "user2@email.com"},
        }
    }
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
        # Create a mock response data
        mock_response_data = {"data": {"user": TEST_USERS_NO_EMAIL_INITIAL[0]}}

        exporter = GraphQLUserExporter(graphql_client)

        with patch.object(
            graphql_client, "send_api_request", return_value=mock_response_data
        ) as mock_request:
            user = await exporter.get_resource(SingleUserOptions(login="user1"))

            assert user == TEST_USERS_NO_EMAIL_INITIAL[0]

            expected_variables = {"login": "user1"}
            expected_payload = graphql_client.build_graphql_payload(
                query=FETCH_GITHUB_USER_GQL, variables=expected_variables
            )
            mock_request.assert_called_once_with(
                graphql_client.base_url, method="POST", json_data=expected_payload
            )

    async def test_get_resource_no_email_fetches_external_identity(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        mock_user_response_data = {
            "data": {"user": copy.deepcopy(TEST_USERS_NO_EMAIL_INITIAL[1])}
        }

        async def mock_external_identities_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield EXTERNAL_IDENTITIES_MOCK  # EXTERNAL_IDENTITIES_MOCK is for "user2"

        exporter = GraphQLUserExporter(graphql_client)

        with (
            patch.object(
                graphql_client, "send_api_request", return_value=mock_user_response_data
            ) as mock_api_request,
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=mock_external_identities_request,
            ) as mock_paginated_request_identities,
        ):
            user_options = SingleUserOptions(login="user2")
            user = await exporter.get_resource(user_options)

            expected_user = {
                "login": "user2",
                "email": "user2@email.com",  # Email fetched from external identity
            }
            assert user == expected_user

            fetch_user_query_payload = graphql_client.build_graphql_payload(
                query=FETCH_GITHUB_USER_GQL, variables={"login": "user2"}
            )
            mock_api_request.assert_called_once_with(
                graphql_client.base_url,
                method="POST",
                json_data=fetch_user_query_payload,
            )

            mock_paginated_request_identities.assert_called_once_with(
                LIST_EXTERNAL_IDENTITIES_GQL,
                {
                    "organization": graphql_client.organization,
                    "first": 100,
                    "__path": "organization.samlIdentityProvider.externalIdentities",
                    "__node_key": "edges",
                },
            )

    async def test_get_paginated_resources(
        self,
        graphql_client: GithubGraphQLClient,
    ) -> None:
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            # Yield a deep copy to prevent modification of the global constant by other tests
            # or by the code under test if it modifies the list in-place.
            yield copy.deepcopy(TEST_USERS_NO_EMAIL_INITIAL)

        async def mock_paginated_request_with_external_identities(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield EXTERNAL_IDENTITIES_MOCK

        expected_users_after_fetch = [
            {
                "login": "user1",
                "email": "johndoe@email.com",
            },
            {
                "login": "user2",
                "email": "user2@email.com",
            },
        ]

        with patch.object(
            graphql_client,
            "send_paginated_request",
            side_effect=[
                mock_paginated_request(),
                mock_paginated_request_with_external_identities(),
            ],
        ) as mock_request:
            async with event_context("test_event"):
                exporter = GraphQLUserExporter(graphql_client)

                users: list[list[dict[str, Any]]] = []
                async for batch in exporter.get_paginated_resources():
                    users.append(batch)

                assert len(users) == 1
                assert users[0] == expected_users_after_fetch

                mock_request.assert_any_call(
                    LIST_ORG_MEMBER_GQL,
                    {
                        "organization": graphql_client.organization,
                        "__path": "organization.membersWithRole",
                    },
                )
                mock_request.assert_any_call(
                    LIST_EXTERNAL_IDENTITIES_GQL,
                    {
                        "organization": graphql_client.organization,
                        "first": 100,
                        "__path": "organization.samlIdentityProvider.externalIdentities",
                        "__node_key": "edges",
                    },
                )

    async def test_fetch_external_identities_modifies_in_place(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        initial_users = [
            {"login": "user1", "email": "johndoe@email.com"},
            {"login": "user2"},
        ]
        users_no_email = {(1, "user2"): initial_users[1]}

        mock_external_identities = [
            {
                "node": {
                    "user": {"login": "user2"},
                    "samlIdentity": {"nameId": "user2@email.com"},
                }
            }
        ]

        async def mock_paginated_request_external_identities(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield mock_external_identities

        with patch.object(
            graphql_client,
            "send_paginated_request",
            side_effect=[mock_paginated_request_external_identities()],
        ) as mock_request:
            exporter = GraphQLUserExporter(graphql_client)
            await exporter._fetch_external_identities(initial_users, users_no_email)

            expected_users = [
                {"login": "user1", "email": "johndoe@email.com"},
                {"login": "user2", "email": "user2@email.com"},
            ]

            assert initial_users == expected_users

            mock_request.assert_called_once_with(
                LIST_EXTERNAL_IDENTITIES_GQL,
                {
                    "organization": graphql_client.organization,
                    "first": 100,
                    "__path": "organization.samlIdentityProvider.externalIdentities",
                    "__node_key": "edges",
                },
            )
