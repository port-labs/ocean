RELATED_ENTITIES_QUERY = """
{
  actor {
    entity(guid: {{ entity_guid }}) {
      guid
      name
      type
      relatedEntities({{ related_entities_args }}) {
        nextCursor
        results {
          type
          source {
            guid
          }
          target {
            guid
            entity {
              guid
              name
              type
            }
          }
        }
      }
    }
  }
}
"""
