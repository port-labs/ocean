# incident.io

Syncs incident.io into Port: incidents, alerts, the people involved, the teams that own them, and who is on call right now.

#### Install & use the integration - [Integration documentation](https://docs.port.io/context-lake/ingestion/ingest-data-into-port/native-integrations/available-integrations/incident-management/incident-io)

#### Develop & improve the integration - [Ocean integration development documentation](https://docs.port.io/context-lake/ingestion/ingest-data-into-port/custom-integration/custom-coded-ocean-integration/overview/)

## Prerequisites

An [incident.io API key](https://app.incident.io/settings/api-keys) that can read incidents, users, teams, and schedules:

| Kind | API | Scope |
|---|---|---|
| `incident` | `GET /v2/incidents` | View incidents (the list reference does not name a separate scope) |
| `user` | `GET /v2/users` | `users.view` |
| `team` | `GET /v3/teams` | `catalog_entries.view` |
| `schedule` | `GET /v2/schedules` | `schedules.view` |
| `alert` | `GET /v2/alerts` | `alerts.view` |

If a kind's permission is missing, that kind's resync fails and Port keeps the entities already ingested for it. The other kinds still sync.

## Configuration

| Field | Description |
|---|---|
| `incidentIoApiKey` | The API key, sent as `Authorization: Bearer <key>`. |
| `incidentIoApiUrl` | API origin. Default `https://api.incident.io`. |

## Selectors

| Kind | Selector | Default | Effect |
|---|---|---|---|
| `user` | `includeInactive` | `false` | Also sync deactivated and not-yet-active users. |
| `incident` | `daysBack` | `180` | Incidents created in the last N days. 180 is about 6 months. Allowed range is 1 to 3650. |
| `incident` | `statusCategories` | all | e.g. `["live", "learning"]`. Active in the dashboard is `live`. Post-incident is `learning`. |
| `incident` | `severities` | all | Severity names or ids, e.g. `["Critical", "Major"]`. Sent as `severity[one_of]` after names are resolved with `GET /v1/severities`. |
| `incident` | `includeTest` | `false` | Also sync test and tutorial incidents. Default is standard and retrospective, which is the API default. |
| `alert` | `daysBack` | `30` | Alerts created in the last N days. Allowed range is 1 to 3650. |
| `alert` | `statuses` | firing and resolved | e.g. `["firing"]`. |

## Notes

- Schedules answer who to page. `current_shifts` is who is on call now, and the schedule is requested at page size 25 so `next_shifts` is included when incident.io returns it. The on-call person changes as the rotation turns, so schedules are fully resynced rather than filtered by `updated_at`.
- Incidents also refresh on the incremental resync. The incident list filter only accepts a calendar date (`yyyy-mm-dd`), so an incremental run re-reads incidents updated on the cursor's UTC day, still inside `daysBack`. It does not delete incidents missing from that shorter window. Users, teams, and schedules refresh on the full resync.
- Alerts also refresh on the incremental resync. `updated_at` accepts a timestamp, so the run starts at the cursor and stays inside `daysBack`. `priority` comes from an alert attribute named Priority. A full resync deletes alerts created outside `daysBack`.
- Relations point at users and teams that were synced. Missing targets are not created as placeholder entities.
- List incidents is limited to 60 requests per minute. The other list endpoints share the account limit of 1200 requests per minute. The client stays under both, and Ocean retries 429 and 5xx.
- Live events are not implemented.
- Incident `status` is the org's status name, stored as a string so a renamed status still syncs. `statusCategory` is the stable API value (`triage`, `live`, `learning`, and the rest) and keeps a color per category.
- `postmortemUrl` is set only when the incident has `postmortem_document_url`.
