from enum import StrEnum

class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"

    @classmethod
    def available_kinds(cls) -> list[str]:
        return [kind.value for kind in cls]