# Contributing to Ocean - devin

## Running locally

```bash
cd integrations/devin
make install
cp .env.example .env
# fill in OCEAN__PORT__CLIENT_ID, OCEAN__PORT__CLIENT_SECRET,
# OCEAN__INTEGRATION__CONFIG__DEVIN_API_KEY (a cog_ service-user key) and
# OCEAN__INTEGRATION__CONFIG__DEVIN_ORG_ID
make run
```

Actions (and therefore session tracking) only run when `OCEAN__ACTIONS_PROCESSOR__ENABLED=true` and the event listener runs actions (`POLLING` locally).

## Service-user permissions

Create an organization service user in Devin and grant it:

- `ViewOrgSessions` and `ManageOrgSessions` (resync, actions, tracking).
- `ImpersonateOrgSessions`, only when `createAsUserEmail` / `messageAsUserEmail` are used.
- `ViewOrgMembership`, to resolve those emails to Devin users (`/v3beta1/.../members/users`).
- Read access to playbooks, knowledge and secrets for their resyncs.

## Session tracking

`create_session` and `send_message` with `reportCompletion: true` leave the Port run `IN_PROGRESS`. The `SessionTracker` (started in `on_start`) completes it.

Tags written on the Devin session are the only tracking state:

| Tag | Meaning |
|-----|---------|
| `port:managed` | Session was created by this integration. Kept forever; drives `managedByPort` and the `onlyManagedByPort` selector. |
| `port:pending:<installationId>` | A Port run of this installation is waiting on the session. The tracker lists sessions by this tag. |
| `port:external-id:devin:<runId>` | The Port run's external ID, used to find the run (`find_run_by_external_id`). |
| `port:sent-at:<epochSeconds>` | When the turn started; earlier messages/status don't count for this turn. |

Tags starting with `port:` are reserved: actions reject them in user-provided tags. Every tag except `port:managed` is removed once the run is completed, timed out, or no longer exists.

Each tick (`sessionTrackingIntervalSeconds`, default 30):

1. Lists sessions tagged `port:pending:<installationId>`.
2. Posts new session messages to the run log as `[devin] ...` / `[user] ...`.
3. Classifies `status` / `status_detail` (`core/tracking/turn_state.py`). A finished turn completes the run with the session output (`startedAt`, `endedAt`, `durationSeconds`, PRs, ACUs, structured output, last Devin message). `waiting_for_user`, `finished` and `suspended/inactivity` need a Devin message after `sent-at`, so a status left over from the previous turn is ignored.
4. Fails runs waiting longer than `sessionTrackingMaxHours` (default 72) with status label `Timed out`.

## Gotchas

- `send_message` fails with `Session busy` when the session has a pending tag or Devin is still working. Runs are serialized per `sessionId`.
- `terminate_session` fails any run still waiting on the session itself; the tracker would otherwise read the `exit` status as a successful turn.
- A run that is not found right after its session was created is retried for 5 minutes (it may not have its external ID yet) before the tags are released.
- Devin's rate limits aren't exposed via headers. Backoff on `429`/`5xx` is handled by Ocean's retryable HTTP extension.
- Unverified against the live API (see `HANDOVER.md`): tag filter semantics for `port:` tags, timestamp units (seconds vs milliseconds are both handled), and how array query params are serialized (repeated keys).
