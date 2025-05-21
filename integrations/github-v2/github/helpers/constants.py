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


PULL_REQUEST_FIELDS_FRAGMENT = """
fragment PullRequestFields on PullRequest {
  id
  number
  title
  body
  state
  createdAt
  updatedAt
  closedAt
  mergedAt
  author { login }
  assignees(first: 5) { nodes { login } }
  reviewRequests(first: 5) { nodes { requestedReviewer { ... on User { login } } } }
  isDraft
  merged
  mergeStateStatus
}
"""


SINGLE_PULL_REQUEST_GQL = f"""
{PULL_REQUEST_FIELDS_FRAGMENT}
query SinglePullRequestQuery(
  $organization: String!
  $repositoryName: String!
  $pullRequestNumber: Int!
) {{
  organization(login: $organization) {{
    repository(name: $repositoryName) {{
      pullRequest(number: $pullRequestNumber) {{
        ...PullRequestFields
      }}
    }}
  }}
}}
"""


LIST_PULL_REQUEST_GQL = f"""
{PULL_REQUEST_FIELDS_FRAGMENT}
{PAGE_INFO_FRAGMENT}
query PullRequestQuery(
  $organization: String!
  $repositoryName: String!
  $first: Int = 100
  $after: String
  $states: [PullRequestState!]
) {{
  organization(login: $organization) {{
    repository(name: $repositoryName) {{
      pullRequests(
        first: $first
        after: $after
        orderBy: {{field: CREATED_AT, direction: DESC}}
        states: $states
      ) {{
        nodes {{
          ...PullRequestFields
        }}
        ...PageInfoFields
      }}
    }}
  }}
}}
"""
