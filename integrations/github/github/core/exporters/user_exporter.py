from typing import Optional
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import SingleUserOptions, ListUserOptions
from github.helpers.exceptions import GraphQLForbiddenFieldError
from github.helpers.gql_queries import (
    FETCH_GITHUB_USER_GQL,
    FETCH_GITHUB_USER_WITH_VERIFIED_EMAILS_GQL,
    LIST_ORG_MEMBER_GQL,
    LIST_ORG_MEMBER_WITH_VERIFIED_EMAILS_GQL,
)
from github.helpers.utils import enrich_members_with_saml_email


class GraphQLUserExporter(AbstractGithubExporter[GithubGraphQLClient]):
    async def get_resource[ExporterOptionT: SingleUserOptions](
        self, options: ExporterOptionT
    ) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        login_option = options["login"]
        include_saml_email = bool(options["include_saml_email"])
        include_verified_domain_emails = bool(
            options.get("include_verified_domain_emails")
        )

        if include_verified_domain_emails:
            query = FETCH_GITHUB_USER_WITH_VERIFIED_EMAILS_GQL
            variables = {"login": login_option, "organization": organization}
        else:
            query = FETCH_GITHUB_USER_GQL
            variables = {"login": login_option}

        payload = self.client.build_graphql_payload(query, variables)
        try:
            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )
        except GraphQLForbiddenFieldError:
            if not include_verified_domain_emails:
                raise
            logger.warning(
                f"organizationVerifiedDomainEmails returned FORBIDDEN for "
                f"user '{login_option}' in '{organization}', falling back to query without verified emails"
            )
            payload = self.client.build_graphql_payload(
                FETCH_GITHUB_USER_GQL, {"login": login_option}
            )
            response = await self.client.send_api_request(
                self.client.base_url, method="POST", json_data=payload
            )

        if not response:
            logger.warning(f"No user found with login: {login_option}")
            return None

        user = response["data"]["user"]

        await enrich_members_with_saml_email(
            self.client, organization, [user], include_saml_email
        )

        return user

    async def get_paginated_resources[ExporterOptionT: ListUserOptions](
        self, options: ExporterOptionT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        include_saml_email = bool(options["include_saml_email"])
        include_verified_domain_emails = bool(
            options.get("include_verified_domain_emails")
        )

        if include_verified_domain_emails:
            query = LIST_ORG_MEMBER_WITH_VERIFIED_EMAILS_GQL
        else:
            query = LIST_ORG_MEMBER_GQL

        variables = {
            "organization": organization,
            "__path": "organization.membersWithRole",
        }
        try:
            async for users in self.client.send_paginated_request(query, variables):
                await enrich_members_with_saml_email(
                    self.client, organization, users, include_saml_email
                )
                yield users
        except GraphQLForbiddenFieldError:
            if not include_verified_domain_emails:
                raise
            logger.warning(
                f"organizationVerifiedDomainEmails returned FORBIDDEN for "
                f"'{organization}', falling back to query without verified emails"
            )
            async for users in self.client.send_paginated_request(
                LIST_ORG_MEMBER_GQL, variables
            ):
                await enrich_members_with_saml_email(
                    self.client, organization, users, include_saml_email
                )
                yield users
