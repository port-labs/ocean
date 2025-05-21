PAGE_INFO_FRAGMENT = """
fragment PageInfoFields on PageInfo {
  hasNextPage
  endCursor
}
"""

REPOSITORY_FIELDS_FRAGMENT = """
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
"""


SINGLE_REPOSITORY_GQL = f"""
{REPOSITORY_FIELDS_FRAGMENT}
query SingleRepositoryQuery(
  $organization: String!
  $repositoryName: String!
) {{
  organization(login: $organization) {{
    repository(name: $repositoryName) {{
      ...RepositoryFields
    }}
  }}
}}
"""


LIST_REPOSITORY_GQL = f"""
{REPOSITORY_FIELDS_FRAGMENT}
{PAGE_INFO_FRAGMENT}
query RepositoryQuery(
  $organization: String!
  $first: Int = 25
  $after: String
) {{
  organization(login: $organization) {{
    repositories(
      first: $first
      after: $after
      orderBy: {{field: NAME, direction: ASC}}
    ) {{
      nodes {{
        ...RepositoryFields
      }}
      ...PageInfoFields
    }}
  }}
}}
"""
