# Contributing to Ocean - github

## Running locally

#### NOTE: Add your own instructions of how to run github

This could be any gotcha's such as rate limiting, how to setup credentials and so forth

## Archived GraphQL Queries

The following GraphQL queries were previously used in the codebase and are archived here for reference:

```graphql
fragment PageInfoFields on PageInfo {
  hasNextPage
  endCursor
}
```

```graphql
fragment RepositoryFields on Repository {
  id
  name
  nameWithOwner
  description
  url
  homepageUrl
  isPrivate
  createdAt
  updatedAt
  pushedAt
  defaultBranchRef { name }
  languages(first: 1) { nodes { name } }
  visibility
}
```

```graphql
query SingleRepositoryQuery(
  $organization: String!
  $repositoryName: String!
) {
  organization(login: $organization) {
    repository(name: $repositoryName) {
      ...RepositoryFields
    }
  }
}
```

```graphql
query RepositoryQuery(
  $organization: String!
  $first: Int = 25
  $after: String
  $repositoryVisibility: RepositoryVisibility
) {
  organization(login: $organization) {
    repositories(
      first: $first
      after: $after
      orderBy: {field: NAME, direction: ASC}
      visibility: $repositoryVisibility
    ) {
      nodes {
        ...RepositoryFields
      }
      pageInfo {
        ...PageInfoFields
      }
    }
  }
}
```

## Archived GraphQLRepositoryExporter

<details>
<summary>GraphQLRepositoryExporter (archived)</summary>

```python
class GraphQLRepositoryExporter(AbstractGithubExporter[GithubGraphQLClient]):
    """GraphQL exporter for repositories."""

    async def get_resource[
        ExporterOptionsT: SingleRepositoryOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:

        variables = {
            "organization": self.client.organization,
            "repositoryName": options["name"],
            "first": 1,
        }
        payload = {"query": SINGLE_REPOSITORY_GQL, "variables": variables}

        response = await self.client.send_api_request(
            self.client.base_url, method="POST", json_data=payload
        )
        logger.info(f"Fetched repository with identifier: {options['name']}")

        return response.json()["data"]["organization"]["repository"]

    @cache_iterator_result()
    async def get_paginated_resources[
        ExporterOptionsT: Any
    ](self, options: Optional[ExporterOptionsT] = None) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all repositories in the organization with pagination."""

        params: Dict[str, Any] = dict(options) if options else {}
        port_app_config = typing.cast("GithubPortAppConfig", event.port_app_config)

        variables = {
            "organization": self.client.organization,
            "visibility": port_app_config.repository_type,
            "__path": "organization.repositories",
            **params,
        }

        async for repos in self.client.send_paginated_request(
            LIST_REPOSITORY_GQL, variables
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from organization {self.client.organization}"
            )
            yield repos
```

</details>
