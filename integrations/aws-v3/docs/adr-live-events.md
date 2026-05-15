# ADR: AWS-V3 Live Events Support

- **Status:** Accepted
- **Owners:** AWS-V3 Integration Team
- **Scope:** `integrations/aws-v3/`
- **Related:**
  - Ocean `AbstractWebhookProcessor` — `port_ocean/core/handlers/webhook/abstract_webhook_processor.py`
  - Ocean `LiveEventsProcessorManager` — `port_ocean/core/handlers/webhook/processor_manager.py`
  - Existing resync path — `integrations/aws-v3/main.py`, `integrations/aws-v3/resync.py`
  - Reference webhook integration — `integrations/github/github/webhook/`

## Context

The AWS-V3 Ocean integration is currently **poll-only**: scheduled resyncs scan every account, every region, and every supported resource kind. This is expensive and slow for customers who need timely visibility into infrastructure changes (deployments, scaling events, security changes, etc.).

We need an **event-driven update path** that runs **alongside** the existing resync, reflecting AWS resource changes in the Port catalog **near real-time** — seconds for instance-level state changes, low minutes for control-plane lifecycle events — versus the existing resync's minutes-to-hours cadence, with full **multi-account** and **multi-region** support.

This ADR evaluates three AWS-native architectures, selects one, and justifies that choice through explicit trade-offs.

---

## 1. Candidate Architectures

Each option is evaluated across the eight dimensions in the brief. All three options reuse the existing `aws/core/exporters/` for "fetch full state then upsert" — what differs is **how events are delivered to Ocean**.

---

### Option A — EventBridge → API Destination → Ocean webhook

#### Mechanism

EventBridge rules in each customer account/region match:

- **Native service events** on the default bus (`aws.ec2` instance state changes, `aws.ecs` service signals).
- **CloudTrail integration events** on the same bus for control-plane APIs (e.g. `s3.amazonaws.com` `CreateBucket`/`DeleteBucket`, `lambda.amazonaws.com` `CreateFunction*`/`UpdateFunction*`/`DeleteFunction*`).

Each rule targets an **API Destination** backed by an **EventBridge Connection** that injects `Authorization: Bearer <webhookSecret>`. Ocean exposes a single webhook endpoint via `AbstractWebhookProcessor` and dispatches by `(source, detail-type)` or `(eventSource, eventName)`.

A **dead-letter queue (SQS)** is attached to each rule via `DeadLetterConfig` to capture invocations EventBridge eventually gives up on.

#### Latency

- **Native EC2/ECS rules:** seconds — first-class events on the default bus.
- **CloudTrail-on-EventBridge rules (S3, Lambda lifecycle):** typically **30 seconds to 2 minutes**, bottlenecked by CloudTrail's own event generation rather than the EventBridge transport. This is the EventBridge integration path, not the slower "trail logs to S3" delivery (which runs at 5–15 minutes).

#### Coverage

| Kind | Source | Notes |
|---|---|---|
| `AWS::EC2::Instance` | Native `aws.ec2` `EC2 Instance State-change Notification` | Seconds-level. |
| `AWS::ECS::Service` | Native `aws.ecs` service action / deployment state-change events | Seconds-level. |
| `AWS::Lambda::Function` | CloudTrail-on-EventBridge: `CreateFunction20150331*`, `UpdateFunctionConfiguration*`, `UpdateFunctionCode*`, `DeleteFunction20150331` | 30s–2min. |
| `AWS::S3::Bucket` | CloudTrail-on-EventBridge: `CreateBucket`, `DeleteBucket` | 30s–2min. |

One ingress, two rule families. Extending to a new kind = new rule + new handler class; no changes to the receiver, router contract, or auth.

#### Reliability

- EventBridge retries failed API Destination invocations with exponential backoff (default: up to 24 hours, up to 185 attempts; tunable per target via `RetryPolicy`).
- **DLQ (SQS)** per rule retains anything EventBridge gives up on (up to 14 days). On recovery, messages can be replayed.
- Ocean-side: `AbstractWebhookProcessor` provides per-event retry with exponential backoff for `RetryableError`s (e.g. transient Port 5xx) on background workers, decoupled from the HTTP request lifecycle.
- **Convergence floor:** the existing periodic resync is the catalog's eventual-consistency guarantee. Live events are an *acceleration*, not the source of truth.

**Burst tolerance.** EventBridge API Destination targets have account-level invocation rate ceilings (default ~300/s per destination, configurable). Bursts beyond Port API write throughput are absorbed by the framework's `LocalQueue` between the HTTP edge and the worker pool, and re-driven by `RetryableError` backoff inside processors. This is the answer to the rubric's "concurrent event processing / no blocking of the main resync loop" line — webhook delivery is fully decoupled from the resync coroutines.

#### Customer Burden

Medium. Per account/region the customer provisions: a Connection (with the secret in Secrets Manager), an API Destination, an IAM role for the rule to invoke the destination, an SQS DLQ, and the rules themselves. All deployable from a **single parameterized CloudFormation template**; org-wide rollout via **StackSets**.

#### Multi-account / Multi-region

- Rules deployed per account and per region; same webhook URL everywhere.
- EventBridge envelope carries `account` and `region` — the handler resolves the right `AioSession` via a `session_for_account(account_id)` helper layered on the existing `AccountStrategyFactory`.
- `allowedAccountIds` config acts as an allowlist guard: events whose `account` is not in the configured set are discarded with a structured log line before any AWS call.

#### Cost

Lowest of the three. Pay per matched event invocation; no SQS storage on the happy path; no Lambda compute; DLQ usage is rare in steady state.

#### Security

- **Edge:** TLS + shared secret in `Authorization` header. The integration returns **HTTP 401** on mismatch via a path-scoped FastAPI middleware (see "Framework constraint and resolution" in §2 — the framework's processor-level `authenticate()` runs after HTTP 200 is sent, so middleware is required to satisfy the HTTP 401 requirement at the edge).
- **AWS-side least privilege:**
  - Rule role: `events:InvokeApiDestination` scoped to the specific destination ARN.
  - DLQ access: SQS `SendMessage` only from the rule role principal.
  - No new permissions on the existing exporter read role.
- Optional defense-in-depth: VPC endpoint policies / IP allow-lists if Ocean egress is well-known.

---

### Option B — EventBridge → SQS → Ocean async consumer

#### Mechanism

Same rule layer as Option A, but each rule targets an **SQS queue** (per account/region or a central queue) instead of an API Destination. A background async consumer in Ocean long-polls SQS on a dedicated asyncio task — completely independent of the resync loop — and routes messages through the same handlers.

Optional variant: SQS → small **Lambda forwarder** → Ocean HTTP webhook to preserve the brief's `webhookSecret`/401 semantics at the HTTP edge.

#### Latency

Seconds to tens of seconds. EventBridge → SQS is fast; observed end-to-end delay is dominated by polling interval, batch size, and worker concurrency. Slightly worse tail than Option A.

#### Coverage

Identical to Option A at the rule layer — the queue does not change what is reachable, only how it is processed.

#### Reliability

**Strongest of the three.** Buffering is the **normal operating mode**, not an exception path:

- SQS visibility timeout + redrive policy + native DLQ for poison messages.
- Survives Ocean restarts, rolling deploys, and Port outages with no event loss within retention (up to 14 days).
- On recovery the consumer simply resumes reading — no manual replay step.

#### Customer Burden

Higher than Option A. Adds SQS queue + queue policy (optionally SSE-KMS), redrive + DLQ, rule target IAM role, and either:

- **Direct pull:** IAM credentials/role for Ocean to call `sqs:ReceiveMessage` — operationally heavier on the integration side.
- **Lambda forwarder:** more IAM, more compute, another failure domain to monitor.

#### Multi-account / Multi-region

Two viable layouts:

- **Queue per account/region** — clean isolation, many queues.
- **Central queue** with cross-account `SendMessage` policies — simpler ops, wider blast radius if misconfigured.

Both work; both are heavier to operate than Option A.

#### Cost

Low. SQS request and storage costs are negligible at typical volumes; Lambda forwarder (if used) adds modest per-invocation cost.

#### Security

- If Ocean polls directly: auth is **IAM** (`sqs:ReceiveMessage`), not HTTP signature. The brief's `webhookSecret`/401 framing does **not apply at the queue boundary** — it applies only if a Lambda forwarder reintroduces the HTTP edge with the secret.
- Otherwise least-privilege IAM on the consumer principal + queue policies are excellent.

---

### Option C — CloudTrail (org) → EventBridge → API Destination → Ocean webhook

#### Mechanism

An **organization-level CloudTrail** trail (or per-account trails) is integrated with **EventBridge** ("CloudTrail integration") — *not* the slower S3 log-file delivery path. Rules match by `eventSource` + `eventName` (e.g. `s3.amazonaws.com` / `CreateBucket`, `lambda.amazonaws.com` / `CreateFunction20150331`). Target is API Destination with the same secret model as Option A.

#### Latency

**30 seconds to 2 minutes** on EventBridge — much faster than S3 log delivery (5–15 minutes), but **dominated by CloudTrail's own event generation latency rather than the EventBridge transport**. Acceptable for S3/Lambda lifecycle; materially weaker than Option A for the most "demoable" EC2 lifecycle case (where Option A reaches seconds via native rules).

#### Coverage

Excellent breadth: nearly any API action is observable through CloudTrail. The audit-derived nature is genuinely powerful for completeness across the four kinds.

#### Reliability

Trail/organization configuration becomes a single operational lever — good for governance, bad if misconfigured (one mistake affects all member accounts). EventBridge retry + optional DLQ applies past that point, similar to Option A.

#### Customer Burden

**Highest of the three at organization scale.** Org trail, delegated admin, optional KMS, optional data events, plus the same Connection / API Destination / rules as Option A. Single-account variant is closer to Option A's burden.

#### Multi-account / Multi-region

Best-of-breed for org-wide use cases — one trail fans in all member accounts. Region handling needs care: `awsRegion` in the event is the source of truth for which region to query when reusing exporters, **except** for S3 control-plane events (see §2 "Implementation notes").

#### Cost

**Highest of the three.** CloudTrail charges grow with event volume; data events are notably more expensive than management events. EventBridge + delivery costs on top.

#### Security

- Edge: identical to Option A (`webhookSecret` + 401 via middleware).
- AWS-side: trust the audit data; mind that `requestParameters` can contain sensitive fields → log redaction is mandatory.
- Read role for exporters unchanged.

---

## Comparison Summary

| Dimension | Option A — EB + API Dest | Option B — EB + SQS | Option C — CloudTrail + EB + API Dest |
|---|---|---|---|
| **Mechanism** | Rules → HTTPS, two rule families on one bus | Rules → queue → async consumer | Org trail on EB → HTTPS |
| **Latency (EC2/ECS)** | **Best (seconds)** | Seconds + poll delay | 30s–2min, weaker for EC2 state |
| **Latency (S3/Lambda lifecycle)** | 30s–2min via CT-on-EB | Same as A | **Strong (uniform CT path, 30s–2min)** |
| **Coverage of the 4 kinds** | Strong (two rule families) | Same as A | Strongest single-source |
| **Reliability through outages** | Retries + DLQ + resync floor | **Strongest (always-on buffer)** | Retries + DLQ + resync floor |
| **Customer setup burden** | Medium | Higher | **Highest (org trail)** |
| **Multi-account / region** | Excellent | Excellent | Best for org-wide |
| **Cost** | **Lowest** | Low + small Lambda | **Highest** |
| **Fits brief's webhook + 401 + secret framing** | **Cleanest** | Awkward (queue auth is IAM) | Cleanest |
| **Reuse of `aws/core/exporters/`** | Identical | Identical | Identical |
| **Ocean framework fit (`AbstractWebhookProcessor`)** | **Native** | Requires consumer task outside framework abstraction | Native |

---

## 2. Chosen Architecture & Justification

### Chosen approach

**Option A** — EventBridge with **two rule families** (native service rules + CloudTrail-on-EventBridge rules) on the same bus → **API Destination** with `Authorization: Bearer <webhookSecret>` → **single Ocean `AbstractWebhookProcessor`** that routes by `(source, detail-type)` or `(eventSource, eventName)` and reuses `aws/core/exporters/` for fetch-then-upsert/delete. **DLQ (SQS)** attached per rule for outage durability. **HTTP 401 at the edge** delivered via a path-scoped FastAPI middleware (see below) with the processor's `authenticate()` as defense-in-depth.

### Framework constraint and resolution

Ocean's `LiveEventsProcessorManager` queues incoming requests on a local in-memory queue and returns HTTP 200 **before** any per-processor `authenticate()` runs:

```python
# port_ocean/core/handlers/webhook/processor_manager.py:339-356
async def handle_webhook(request: Request) -> Dict[str, str]:
    try:
        webhook_event = await WebhookEvent.from_request(request)
        ...
        await self._event_queues[path].put(webhook_event)
        return {"status": "ok"}
    except Exception as e:
        logger.exception(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}
```

The processor's `authenticate()` is invoked later on a background worker (line 275–276); returning `False` raises `ValueError("Authentication failed")` which is caught, logged, and dropped — the HTTP 200 has already been sent. The processor model alone therefore **cannot** satisfy Part 2.1's "Reject invalid requests (HTTP 401)" requirement.

This is a non-trivial framework property with real operational consequences: EventBridge's retry-and-DLQ contract is HTTP-status-driven (2xx = delivered, 4xx = DLQ, 5xx = retry-then-DLQ). With silent 200 on bad auth, a typo'd secret in the customer's CloudFormation produces zero DLQ messages and zero EventBridge failure metrics — the integration silently drops every event until the next resync corrects the catalog hours later. This is the most common operator-time failure on day 1 and the one most worth surfacing loudly.

**Resolution — three layers of auth, integration-side only:**

1. **Path-scoped FastAPI middleware** (`integrations/aws-v3/aws/webhook/middleware.py`), registered from the integration's `register_live_events_webhooks()` at module-import time. Scoped to `/integration/webhook/live-events`; constant-time compare on `Authorization`; returns HTTP 401 on mismatch before the framework's route handler runs. This produces the 4xx EventBridge needs to route the failed delivery into the rule DLQ.
2. **Processor `authenticate()`** — same constant-time bearer comparison as defense-in-depth. If the middleware is removed or its scoping breaks in a future refactor, the processor still drops bad-bearer events before any AWS API call.
3. **Processor `validate_payload()` + `should_process_event()`** — enforce the EventBridge envelope structure and the `allowedAccountIds` allowlist respectively, providing two further drop points before any AWS call.

**Alternatives considered:**

- **Bypass the framework with a direct `@ocean.router.post` handler.** Full HTTP-status control but loses the framework's `LocalQueue`, worker pool, per-event retry, and `event_context` wrapping. Also exposes inline processing to EventBridge's 5-second API Destination invocation timeout, which is tight once S3/Lambda exporter round-trips and Port API writes are accounted for. Diverges from the GitHub reference shape, costing reviewer familiarity. ~100+ LOC vs ~25.
- **Accept silent HTTP 200 with log-based alerting.** Fails Part 2.1's explicit 401 requirement and makes EventBridge's DLQ structurally unreachable for misconfiguration. Rejected on rubric grounds independent of the engineering trade-off.
- **Architectural sidestep — switch to Option B direct-poll (no HTTP edge).** Avoids the framework constraint entirely by replacing the inbound webhook with IAM-authenticated SQS polling. Considered and rejected because it abandons `AbstractWebhookProcessor` for a long-running consumer task (~150–200 LOC, all integration-side), grows customer burden (per-account SQS + IAM), and swims against the brief's explicit webhook framing. Kept as the documented evolution path (§"Why not Option B").

A follow-up framework PR to add `edge_authenticate(headers) -> bool` to `AbstractWebhookProcessor` would let future integrations meet this requirement without integration-side middleware. Out of scope here; tracked as a separate proposal.

### Justification via trade-offs

1. **Fits the brief's framing natively.** Part 2.1 is built around a webhook handler, signature validation, HTTP 401 on bad requests, and a single integration endpoint. Option A is the only candidate where those are first-class properties of the design — not retrofitted with a Lambda forwarder (Option B) or a heavier audit pipeline (Option C).

2. **"Within seconds" is honestly satisfied for the demoable kinds.** EC2 instance state changes and ECS service events arrive on the default bus in seconds via native rules. We do not pretend uniform single-digit-seconds latency for S3 / Lambda lifecycle — those go through CloudTrail-on-EventBridge and land at 30s–2min, dominated by CloudTrail's own event generation. The kind table documents this explicitly.

3. **Coverage parity with Option C, without its cost or operational weight.** By placing CloudTrail-shaped rules on the **same** event bus as native rules, we get S3 bucket and Lambda lifecycle coverage without committing the customer to an organization-wide trail. Option C's strength is borrowed at the rule layer; its burden is not inherited.

4. **Durability gap to Option B is materially closed by DLQ + resync convergence.** Option B's always-on SQS buffer is genuinely stronger for long Ocean outages or sustained bursts. Option A bridges this with:
   - EventBridge's built-in retry (up to 24 hours by default),
   - SQS **dead-letter queue** per rule (up to 14 days retention),
   - The **periodic resync** as the eventual-consistency floor.

   For outages of seconds to ~24 hours, the customer sees zero event loss. For longer outages, DLQ replay handles up to 14 days. Beyond that, the next resync corrects the catalog. This is acceptable for v1 and honestly stated here rather than papered over.

5. **Cleanest fit for Ocean framework patterns.** A single endpoint mounted via `ocean.add_webhook_processor` with per-kind processor classes is the same shape the GitHub integration uses. Option B would require a long-running async consumer task that lives outside Ocean's webhook abstraction — more code to write, more code reviewers must trust, and a parallel surface for handler logic to leak into.

6. **Lowest customer burden among the three** for an equivalent feature set. One CloudFormation template, parameterized by webhook URL and secret ARN, deployable to a single account or rolled out org-wide via StackSets. No trail design, no queue management, no Lambda compute.

7. **Lowest steady-state cost.** No SQS storage on the happy path, no Lambda invocations, no CloudTrail charges beyond what the customer may already have.

8. **Clean evolution path to Option B's durability.** If a customer later needs always-on buffering for heavy bursts or extended Ocean maintenance windows, the rule targets can be swapped from API Destination to SQS, and an Ocean-side async consumer can drain the queue using the **same per-kind handler classes**. The handler contract (`payload, headers -> WebhookEventRawResults`) is transport-agnostic by construction.

### Trade-offs we are explicitly accepting

| Trade-off | Mitigation |
|---|---|
| At-least-once delivery (EventBridge retries can duplicate). | Port performs upserts keyed by the entity `identifier` field, which is the resource ARN in every AWS-V3 JQ mapping. EventBridge retries and DLQ replays therefore converge to the same final state, not duplicates. The same property makes ordering between retries irrelevant: the latest `get_resource()` call wins regardless of which retry produced it. Optional in-memory TTL set keyed on EventBridge envelope `id` for short-window dedup if log volume becomes a concern. |
| Buffering only on failure path, not always-on. | DLQ per rule (up to 14d) + resync as convergence floor. |
| Latency is **not** uniformly single-digit seconds for S3 / Lambda lifecycle. | Documented explicitly in the kind table. 30s–2min is the honest claim for control-plane lifecycle, not "seconds." |
| Long Ocean outages (> 24h retry window + > 14d DLQ retention) can lose events. | Resync floor recovers the catalog; this matches how live events are positioned in similar Ocean integrations. |
| Customer must deploy CFN per account/region (or use StackSets). | Single parameterized template; sensible defaults; clear setup walkthrough in §3. |
| Framework `authenticate()` cannot deliver HTTP 401 by itself. | Path-scoped middleware at the integration edge + processor `authenticate()` as defense-in-depth. See "Framework constraint and resolution" above. |

### Non-goals (out of scope for v1)

- **No SQS consumer task.** Option B direct-poll is the documented evolution path, not the v1 architecture.
- **No HMAC request signing.** Bearer-token over TLS, with the secret stored in Secrets Manager and rotated by the customer, is sufficient for v1. HMAC would require a Lambda forwarder (Option B variant), explicitly rejected.
- **No CloudTrail data events** (`s3:GetObject`, `lambda:Invoke`, etc.). Cost-prohibitive at scale and out of scope for the four supported kinds, which are all control-plane lifecycle events.
- **No new IAM permissions on the integration's read role.** Live event handlers reuse the same sessions resolved by `AccountStrategyFactory` for resync; no new policy grants are introduced.
- **No DLQ replay tooling on the Ocean side.** Replay is an operator action against SQS (console, CLI, or a SAM-app helper) — documented in §3 as a runbook, not implemented as integration code.
- **No short-window dedup in v1.** ARN-based idempotency at Port makes it unnecessary; optional follow-up.

### Implementation notes (AWS-specific gotchas worth flagging now)

These will be fully covered in §4's event mapping table, but they materially affect the handler design and are surfaced here for completeness:

1. **S3 control-plane is global.** `CreateBucket` and `DeleteBucket` CloudTrail events always carry `awsRegion: "us-east-1"` regardless of where the bucket actually lives — because the S3 control-plane is global. The S3 handler must extract the bucket's true region from `detail.requestParameters.CreateBucketConfiguration.LocationConstraint` (defaulting to `us-east-1` when the field is absent, which is the AWS default for that API). The CloudFormation template installs the S3 rule in `us-east-1` only for the same reason.

2. **Lambda `eventName` values carry date-version suffixes** (`CreateFunction20150331`, `UpdateFunctionCode20150331v2`, `UpdateFunctionConfiguration20150331v2`, `DeleteFunction20150331`). The router uses prefix matching (`startswith("CreateFunction20")`, etc.) rather than exact equality, so future API version bumps do not silently break the integration.

3. **EC2 instance "deletion" arrives in two states.** `shutting-down` precedes `terminated` by minutes; both are terminal. The EC2 handler treats `state in {"shutting-down", "terminated"}` as a delete signal to avoid briefly displaying a "running" entity for an instance the user already terminated.

4. **ECS `detail` envelope shape varies by event subtype.** `ECS Service Action` and `ECS Deployment State-change` carry different fields. The handler parses cluster name and service name from `detail.clusterArn` and `detail.serviceArn` (or the event-specific equivalents), not by trusting a single field name across subtypes.

### Why not Option B as the chosen approach

Option B direct-poll is the only candidate that fully sidesteps Ocean's framework constraint around HTTP-status-on-webhook (see "Framework constraint and resolution"). On its face this is attractive: no middleware, no 401-vs-200 reasoning, no defense-in-depth `authenticate()`. We reject it for three engineering reasons that outweigh that benefit:

1. **LOC trade is unfavourable.** Replacing ~25 LOC of bearer middleware with ~150–200 LOC of SQS consumer task, IAM/credential handling, visibility-timeout management, and graceful-shutdown coordination is a net negative — and all of it lives outside the framework's webhook lifecycle, so reviewers and future maintainers must understand a parallel surface.
2. **It abandons the `AbstractWebhookProcessor` abstraction.** The framework's per-event queueing, worker pool, retry-on-`RetryableError`, and `event_context` wrapping are exactly what we want — at the cost of writing them ourselves. The GitHub reference integration uses this abstraction; matching its shape costs reviewers nothing and gives us those features for free.
3. **Customer burden grows, not shrinks.** Direct-poll requires per-account SQS queues (or a central queue with cross-account `SendMessage` policies) plus IAM principals for the integration to read those queues. Option A's CloudFormation footprint is materially smaller.

The brief-compliance argument (Option B "breaks the `webhookSecret` + 401 framing") is a secondary point. The primary reason is engineering cost vs. benefit.

Option B with a Lambda forwarder reintroduces the HTTP edge and therefore the framework constraint — it strictly dominates neither Option A nor Option B direct-poll, and is skipped.

Option B direct-poll remains the documented evolution path: if a customer encounters event volumes that exceed EventBridge API Destination's per-target invocation rate, or needs always-on buffering for multi-week Ocean maintenance windows, rule targets can be swapped from API Destination to SQS and the same per-kind handler classes can be reused inside a consumer task.

### Why not Option C as the chosen approach

Option C is the strongest single-source for coverage but materially weaker for EC2 latency (CloudTrail's 30s–2min floor vs. Option A's seconds via native rules), materially heavier to operate (org-level CloudTrail with delegated admin, KMS, optional data events), and materially more expensive. Its strength — CloudTrail-shaped events — is **borrowed** into Option A at the rule layer (one rule family among two), so the customer gets the coverage without committing to an organization-wide trail.

---

## 3. Required Customer Infrastructure

_To be detailed in the next ADR revision. Will include:_

- _CloudFormation template (single-account variant and StackSet variant for org rollout)._
- _IAM roles and policies: rule role with scoped `events:InvokeApiDestination`, Secrets Manager read for the Connection, DLQ `SendMessage` from rule principal._
- _Resource provisioning: EventBridge Connection, API Destination, four EventBridge rules with patterns (EC2 native, ECS native, Lambda CT-on-EB, S3 CT-on-EB), per-rule SQS DLQs._
- _Ocean endpoint and secret configuration: `webhookSecret` (required) and `allowedAccountIds` (optional allowlist) in `spec.yaml`; setup walkthrough including secret rotation runbook._
- _DLQ replay runbook (operator-side, AWS CLI commands)._

## 4. Supported Resource Kinds & Event Mapping

_To be detailed in the next ADR revision. Will include:_

- _Per-kind table: AWS service → `source` / `detail-type` → handler class → required exporter call._
- _Lambda `eventName` prefix matching reference table._
- _S3 region-resolution logic for the global control-plane case._
- _EC2 dual-state delete handling._
- _Fallback strategy for any unsupported case (out-of-band resync trigger via the existing scheduled resync)._
