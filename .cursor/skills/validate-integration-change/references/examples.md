# Validation file examples

Made-up examples for an imaginary `acme` integration with `team` and `user` kinds. Copy
the shape, not the content.

## Layout

```text
integrations/acme/validation/
├── scenarios.yaml
├── models/
│   └── team.py
├── mock/
│   ├── routes/
│   │   ├── team.yaml
│   │   └── user.yaml
│   └── bodies/
│       └── team/
│           ├── page-1.json
│           └── page-2.json
└── expected/            # written by the runner when missing and resync completes (review before commit)
    └── happy_path/
        └── acmeTeam.json
```

## `models/team.py`

```python
from typing import ClassVar

from pydantic import BaseModel


class Team(BaseModel):
    id: str
    name: str
    description: str | None = None


class TeamListResponse(BaseModel):
    source: ClassVar[str] = "https://docs.acme.example/api/teams#list-teams"
    endpoint: ClassVar[str] = "GET /api/v2/teams"

    data: list[Team]
    next_cursor: str | None = None
```

## `mock/routes/team.yaml`

```yaml
routes:
  - id: list-teams-page-1
    verified: false
    request:
      method: GET
      path: /api/v2/teams
    response:
      status: 200
      body_file: bodies/team/page-1.json
      response_model: team.TeamListResponse

  # Listed after page 1: when several routes match, the last one wins.
  - id: list-teams-page-2
    verified: false
    request:
      method: GET
      path: /api/v2/teams
      query:
        cursor: page-2
    response:
      status: 200
      body_file: bodies/team/page-2.json
      response_model: team.TeamListResponse
```

`bodies/team/page-1.json`:

```json
{
  "data": [
    {"id": "team-1", "name": "Platform", "description": "Fake team for validation"}
  ],
  "next_cursor": "page-2"
}
```

## Rate limit route (`sequence`)

```yaml
routes:
  - id: list-teams-rate-limited
    verified: false
    request:
      method: GET
      path: /api/v2/teams
    sequence:
      - status: 429
        headers:
          Retry-After: "1"
        body: {"error": "rate_limited"}
      - status: 200
        body_file: bodies/team/page-1.json
        response_model: team.TeamListResponse
```

## Path parameters

```yaml
routes:
  - id: get-team
    verified: false
    request:
      method: GET
      path: /api/v2/teams/{team_id}
    response:
      status: 200
      body_file: bodies/team/{team_id}.json
      fallback_body: {"id": "unknown", "name": "Unknown"}
      response_model: team.Team
```

## `scenarios.yaml`

```yaml
defaults:
  port_app_config: .port/resources/port-app-config.yaml
  blueprints: .port/resources/blueprints.json
  integration_config:
    acmeHost: "{{mock_base_url}}"
    acmeApiKey: fake-api-key
  ignore_fields:
    - properties.lastSyncedAt

scenarios:
  happy_path:
    description: Every kind, one page each.
    routes:
      - routes/team.yaml
      - routes/user.yaml

  team_pagination:
    description: The client follows next_cursor until it is empty.
    kinds: [team]
    routes:
      - routes/team.yaml

  team_rate_limit:
    description: A 429 is retried and the resync still completes.
    kinds: [team]
    routes:
      - routes/team_rate_limit.yaml

  team_include_members:
    description: The includeMembers selector adds the members relation.
    kinds: [team]
    routes:
      - routes/team.yaml
      - routes/team_members.yaml
    port_app_config_overrides:
      - kind: team
        selector:
          includeMembers: true
```

Optional per scenario: `blueprints`, `integration_config` (merged over the defaults) and
`expect` (`unmatched_requests: allow` to tolerate calls the scenario doesn't mock).
