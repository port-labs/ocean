# Devin integration: handover for local verification

> Temporary file. Delete it before [ocean#4389](https://github.com/port-labs/ocean/pull/4389) merges.

You are a local agent. Your job is to run this integration against a **real Devin organization** and the **Port preview environment** built from [Port#21000](https://github.com/port-labs/Port/pull/21000), confirm or correct the assumptions below, fix what's broken, and report back. Everything here was written without access to a real Devin org, so every Devin API behavior below is an assumption until you verify it.

## 1. Goal and context

- Design: ADR 0041 and its `plan.md` in port-labs/port ([#20975](https://github.com/port-labs/Port/pull/20975), `docs/decisions/0041-devin-ocean-integration*`). Operator docs: [`CONTRIBUTING.md`](./CONTRIBUTING.md).
- Integration code: branch `cursor/devin-integration-610d` in port-labs/ocean, `integrations/devin`.
- Workflow builder nodes and AI-skill docs: branch `cursor/task_devin-workflow-nodes-610d` in port-labs/port.

**How tracking works (what you are verifying).** Devin has no webhooks. When `create_session` / `send_message` run with `reportCompletion: true`, the session gets these tags:

| Tag | Meaning |
|-----|---------|
| `port:managed` | Created by this integration (kept forever) |
| `port:pending:<OCEAN__INTEGRATION__IDENTIFIER>` | A run of this installation is waiting; the tracker lists sessions by this tag |
| `port:external-id:devin:<portRunId>` | The run's external ID (`find_run_by_external_id`) |
| `port:sent-at:<epochSeconds>` | Turn start; older messages/status don't count for this turn |

`SessionTracker.tick()` (`core/tracking/session_tracker.py`) runs every `sessionTrackingIntervalSeconds`: list sessions by the pending tag, then for each one post new messages to the run log as `[devin] ...` / `[user] ...`, classify `status` / `status_detail` (`core/tracking/turn_state.py`), and on a finished turn complete the run with `startedAt`, `endedAt`, `durationSeconds`, `status`, `statusDetail`, `pullRequests`, `structuredOutput`, `acusConsumed`, `lastMessage`, then strip every `port:` tag except `port:managed`. There is no local state, so a restart re-derives everything from tags.

**Deliberate deviations from the ADR plan** (keep them unless the real API forces a change):

- The external-ID tag is `port:external-id:devin:<runId>`. It doesn't include the session ID, so `create_session` can write every tag in the create call itself.
- For `running/waiting_for_user`, `running/finished` and `suspended/inactivity`, completion requires a **Devin message created after `sent-at`**, not `updated_at > sent-at`, because sending a message probably bumps `updated_at`. `exit` / `error` / other `suspended` details use `updated_at > sent-at`.
- If the run isn't found, the tracker waits 5 minutes after `sent-at` before releasing the tags (covers the gap between create and `update_run_started`).
- `terminate_session` fails any run still waiting on the session (otherwise `exit` would read as success).

## 2. Prerequisites (ask the human)

- A Devin org ID (`org-...`) and a service-user key (`cog_...`) with `ViewOrgSessions`, `ManageOrgSessions`, `ViewOrgMembership`, `ImpersonateOrgSessions`, and read access to playbooks, knowledge and secrets.
- At least one repository connected to that Devin org, and a few ACUs of budget.
- A user in the preview env's Port org, plus Port client ID / secret for that org (from the Credentials menu in the preview frontend).
- Python 3.12+ and Poetry (`integrations/_infra/Makefile` installs Poetry if it's missing).

Never commit the key, secrets or `.env`.

## 3. Bring up the preview env

1. On [Port#21000](https://github.com/port-labs/Port/pull/21000), check that the `preview` label is present and the "Create PR preview environment" workflow finished. A comment with "Preview Environment Ready" links the env. If it failed, re-run the workflow or remove and re-add the `preview` label.
2. URLs (env `pr-21000`):
   - Frontend: `https://frontend-pr-21000.cde-01.port.io`
   - API (`OCEAN__PORT__BASE_URL`): `https://api-pr-21000.cde-01.port.io`
   - Swagger: `https://port-api-pr-21000.cde-01.port.io/swagger/static/index.html`
3. Log in to the frontend, open a workflow, and click "Add node": an "Integration actions → Devin" category with Create / Send message / Terminate / Archive should be there. Pushing to the Port branch redeploys the env.

## 4. Run the integration locally

```bash
git clone https://github.com/port-labs/ocean && cd ocean
git checkout cursor/devin-integration-610d
cd integrations/devin
make install
cp .env.example .env
```

Set in `.env`:

```bash
OCEAN__PORT__BASE_URL=https://api-pr-21000.cde-01.port.io
OCEAN__PORT__CLIENT_ID=...
OCEAN__PORT__CLIENT_SECRET=...
OCEAN__INTEGRATION__IDENTIFIER=devin-local-<yourname>   # scopes the pending tag; must be unique
OCEAN__EVENT_LISTENER__TYPE=POLLING
OCEAN__INITIALIZE_PORT_RESOURCES=true
OCEAN__ACTIONS_PROCESSOR__ENABLED=true                  # required, or actions and the tracker never start
OCEAN__INTEGRATION__CONFIG__DEVIN_API_KEY=cog_...
OCEAN__INTEGRATION__CONFIG__DEVIN_ORG_ID=org-...
OCEAN__INTEGRATION__CONFIG__SESSION_TRACKING_INTERVAL_SECONDS=10
```

Run `make run` (or `python debug.py` under a debugger). Expect blueprints `devin_session` / `devin_playbook` / `devin_knowledge_note` / `devin_secret` to be created, a resync to finish, and a `SessionTracker started` log line.

## 5. P0 spike checklist (do this first)

Run these straight against Devin before driving anything through Port:

```bash
export DEVIN=https://api.devin.ai/v3/organizations/$DEVIN_ORG_ID
export AUTH="Authorization: Bearer $DEVIN_API_KEY"
```

Save one redacted raw response per endpoint under `tests/fixtures/` (e.g. `session.json`, `messages_page.json`, `sessions_by_tag.json`, `member_lookup.json`).

| # | Check | How | If wrong, change |
|---|-------|-----|------------------|
| S1 | Create accepts `port:` tags with `:` and `-` characters, about 60 characters long, and returns them unchanged | `curl -sX POST "$DEVIN/sessions" -H "$AUTH" -H 'content-type: application/json' -d '{"prompt":"Say hi and stop.","tags":["port:managed","port:pending:devin-local-x","port:external-id:devin:wfnr_abc123","port:sent-at:1760000000"]}'` | `core/tracking/tags.py` (encoding), `tests/test_tags.py` |
| S2 | `GET /sessions?tags=X` filters server-side, and repeated `tags=a&tags=b` is AND (or note OR). The client sends repeated keys. | `curl -s "$DEVIN/sessions?tags=port:pending:devin-local-x&first=10" -H "$AUTH"`, then with a second tag that only one session has | `core/sessions.py:list_by_tag`, `clients/devin_client.py`. If the filter is unusable, see Fallbacks. |
| S3 | Are `created_at` / `updated_at` in seconds or ms? (Both are handled; just record which.) Does `updated_at` change when a message is sent, and when a turn ends? | `GET $DEVIN/sessions/<id>` before and after `POST $DEVIN/sessions/<id>/messages -d '{"message":"..."}'` | `turn_state.py:turn_has_ended` |
| S4 | Real `status` / `status_detail` sequence for: new → working → waiting for user; a finished task; terminate (`DELETE $DEVIN/sessions/<id>`); idle suspend; out-of-ACU (`max_acu_limit: 1`) | Poll `GET $DEVIN/sessions/<id>` every 10s and log the pairs | `core/tracking/turn_state.py` and its matrix in `tests/test_turn_state.py` |
| S5 | Right after a follow-up message, does the session briefly keep the previous turn's status (e.g. still `waiting_for_user`)? | Poll fast (1s) right after `POST .../messages` | The guard should already cover this; if it doesn't, change `turn_state.py` |
| S6 | Messages: `source` values (`devin` / `user`?), `event_id` present, chronological order, the shape of `end_cursor` / `has_next_page`, and whether `end_cursor` is null when there's nothing after `after` | `curl -s "$DEVIN/sessions/<id>/messages?first=2" -H "$AUTH"`, then `&after=<end_cursor>` | `core/sessions.py:list_messages_after`, `clients/models.py`, `session_tracker.py:_post_new_messages` |
| S7 | Member lookup works for an org-scoped service user, and the response field is `user_id` | `curl -s "https://api.devin.ai/v3beta1/organizations/$DEVIN_ORG_ID/members/users?email=<you>&first=1" -H "$AUTH"` | `core/sessions.py:find_user_id_by_email`, `clients/endpoints.py` |
| S8 | `create_as_user_id` without `ImpersonateOrgSessions`: does create fail (403) or ignore it? The form defaults `createAsUserEmail` to the triggering user, so a 403 would break the default path. | Create with `create_as_user_id` using a key without that permission | If it 403s: in `actions/create_session_executor.py`, retry once without `create_as_user_id` and log a WARNING, then add a test |
| S9 | Tags API: `POST .../tags` appends, `PUT .../tags` replaces, both with body `{"tags": [...]}`, and the response contains `tags` | `curl -sX PUT "$DEVIN/sessions/<id>/tags" -H "$AUTH" -H 'content-type: application/json' -d '{"tags":["port:managed"]}'` | `core/sessions.py` |
| S10 | `DELETE /sessions/<id>?archive=true` and `POST /sessions/<id>/archive` return the session object | curl both | `core/sessions.py`, executors |

## 6. E2E scenarios (preview env)

Build a workflow in the preview frontend with a self-service trigger and a **Create Devin Session** node (installation `devin-local-<yourname>`, small prompt, a connected repo, `reportCompletion` on). For each scenario, record the run status, status labels, run logs and node output.

| # | Scenario | Expected |
|---|----------|----------|
| E1 | Create a session from a workflow | Node goes IN_PROGRESS. Logs: "Creating a Devin session", "Devin session started: <url>", then `[user] <prompt>`, `[devin] ...` as they arrive, status labels like "Devin working", then "Devin session ended at <iso> ...". Node SUCCESS with label "Awaiting input" or "Finished", and output containing `sessionId`, `url`, `startedAt`, `endedAt`, `durationSeconds`, `pullRequests`, `lastMessage`. The Devin session keeps only `port:managed` plus user tags. A `devin_session` entity exists with `managedByPort: true`. |
| E2 | Same through a self-service **action** (Ocean action run, not a workflow) | Same, except the action run has no persisted output. The completion message carries duration, status, PRs and ACUs. |
| E3 | Add a **Send Devin Message** node after E1 using `{{ .outputs.<createNode>.sessionId }}` | The second node completes on **its own** turn, not instantly from the previous `waiting_for_user`. Its logs contain only messages after its `startedAt`. |
| E4 | Send a message while Devin is still working | Run FAILURE with label "Session busy"; no message is sent. |
| E5 | Stop `make run` mid-turn, wait for Devin to finish, restart | The run completes after restart. Messages logged before the stop may be re-posted once (bounded by `sent-at`), but none are lost. |
| E6 | **Terminate Devin Session** while E1-style run is waiting | The waiting run fails with label "Terminated"; the terminate run succeeds; tracking tags are removed. |
| E7 | **Archive Devin Session** | Run succeeds; the entity shows `archived: true` after the next resync. |
| E8 | `maxAcuLimit: 1` on a task that needs more | Run FAILURE with "Usage limit" (or whatever S4 shows), and the tags are released. |
| E9 | Optional, since it is unit-tested by `test_expired_turn_times_out`: `SESSION_TRACKING_MAX_HOURS=1` (integer) with a task that keeps Devin working for over an hour | Run FAILURE with label "Timed out"; tags released. |
| E10 | Resync | Sessions (last 30 days, unarchived), playbooks, knowledge notes and secrets (metadata only) appear with sensible titles. `createdAt`/`updatedAt` are correct dates, so check the ms/s handling in `port-app-config.yml`. |
| E11 | Reserved tag in the node's Tags (`["port:x"]`) | Run FAILURE "Invalid inputs"; no session is created. |

## 7. Where to fix what

| Symptom | File |
|---------|------|
| Tags rejected or filter not matching | `core/tracking/tags.py`, `core/sessions.py:list_by_tag` |
| Run completes too early or never | `core/tracking/turn_state.py` (classification) and `session_tracker.py:_process` |
| Logs missing, duplicated or out of order | `session_tracker.py:_post_new_messages`, `core/sessions.py:list_messages_after` |
| Wrong start/end time or duration | `core/tracking/run_output.py`, `turn_state.to_epoch_seconds` |
| Request shape errors (4xx) | `actions/*_executor.py`, `clients/devin_client.py` |
| Catalog fields wrong | `.port/resources/blueprints.json`, `.port/resources/port-app-config.yml` |
| Node form issues | port repo, `apps/frontend/src/modules/application/workflows/components/graph/WorkflowBuilderGraph/forms/ai/*Devin*` |

Rules:

- Run `make lint` and `make test` in `integrations/devin` after every change, and add a regression test for every behavior fix. The in-memory fakes are in `tests/fakes.py`.
- For the Port repo, run `yarn workspace frontend lint`, `yarn workspace frontend test:component:agent <path>` and `yarn workspace frontend typecheck`.
- Commit to the existing branches with descriptive messages; no force pushes.
- Don't add config knobs or rework the tag-based design without flagging it in the report.

**Fallbacks.** If server-side tag filtering doesn't work (S2), first change the encoding in `tags.py`. If it still fails, change only the query step of `tick()` to scan `GET /sessions?updated_after=<now - window>` and filter by tag client-side; completion logic stays as is.

## 8. Reporting back

Fill in this table, commit it here, and paste it into both PR descriptions:

| Item | Result (confirmed / differs) | Finding | Fix commit |
|------|------------------------------|---------|------------|
| S1 | | | |
| S2 | | | |
| S3 | | | |
| S4 | | | |
| S5 | | | |
| S6 | | | |
| S7 | | | |
| S8 | | | |
| S9 | | | |
| S10 | | | |
| E1–E11 | pass / fail each | | |

Also commit the redacted fixtures under `tests/fixtures/`, and use them in at least one client and one tracker test.

## 9. Cleanup

- Terminate and archive every test Devin session.
- Delete the `devin-local-<yourname>` integration from the preview org.
- Delete this file before the Ocean PR merges.
- The preview env is torn down when Port#21000 closes (`destroy-pr-preview-environment.yml`).
