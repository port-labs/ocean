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

_CUSTOMER_FIELDS = """
id
externalId
fullName
shortName
email {
  email
}
company {
  id
}
tenantMemberships(first: 100) {
  edges {
    node {
      tenant {
        id
      }
    }
  }
}
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()

_THREAD_FIELDS = """
id
ref
externalId
title
description
status
priority
customer {
  id
}
tenant {
  id
}
assignedTo {
  __typename
  ... on User {
    id
  }
  ... on MachineUser {
    id
  }
  ... on System {
    id
  }
}
labels {
  id
  labelType {
    id
    name
  }
}
threadFields {
  id
  key
  type
  stringValue
  booleanValue
  numberValue
}
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()


def _indent(selection: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in selection.splitlines())


LIST_CUSTOMERS = f"""
query ListCustomers($first: Int, $after: String) {{
  customers(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_CUSTOMER_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_CUSTOMER = f"""
query GetCustomer($customerId: ID!) {{
  customer(customerId: $customerId) {{
{_indent(_CUSTOMER_FIELDS, 4)}
  }}
}}
""".strip()

LIST_THREADS = f"""
query ListThreads($first: Int, $after: String, $filters: ThreadsFilter) {{
  threads(first: $first, after: $after, filters: $filters) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_THREAD_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_THREAD = f"""
query GetThread($threadId: ID!) {{
  thread(threadId: $threadId) {{
{_indent(_THREAD_FIELDS, 4)}
  }}
}}
""".strip()
