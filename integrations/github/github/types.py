import typing as t

# Note: The types here are not complete for the sake of simplicity.
# I only need the fields that i may use in the code.


class GithubUser(t.TypedDict):
    login: str
    id: int
    node_id: str
    avatar_url: str
    gravatar_id: str
    url: str
    html_url: str
    type: str
    site_admin: bool


class GithubRepo(t.TypedDict):
    id: int
    node_id: str
    name: str
    full_name: str
    private: bool
    owner: GithubUser
    html_url: str
    description: str | None
    fork: bool
    url: str
    created_at: str
    updated_at: str
    pushed_at: str
    default_branch: str
    stargazers_count: int
    size: int


class GithubBranch(t.TypedDict):
    label: str
    ref: str
    sha: str
    user: GithubUser
    repo: GithubRepo


class GithubPullRequest(t.TypedDict):
    url: str
    id: int
    node_id: str
    html_url: str
    number: int
    state: str
    locked: bool
    title: str
    user: GithubUser
    body: str | None
    created_at: str
    updated_at: str
    closed_at: str | None
    merged_at: str | None
    assignee: GithubUser | None
    assignees: list[GithubUser]
    requested_reviewers: list[GithubUser]
    requested_teams: list[dict[str, t.Any]]
    labels: list[dict[str, t.Any]]
    milestone: dict[str, t.Any] | None
    draft: bool
    head: GithubBranch
    base: GithubBranch
    merged: bool
    mergeable: bool
    mergeable_state: str


class GithubIssue(t.TypedDict):
    url: str
    repository_url: str
    labels_url: str
    comments_url: str
    events_url: str
    html_url: str
    id: int
    node_id: str
    number: int
    title: str
    user: GithubUser
    labels: list[dict[str, t.Any]]
    state: str
    locked: bool
    assignee: GithubUser | None
    assignees: list[GithubUser]
    milestone: dict[str, t.Any] | None
    comments: int
    created_at: str
    updated_at: str
    closed_at: str | None
    author_association: str
    active_lock_reason: str | None
    body: str | None
    closed_by: GithubUser | None
    timeline_url: str
    performed_via_github_app: dict[str, t.Any] | None
    state_reason: str | None


class GithubTeam(t.TypedDict):
    id: int
    node_id: str
    url: str
    html_url: str
    name: str
    slug: str
    description: str | None
    privacy: str
    notification_setting: str
    permission: str
    members_url: str


class GithubWorkflow(t.TypedDict):
    id: int
    node_id: str
    name: str
    path: str
    state: str
    created_at: str
    updated_at: str
    url: str
    html_url: str
    badge_url: str
