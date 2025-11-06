GET_ENTITY_TAGS_QUERY = """
{
  actor {
    entity(guid: "{{ entity_guid }}") {
      guid
      name
      entityType
      tags {
        key
        values
      }
    }
  }
}
"""
