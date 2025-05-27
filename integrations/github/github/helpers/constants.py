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
