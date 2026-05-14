import copy
from typing import Any, AsyncGenerator, Iterator
from github.helpers.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import AsyncMock, patch
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.team_exporter import (
    RestTeamExporter,
    GraphQLTeamWithMembersExporter,
)
from github.core.options import ListTeamOptions
from integration import GithubPortAppConfig, GithubTeamConfig, GithubTeamSelector
from port_ocean.context.event import event_context
from github.core.options import SingleTeamOptions

from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
    LIST_EXTERNAL_IDENTITIES_GQL,
)


TEST_TEAMS = [
    {
        "id": 1,
        "slug": "team-alpha",
        "name": "Team Alpha",
        "description": "Alpha team",
    },
    {
        "id": 2,
        "slug": "team-beta",
        "name": "Team Beta",
        "description": "Beta team",
    },
]


@pytest.fixture
def mock_port_app_config() -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[
            GithubTeamConfig(
                kind=ObjectKind.TEAM,
                selector=GithubTeamSelector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".slug",
                            title=".name",
                            blueprint='"githubTeam"',
                            properties={},
                        )
                    )
                ),
            )
        ],
    )


@pytest.mark.asyncio
class TestRestTeamExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestTeamExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", return_value=TEST_TEAMS[0]
        ) as mock_request:
            team = await exporter.get_resource(
                SingleTeamOptions(
                    organization="test-org",
                    slug="team-alpha",
                    include_saml_email=False,
                )
            )

            assert team == {**TEST_TEAMS[0], "__organization": "test-org"}

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/test-org/teams/team-alpha"
            )

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        # Create an async mock to return the test teams
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_TEAMS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = RestTeamExporter(rest_client)

                teams: list[list[dict[str, Any]]] = [
                    batch
                    async for batch in exporter.get_paginated_resources(
                        ListTeamOptions(
                            organization="test-org",
                            include_saml_email=False,
                        )
                    )
                ]

                assert len(teams) == 1
                assert len(teams[0]) == 2
                assert teams[0] == [
                    {**TEST_TEAMS[0], "__organization": "test-org"},
                    {**TEST_TEAMS[1], "__organization": "test-org"},
                ]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org/teams"
                )


MEMBER_PAGE_SIZE_IN_EXPORTER = 10

TEAM_ALPHA_MEMBERS_PAGE1_NODES = [
    {
        "id": f"MEMBER_ALPHA_{i + 1}",
        "login": f"member_alpha_{i + 1}",
        "email": f"member_alpha_{i + 1}@example.com",
        "isSiteAdmin": False,
    }
    for i in range(MEMBER_PAGE_SIZE_IN_EXPORTER)
]
TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO = {
    "hasNextPage": True,
    "endCursor": "cursor_alpha_p1",
}

TEAM_ALPHA_MEMBERS_PAGE2_NODES = [
    {
        "id": "MEMBER_ALPHA_LAST",
        "login": "member_alpha_last",
        "email": "member_alpha_last@example.com",
        "isSiteAdmin": False,
    }
]
TEAM_ALPHA_MEMBERS_PAGE2_PAGEINFO = {
    "hasNextPage": False,
    "endCursor": "cursor_alpha_p2",
}

TEAM_ALPHA_ALL_MEMBERS_NODES = (
    TEAM_ALPHA_MEMBERS_PAGE1_NODES + TEAM_ALPHA_MEMBERS_PAGE2_NODES
)

TEAM_ALPHA_INITIAL = {
    "id": "T_ALPHA",
    "slug": "team-alpha",
    "name": "Team Alpha",
    "description": "Alpha team with paginated members",
    "privacy": "VISIBLE",
    "notificationSetting": "NOTIFICATIONS_ENABLED",
    "url": "https://github.com/org/test-org/teams/team-alpha",
    "members": {
        "nodes": TEAM_ALPHA_MEMBERS_PAGE1_NODES,
        "pageInfo": TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO,
    },
}

# Team Alpha - Resolved state (all members fetched)
TEAM_ALPHA_RESOLVED = {
    "id": "T_ALPHA",
    "slug": "team-alpha",
    "name": "Team Alpha",
    "description": "Alpha team with paginated members",
    "privacy": "VISIBLE",
    "notificationSetting": "NOTIFICATIONS_ENABLED",
    "url": "https://github.com/org/test-org/teams/team-alpha",
    "members": {"nodes": TEAM_ALPHA_ALL_MEMBERS_NODES},  # pageInfo is removed
    "__graphql_privacy": "VISIBLE",
    "__organization": "test-org",
}

# Team Beta - No member pagination needed for this example
TEAM_BETA_MEMBER_NODES = [
    {
        "id": "MEMBER_BETA_1",
        "login": "member_beta_1",
        "email": "member_beta_1@example.com",
        "isSiteAdmin": True,
    }
]
TEAM_BETA_INITIAL = {
    "id": "T_BETA",
    "slug": "team-beta",
    "name": "Team Beta",
    "description": "Beta team, no member pagination",
    "privacy": "SECRET",
    "notificationSetting": "NOTIFICATIONS_DISABLED",
    "url": "https://github.com/org/test-org/teams/team-beta",
    "members": {
        "nodes": TEAM_BETA_MEMBER_NODES,
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    },
}

TEAM_BETA_RESOLVED = {
    "id": "T_BETA",
    "slug": "team-beta",
    "name": "Team Beta",
    "description": "Beta team, no member pagination",
    "privacy": "SECRET",
    "notificationSetting": "NOTIFICATIONS_DISABLED",
    "url": "https://github.com/org/test-org/teams/team-beta",
    "members": {"nodes": TEAM_BETA_MEMBER_NODES},  # pageInfo is removed
    "__graphql_privacy": "SECRET",
    "__organization": "test-org",
}


GET_RESOURCE_TEAM_ALPHA_PAGE1_RESPONSE = {
    "data": {"organization": {"team": TEAM_ALPHA_INITIAL}}
}
GET_RESOURCE_TEAM_ALPHA_PAGE2_RESPONSE = {
    "data": {
        "organization": {
            "team": {
                # Only members part is crucial for the second fetch
                "slug": "team-alpha",
                "id": "T_ALPHA",
                "name": "Team Alpha",
                "description": "Alpha team with paginated members",
                "privacy": "VISIBLE",
                "notificationSetting": "NOTIFICATIONS_ENABLED",
                "url": "https://github.com/org/test-org/teams/team-alpha",
                "members": {
                    "nodes": TEAM_ALPHA_MEMBERS_PAGE2_NODES,
                    "pageInfo": TEAM_ALPHA_MEMBERS_PAGE2_PAGEINFO,
                },
            }
        }
    }
}


@pytest.mark.asyncio
class TestGraphQLTeamExporter:
    @pytest.fixture(autouse=True)
    def patch_page_size(self) -> Iterator[None]:
        with patch.object(
            GraphQLTeamWithMembersExporter,
            "MEMBER_PAGE_SIZE",
            MEMBER_PAGE_SIZE_IN_EXPORTER,
        ):
            yield

    async def test_get_resource_with_member_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        mock_send_api_request = AsyncMock(
            side_effect=[
                copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE1_RESPONSE),
                copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE2_RESPONSE),
            ]
        )

        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        # This test is not about SAML enrichment; stub it so it doesn't
        # consume `send_api_request` via GraphQL pagination.
        with (
            patch.object(graphql_client, "send_api_request", new=mock_send_api_request),
            patch(
                "github.helpers.utils.get_saml_identities",
                new=AsyncMock(return_value={}),
            ),
        ):
            team = await exporter.get_resource(
                SingleTeamOptions(
                    organization="test-org",
                    slug="team-alpha",
                    include_saml_email=False,
                )
            )

            assert team == TEAM_ALPHA_RESOLVED
            assert mock_send_api_request.call_count == 2

            call_args_initial = mock_send_api_request.call_args_list[0]
            expected_variables_initial = {
                "slug": "team-alpha",
                "organization": "test-org",
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
            }
            expected_payload_initial = graphql_client.build_graphql_payload(
                query=FETCH_TEAM_WITH_MEMBERS_GQL, variables=expected_variables_initial
            )
            assert call_args_initial[0][0] == graphql_client.base_url
            assert call_args_initial[1]["method"] == "POST"
            assert call_args_initial[1]["json_data"] == expected_payload_initial

            # Assertions for the second call (triggered by fetch_other_members)
            call_args_page2 = mock_send_api_request.call_args_list[1]
            expected_variables_page2 = {
                "slug": "team-alpha",
                "organization": "test-org",
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO["endCursor"],
            }
            expected_payload_page2 = graphql_client.build_graphql_payload(
                query=FETCH_TEAM_WITH_MEMBERS_GQL, variables=expected_variables_page2
            )
            assert call_args_page2[0][0] == graphql_client.base_url
            assert call_args_page2[1]["method"] == "POST"
            assert call_args_page2[1]["json_data"] == expected_payload_page2

    async def test_get_resource_no_member_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        mock_response_data = copy.deepcopy(
            {"data": {"organization": {"team": TEAM_BETA_INITIAL}}}
        )

        exporter = GraphQLTeamWithMembersExporter(graphql_client)
        # This test is not about SAML enrichment; stub it so it doesn't
        # trigger GraphQL pagination for external identities.
        with (
            patch.object(
                graphql_client,
                "send_api_request",
                new=AsyncMock(return_value=mock_response_data),
            ) as mock_request,
            patch(
                "github.helpers.utils.get_saml_identities",
                new=AsyncMock(return_value={}),
            ),
        ):
            team = await exporter.get_resource(
                SingleTeamOptions(
                    organization="test-org",
                    slug="team-beta",
                    include_saml_email=False,
                )
            )

            assert team == TEAM_BETA_RESOLVED
            mock_request.assert_called_once()

    @pytest.mark.parametrize(
        "mock_response",
        [
            {"data": {"organization": {"team": None}}},
            {"data": {"organization": None}},
            {"data": None},
        ],
        ids=["team_is_null", "organization_is_null", "data_is_null"],
    )
    async def test_get_resource_returns_none_when_graphql_data_missing(
        self,
        graphql_client: GithubGraphQLClient,
        mock_response: dict[str, Any],
    ) -> None:
        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=mock_response),
        ):
            team = await exporter.get_resource(
                SingleTeamOptions(
                    organization="test-org",
                    slug="missing-team",
                    include_saml_email=False,
                )
            )

        assert team is None

    async def test_get_paginated_resources_is_retired(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        with pytest.raises(NotImplementedError):
            exporter.get_paginated_resources(
                ListTeamOptions(
                    organization="test-org",
                    include_saml_email=False,
                )
            )


TEAM_NO_EMAIL_MEMBER_NODES = [
    {
        "id": "MEMBER_NO_EMAIL_1",
        "login": "member_no_email_1",
        "isSiteAdmin": False,
    },
    {
        "id": "MEMBER_NO_EMAIL_2",
        "login": "member_no_email_2",
        "email": "member_with_email@example.com",
        "isSiteAdmin": False,
    },
]

SAML_IDENTITIES_MOCK = [
    {
        "node": {
            "user": {"login": "member_no_email_1"},
            "samlIdentity": {"nameId": "member_no_email_1@saml.example.com"},
        }
    }
]


@pytest.mark.asyncio
class TestGraphQLTeamWithMembersExporterSamlEnrichment:
    @pytest.fixture(autouse=True)
    def patch_page_size(self) -> Iterator[None]:
        with patch.object(
            GraphQLTeamWithMembersExporter,
            "MEMBER_PAGE_SIZE",
            MEMBER_PAGE_SIZE_IN_EXPORTER,
        ):
            yield

    async def test_get_resource_enriches_members_without_email(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        team_initial = {
            "id": "T_NOEMAIL",
            "slug": "team-noemail",
            "name": "Team NoEmail",
            "description": "Team with members missing email",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-noemail",
            "members": {
                "nodes": copy.deepcopy(TEAM_NO_EMAIL_MEMBER_NODES),
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

        async def mock_saml_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield SAML_IDENTITIES_MOCK

        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        with (
            patch.object(
                graphql_client,
                "send_api_request",
                new=AsyncMock(
                    return_value={"data": {"organization": {"team": team_initial}}}
                ),
            ),
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=mock_saml_paginated_request,
            ) as mock_paginated,
        ):
            team = await exporter.get_resource(
                SingleTeamOptions(
                    organization="test-org",
                    slug="team-noemail",
                    include_saml_email=False,
                )
            )

        assert team is not None
        members = team["members"]["nodes"]
        assert members[0]["login"] == "member_no_email_1"
        assert members[0]["email"] == "member_no_email_1@saml.example.com"
        assert members[1]["email"] == "member_with_email@example.com"

        mock_paginated.assert_called_once_with(
            LIST_EXTERNAL_IDENTITIES_GQL,
            {
                "organization": "test-org",
                "first": 100,
                "__path": "organization.samlIdentityProvider.externalIdentities",
                "__node_key": "edges",
            },
        )


@pytest.mark.asyncio
class TestGraphQLTeamWithMembersExporterExtrasEnrichment:
    async def test_enrich_team_with_extras_merges_missing_fields_only(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        base_team = {"slug": "team-alpha", "name": "Team Alpha", "existing": "keep"}
        extras_team = {
            "slug": "team-alpha",
            "name": "Team Alpha",
            "existing": "do-not-overwrite",
            "extra_field": "extra-value",
        }

        mock_get_resource = AsyncMock(return_value=extras_team)
        with patch.object(exporter, "get_resource", new=mock_get_resource):
            teams = await exporter._enrich_team_with_extras(
                [copy.deepcopy(base_team)],
                ListTeamOptions(organization="test-org", include_saml_email=False),
            )

        assert teams[0]["existing"] == "keep"
        assert teams[0]["extra_field"] == "extra-value"
        mock_get_resource.assert_awaited_once_with(
            SingleTeamOptions(
                slug="team-alpha",
                organization="test-org",
                include_saml_email=False,
            )
        )

    async def test_enrich_team_with_extras_skips_when_team_not_found(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        base_team_1 = {"slug": "team-alpha", "name": "Team Alpha"}
        base_team_2 = {"slug": "team-beta", "name": "Team Beta"}

        extras_team_2 = {"slug": "team-beta", "extra_field": "extra-value"}

        mock_get_resource = AsyncMock(side_effect=[None, extras_team_2])
        with patch.object(exporter, "get_resource", new=mock_get_resource):
            teams = await exporter._enrich_team_with_extras(
                [copy.deepcopy(base_team_1), copy.deepcopy(base_team_2)],
                ListTeamOptions(organization="test-org", include_saml_email=False),
            )

        assert "extra_field" not in teams[0]
        assert teams[1]["extra_field"] == "extra-value"
