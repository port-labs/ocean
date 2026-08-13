import json
from typing import Any

from pydantic.v1 import BaseModel


def identifier_to_dict(identifier: Any) -> dict[str, Any] | None:
    if isinstance(identifier, BaseModel):
        identifier = identifier.dict()

    return identifier if isinstance(identifier, dict) else None


def normalize_identifier(identifier: Any) -> str:
    identifier_dict = identifier_to_dict(identifier)
    if identifier_dict is not None:
        return json.dumps(identifier_dict, sort_keys=True)

    return str(identifier)


def relation_target_identifier_keys(identifier: Any) -> set[str]:
    """Return local dependency keys that can be inferred from a relation target.

    Search queries can express predicates that Ocean cannot resolve locally, such
    as `contains` on custom properties. For sorting purposes we only infer an
    extra dependency key from exact `$identifier = <value>` rules. Plain relation
    values remain identifier-only, so duplicate identifiers across blueprints may
    still over-match when no blueprint is available in the relation target.
    """
    target_ids = {normalize_identifier(identifier)}
    search_query = identifier_to_dict(identifier)
    if search_query is None:
        return target_ids

    for rule in search_query.get("rules", []):
        rule_dict = identifier_to_dict(rule)
        if rule_dict is None:
            continue
        if rule_dict.get("rules"):
            target_ids.update(relation_target_identifier_keys(rule))
        if (
            rule_dict.get("property") == "$identifier"
            and rule_dict.get("operator") == "="
            and "value" in rule_dict
        ):
            target_ids.add(normalize_identifier(rule_dict["value"]))
    return target_ids
