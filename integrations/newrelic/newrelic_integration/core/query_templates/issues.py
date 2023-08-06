LIST_ISSUES_BY_ENTITY_GUIDS_MINIMAL_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiIssues {
        issues(filter: {entityGuids: "{{ entity_guid }}"}{{ next_cursor_request }}) {
          issues {
            entityGuids
            issueId
            state
            closedAt
          }
          nextCursor
        }
      }
    }
  }
}
"""


# TODO: filter by state once the API supports it
# https://forum.newrelic.com/s/hubtopic/aAX8W00000005U2WAI/nerdgraph-api-issues-query-state-filter-does-not-seem-to-be-working
LIST_ISSUES_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiIssues {
        issues{{ next_cursor_request }} {
          issues {
            issueId
            priority
            state
            title
            conditionName
            description
            entityGuids
            policyName
            createdAt
            origins
            policyIds
            sources
            activatedAt
          }
          nextCursor
        }
      }
    }
  }
}
"""
