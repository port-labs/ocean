from typing import TypedDict, List, Any, Dict


class Change(TypedDict):
    before: List[Dict[Any, Any]]
    after: List[Dict[Any, Any]]
