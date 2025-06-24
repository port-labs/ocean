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
            email
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
          email
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
