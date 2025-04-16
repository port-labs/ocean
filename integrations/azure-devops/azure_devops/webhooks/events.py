from enum import StrEnum


class PullRequestEvents(StrEnum):
    PULL_REQUEST_CREATED = "git.pullrequest.created"
    PULL_REQUEST_UPDATED = "git.pullrequest.updated"


class PushEvents(StrEnum):
    PUSH = "git.push"


if __name__ == "__main__":
    print(bool(PullRequestEvents("git.pullrequest.created")))
    print(bool(PushEvents("git.nothing")))
