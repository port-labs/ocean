GET_ENTITY_BY_GUID_QUERY = """
{
  actor {
    entity(guid: "{{ entity_guid }}") {
      entityType
      guid
      domain
      name
      permalink
      reporting
      tags {
        key
        values
      }
      type
    }
  }
}
"""

LIST_ENTITIES_WITH_FILTER_QUERY = """
{
  actor {
    entitySearch(query: "{{ entity_query_filter }}") {
      results{{ next_cursor_request }} {
        entities {
          entityType
          type
          tags {
            key
            values
          }
          reporting
          name
          lastReportingChangeAt
          guid
          domain
          accountId
          alertSeverity
          permalink
        }
        nextCursor
      }
    }
  }
}
"""

# entities api doesn't support pagination
LIST_ENTITIES_BY_GUIDS_QUERY = """
{
    actor {
        entities(guids: {{ entity_guids }}) {
            entityType
            type
            tags {
                key
                values
            }
            reporting
            name
            lastReportingChangeAt
            guid
            domain
            accountId
            alertSeverity
            permalink
        }
    }
}
"""
