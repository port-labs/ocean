from typing import TypedDict, List


class Change(TypedDict):
    before: List[dict]
    after: List[dict]
