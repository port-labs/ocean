GET_SLI_BY_NRQL_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      nrql(query: "{{ nrql_query }}") {
  results
      }
    }
  }
}
"""

LIST_SLOS_QUERY = """
{
  actor {
    entitySearch(query: "type ='SERVICE_LEVEL'") {
      count
      query
      results{{ next_cursor_request }} {
        entities {
          serviceLevel {
            indicators {
              resultQueries {
                indicator {
                  nrql
                }
              }
              id
              name
              description
              createdBy {
                email
              }
              guid
              updatedAt
              createdAt
              updatedBy {
                email
              }
              objectives {
                description
                target
                name
                timeWindow {
                  rolling {
                    count
                    unit
                  }
                }
              }
            }
          }
          tags {
            key
            values
          }
        }
        nextCursor
      }
    }
  }
}
"""
