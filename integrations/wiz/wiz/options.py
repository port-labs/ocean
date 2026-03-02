from typing import List, Literal, TypedDict, Required, NotRequired, Optional


class IssueOptions(TypedDict):
    max_pages: Required[int]
    status_list: Required[List[Literal["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]]]
    severity_list: NotRequired[
        Optional[List[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INFORMATIONAL"]]]
    ]
    type_list: NotRequired[
        Optional[
            List[
                Literal["TOXIC_COMBINATION", "THREAT_DETECTION", "CLOUD_CONFIGURATION"]
            ]
        ]
    ]


class ProjectOptions(TypedDict):
    include_archived: NotRequired[Optional[bool]]
    impact: NotRequired[Optional[Literal["LBI", "MBI", "HBI"]]]
