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
query getTeamMembers($organization: String!, $first: Int = 25, $after: String){{
	organization(login: $organization){{
    teams(first:$first, after: $after){{
      nodes{{
        slug
        id
        name
        description
        privacy
        notificationSetting
        url

        members{{
          nodes{{
            login
            isSiteAdmin
            email
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

FETCH_TEAM_WITH_MEMBERS_GQL = """
query getTeam($organization: String!, $slug: String!){
	organization(login: $org){
    team(slug:$slug){

        slug
        id
        name
        description
        privacy
        notificationSetting
        url

        members{
          nodes{
            login
            isSiteAdmin
            email
          }
        }
      }

  }
}
"""
