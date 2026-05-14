from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger

from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleTeamOptions, ListTeamOptions
from github.helpers.gql_queries import (
    FETCH_TEAM_WITH_MEMBERS_GQL,
)
from github.helpers.utils import (
    enrich_members_with_saml_email,
    enrich_with_organization,
)


class GraphQLTeamWithMembersExporter(AbstractGithubExporter[GithubGraphQLClient]):
    MEMBER_PAGE_SIZE = 30

    async def get_resource[
        ExporterOptionT: SingleTeamOptions
    ](self, options: ExporterOptionT) -> Optional[RAW_ITEM]:
        include_saml_email = bool(options["include_saml_email"])
        organization = options["organization"]
        slug = options["slug"]
        variables = {
            "slug": slug,
            "organization": organization,
            "memberFirst": self.MEMBER_PAGE_SIZE,
        }

        payload = self.client.build_graphql_payload(
            FETCH_TEAM_WITH_MEMBERS_GQL, variables
        )
        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        if not response:
            logger.warning(
                f"No team found with slug: {slug} in organization {organization}"
            )
            return None

        data = response.get("data") or {}
        organization_data = data.get("organization")
        if not organization_data:
            logger.warning(
                f"GraphQL response missing organization data for slug: {slug} in organization {organization}"
            )
            return None

        team = organization_data.get("team")
        if not team:
            logger.warning(
                f"Team not found via GraphQL with slug: {slug} in organization {organization}"
            )
            return None

        members_data = team["members"]
        member_nodes = members_data["nodes"]
        member_page_info = members_data["pageInfo"]
        team["__graphql_privacy"] = team["privacy"]

        if member_page_info.get("hasNextPage"):
            all_member_nodes_for_team = await self.get_paginated_members(
                organization=organization,
                team_slug=team["slug"],
                initial_members_page_info=member_page_info,
                initial_member_nodes=member_nodes,
                member_page_size=self.MEMBER_PAGE_SIZE,
            )
            team["members"]["nodes"] = all_member_nodes_for_team

        del team["members"]["pageInfo"]

        await enrich_members_with_saml_email(
            self.client, organization, team["members"]["nodes"], include_saml_email
        )

        return enrich_with_organization(team, organization)

    def get_paginated_resources[
        ExporterOptionT: ListTeamOptions
    ](self, options: ExporterOptionT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError(
            "GraphQL team pagination is retired. Use RestTeamExporter.get_paginated_resources "
            "and GraphQLTeamWithMembersExporter._enrich_team_with_extras for member enrichment."
        )

    async def get_paginated_members(
        self,
        organization: str,
        team_slug: str,
        initial_members_page_info: dict[str, Any],
        initial_member_nodes: list[dict[str, Any]],
        member_page_size: int,
    ) -> list[dict[str, Any]]:
        """
        Fetches all subsequent pages of members for a given team.

        Args:
            team_slug: The slug of the team.
            initial_members_page_info: The pageInfo object from the initial members fetch.
            initial_member_nodes: The list of member nodes from the initial fetch.
            member_page_size: The number of members to fetch per page.

        Returns:
            A complete list of member nodes
        """
        logger.info(f"Fetching additional team members. team_slug='{team_slug}'")

        all_member_nodes = list(initial_member_nodes)
        current_page_info = dict(initial_members_page_info)

        while current_page_info.get("hasNextPage"):
            variables = {
                "organization": organization,
                "slug": team_slug,
                "memberFirst": member_page_size,
                "memberAfter": current_page_info.get("endCursor"),
            }
            payload = self.client.build_graphql_payload(
                FETCH_TEAM_WITH_MEMBERS_GQL, variables
            )

            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )
            if not response or "data" not in response:
                logger.warning(
                    f"No data returned while paginating members for team '{team_slug}', stopping pagination"
                )
                break

            organization_data = (response.get("data") or {}).get("organization")
            team_data = (organization_data or {}).get("team")
            if not team_data:
                logger.warning(
                    f"Team '{team_slug}' missing in GraphQL response while paginating members, stopping pagination"
                )
                break

            new_members_data = team_data["members"]
            all_member_nodes.extend(new_members_data["nodes"])
            current_page_info = new_members_data["pageInfo"]

        logger.info(
            f"Successfully fetched {len(all_member_nodes)} members for team '{team_slug}'"
        )
        return all_member_nodes

    async def _enrich_team_with_extras(
        self,
        teams: list[dict[str, Any]],
        options: ListTeamOptions,
    ) -> list[dict[str, Any]]:
        for team in teams:
            team_extras = await self.get_resource(
                SingleTeamOptions(
                    slug=team["slug"],
                    organization=options["organization"],
                    include_saml_email=options["include_saml_email"],
                )
            )
            if not team_extras:
                continue

            team.update({k: v for k, v in team_extras.items() if k not in team})
        return teams
