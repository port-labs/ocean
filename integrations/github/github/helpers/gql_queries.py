PAGE_INFO_FRAGMENT = """
fragment PageInfoFields on PageInfo {
  hasNextPage
  endCursor
}
"""

LIST_ORG_MEMBER_GQL = f"""
{PAGE_INFO_FRAGMENT}
query OrgMemberQuery(
  $organization: String!
  $first: Int = 25
  $after: String
) {{
    organization(login: $organization) {{
      membersWithRole(
        first: $first
        after: $after
      ) {{
        nodes {{
          login
          email
        }}
        pageInfo {{
        ...PageInfoFields
        }}
      }}
    }}
}}
"""

FETCH_GITHUB_USER_GQL = """
        query ($login: String!) {
            user(login: $login) {
                login
                email
            }
        }
        """

LIST_TEAM_MEMBERS_GQL = f"""
{PAGE_INFO_FRAGMENT}
query getTeamMembers(
  $organization: String!,
  $first: Int = 25,         # For team pagination (default handled by GraphQL client if not overridden)
  $after: String,           # For team pagination
  $memberFirst: Int = 50,   # For member pagination (matches exporter's default)
  $memberAfter: String      # For member pagination
) {{
  organization(login: $organization){{
    teams(first: $first, after: $after){{ # Team pagination
      nodes{{
        slug
        id
        name
        description
        privacy
        notificationSetting
        url

        members(first: $memberFirst, after: $memberAfter){{
          nodes{{
            login
            isSiteAdmin
          }}

          pageInfo{{
            ...PageInfoFields
          }}
        }}
      }}
      pageInfo{{
        ...PageInfoFields
      }}
  }}
}}
}}
"""

FETCH_TEAM_WITH_MEMBERS_GQL = f"""
{PAGE_INFO_FRAGMENT}
query getTeam(
    $organization: String!,
    $slug: String!,
    $memberFirst: Int = 25,
    $memberAfter: String
) {{
  organization(login: $organization) {{
    team(slug: $slug) {{
      slug
      id
      name
      description
      privacy
      notificationSetting
      url
      members(first: $memberFirst, after: $memberAfter) {{
        nodes {{
          login
          isSiteAdmin
        }}
        pageInfo {{
          ...PageInfoFields
        }}
      }}
    }}
  }}
}}
"""

LIST_EXTERNAL_IDENTITIES_GQL = f"""
    {PAGE_INFO_FRAGMENT}
    query ($organization: String!, $first: Int = 25, $after: String) {{
      organization(login: $organization) {{
        samlIdentityProvider {{
          ssoUrl
          externalIdentities(first: $first, after: $after) {{
            edges {{
              node {{
                guid
                samlIdentity {{
                  nameId
                  emails {{
                    primary
                    type
                    value
                  }}
                }}
                user {{
                  login
                }}
              }}
            }}
            pageInfo {{
            ...PageInfoFields
            }}
          }}
        }}
      }}
    }}
"""

REPOSITORY_FRAGMENT = """
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
  primaryLanguage { name }
  visibility
}
"""

COLLABORATORS_FIELD = """
collaborators(first: 25) {
  nodes {
    login
    name
    email
    url
  }
  pageInfo {
    ...PageInfoFields
  }
}
"""


def build_single_repository_gql(
    additional_fragments: str = "", additional_fields: str = ""
) -> str:
    """Build a GraphQL query for fetching a single repository with optional additional fields."""
    return f"""
{PAGE_INFO_FRAGMENT}
{REPOSITORY_FRAGMENT}
{additional_fragments}
query getRepository(
  $organization: String!,
  $repositoryName: String!,
) {{
  organization(login: $organization) {{
    repository(name: $repositoryName) {{
      ...RepositoryFields
      {additional_fields}
    }}
  }}
}}
"""


def build_list_repositories_gql(
    additional_fragments: str = "", additional_fields: str = ""
) -> str:
    return f"""
{PAGE_INFO_FRAGMENT}
{REPOSITORY_FRAGMENT}
{additional_fragments}
query listOrgRepositories(
  $organization: String!,
  $first: Int = 25,
  $after: String,
  $repositoryVisibility: RepositoryVisibility
) {{
  organization(login: $organization) {{
    repositories(first: $first, after: $after, visibility: $repositoryVisibility) {{
      nodes {{
        ...RepositoryFields
        {additional_fields}
      }}
      pageInfo {{
        ...PageInfoFields
      }}
    }}
  }}
}}
"""
