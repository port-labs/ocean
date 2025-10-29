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
          ... on User {{
                login
                email
                name
            }}
        }}
        pageInfo {{
        ...PageInfoFields
        }}
      }}
    }}
}}
"""

LIST_ORG_MEMBER_WITH_BOTS_GQL = f"""
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
            name
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
                name
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
            name
            email
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


TEAM_FIELDS_FRAGMENT = """
fragment TeamFields on Team {
  slug
  id
  name
  description
  privacy
  notificationSetting
  url
}
"""


TEAM_MEMBER_FRAGMENT = """
fragment TeamMemberFields on Team {
  members(first: $memberFirst, after: $memberAfter) {
    nodes {
      id
      login
      name
      isSiteAdmin
    }
    pageInfo {
      ...PageInfoFields
    }
  }
}
"""


FETCH_TEAM_WITH_MEMBERS_GQL = f"""
{PAGE_INFO_FRAGMENT}
{TEAM_FIELDS_FRAGMENT}
{TEAM_MEMBER_FRAGMENT}

query getTeam(
  $organization: String!,
  $slug: String!,
  $memberFirst: Int = 25,
  $memberAfter: String
) {{
  organization(login: $organization) {{
    team(slug: $slug) {{
      ...TeamFields
      ...TeamMemberFields
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


TEAM_REPOSITORY_FRAGMENT = """
fragment TeamRepositoryFields on Team {
  repositories(first: $repoFirst, after: $repoAfter) {
    nodes {
      ...RepositoryFields
    }
    pageInfo {
      ...PageInfoFields
    }
  }
}
"""

SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL = f"""
{PAGE_INFO_FRAGMENT}
{TEAM_FIELDS_FRAGMENT}
{TEAM_MEMBER_FRAGMENT}
{REPOSITORY_FRAGMENT}
{TEAM_REPOSITORY_FRAGMENT}

query getTeamWithMembersAndRepos(
  $organization: String!,
  $slug: String!,
  $memberFirst: Int = 50,
  $memberAfter: String,
  $repoFirst: Int = 25,
  $repoAfter: String
) {{
  organization(login: $organization) {{
    team(slug: $slug) {{
      ...TeamFields
      ...TeamMemberFields
      ...TeamRepositoryFields
    }}
  }}
}}
"""
