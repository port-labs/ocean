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
          {{ extra_entity_properties }}
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
            {{ extra_entity_properties }}
        }
    }
}
"""

LIST_ENTITIES_RELATED_ENTITIES_BY_GUIDS_QUERY = """
{
  actor {
    entities(guids: {{ entity_guids }}) {
      guid
      relatedEntities(filter: {direction: OUTBOUND, relationshipTypes: {include: [CALLS]}}) {
        nextCursor
        results {
          type
          createdAt
          source {
            entity {
              guid
            }
          }
          target {
            accountId
            entity {
              guid
              name
              type
              domain
              entityType
              accountId
              reporting
              permalink
              tags {
                key
                values
              }
            }
          }
        }
      }
    }
  }
}
"""

LIST_ENTITY_RELATED_ENTITIES_QUERY = """
{
  actor {
    entity(guid: "{{ entity_guid }}") {
      guid
      relatedEntities(filter: {direction: OUTBOUND, relationshipTypes: {include: [CALLS]}} {{ next_cursor_request }}) {
        nextCursor
        results {
          type
          createdAt
          source {
            entity {
              guid
            }
          }
          target {
            accountId
            entity {
              guid
              name
              type
              domain
              entityType
              accountId
              reporting
              permalink
              tags {
                key
                values
              }
            }
          }
        }
      }
    }
  }
}
"""
