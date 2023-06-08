import jq

def resources_to_port_entity(resource_object, mapping):
    def run_jq_query(jq_query):
        return jq.first(jq_query, resource_object)

    def raise_missing_exception(missing_field, mapping):
        raise Exception(
            f"Missing required field value for entity, field: {missing_field}, mapping: {mapping.get(missing_field)}")

    def remove_nulls_from_dict(d):
        return {k: v for k, v in d.items() if v is not None}

    if mapping["selector"]["query"] and not run_jq_query(mapping["selector"]["query"]):
        return []

    mapping = mapping["port"]["entity"]["mappings"]

    return remove_nulls_from_dict({
        "identifier": run_jq_query(mapping.get('identifier', 'null')) or raise_missing_exception('identifier', mapping),
        "title": run_jq_query(mapping.get('title', 'null')) if mapping.get('title') else None,
        "blueprint": mapping.get('blueprint', '').strip('\"') or raise_missing_exception('blueprint', mapping),
        "icon": run_jq_query(mapping.get('icon', 'null')) if mapping.get('icon') else None,
        "team": run_jq_query(mapping.get('team', 'null')) if mapping.get('team') else None,
        "properties": {prop_key: run_jq_query(prop_val) for prop_key, prop_val in
                       mapping.get('properties', {}).items()},
        "relations": {rel_key: run_jq_query(rel_val) for rel_key, rel_val in
                      mapping.get('relations', {}).items()} or None
    })
