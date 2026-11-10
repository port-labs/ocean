"""Support for the deprecated `file://` and `search://` mapping values, which are replaced by
the `includedFiles` and `searchQueries` selectors."""

import json
from dataclasses import dataclass, field
from typing import Any

FILE_REF_PREFIX = "file://"
SEARCH_REF_PREFIX = "search://"

INCLUDED_FILES_KEY = "__includedFiles"
SEARCH_RESULTS_KEY = "__search"


@dataclass
class MappingRefs:
    files: set[str] = field(default_factory=set)
    searches: set[str] = field(default_factory=set)

    def __bool__(self) -> bool:
        return bool(self.files or self.searches)


def _parse_ref(expression: str) -> tuple[str, str] | None:
    trimmed = expression.strip()
    if trimmed.startswith(FILE_REF_PREFIX):
        return INCLUDED_FILES_KEY, trimmed[len(FILE_REF_PREFIX) :].strip()
    if trimmed.startswith(SEARCH_REF_PREFIX):
        return SEARCH_RESULTS_KEY, trimmed[len(SEARCH_REF_PREFIX) :].strip()
    return None


def rewrite_mapping_ref(expression: str) -> str:
    """Turn a `file://P` / `search://Q` mapping value into the jq expression that reads
    the value the integration's raw enricher attached to the raw item."""
    parsed = _parse_ref(expression)
    if parsed is None:
        return expression
    container, key = parsed
    return f".{container}[{json.dumps(key)}]"


def rewrite_mapping_refs(value: Any) -> Any:
    if isinstance(value, str):
        return rewrite_mapping_ref(value)
    if isinstance(value, dict):
        return {key: rewrite_mapping_refs(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [rewrite_mapping_refs(inner) for inner in value]
    return value


def collect_mapping_refs(value: Any, refs: MappingRefs | None = None) -> MappingRefs:
    refs = refs if refs is not None else MappingRefs()
    if isinstance(value, str):
        parsed = _parse_ref(value)
        if parsed is not None:
            container, key = parsed
            (refs.files if container == INCLUDED_FILES_KEY else refs.searches).add(key)
    elif isinstance(value, dict):
        for inner in value.values():
            collect_mapping_refs(inner, refs)
    elif isinstance(value, list):
        for inner in value:
            collect_mapping_refs(inner, refs)
    return refs
