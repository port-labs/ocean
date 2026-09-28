LIST_COMPANIES = """
query ListCompanies($first: Int, $after: String) {
  companies(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        domainName
        createdAt {
          iso8601
        }
        updatedAt {
          iso8601
        }
      }
    }
  }
}
""".strip()

LIST_TENANTS = """
query ListTenants($first: Int, $after: String) {
  tenants(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        externalId
        name
        url
        createdAt {
          iso8601
        }
        updatedAt {
          iso8601
        }
      }
    }
  }
}
""".strip()

LIST_USERS = """
query ListUsers($first: Int, $after: String) {
  users(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        fullName
        publicName
        email
        status
        role {
          id
          name
          key
        }
      }
    }
  }
}
""".strip()
