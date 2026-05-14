# ADR: AWS-V3 Live Events Support

---

## 1. Context

AWS-V3 keeps Port's catalog in sync via a scheduled, full resync — every
kind, every region, every account walked on a fixed cadence. Three problems
with that model at scale:

1. **Slow visibility.** Infra changes (deployments, scaling, IAM, terminations)
   show up at the next resync — minutes to hours behind reality.
2. **Cost and blast radius.** A full crawl across hundreds of accounts × dozens
   of regions × every kind is API-heavy and bumps into AWS rate limits.
3. **Catalog drift.** Workflows that key off the catalog (ownership,
   scorecards, self-serve actions) operate on stale state between resyncs.

This ADR covers a live-event path that runs alongside resync. Resync stays
the source of truth for full reconciliation and for changes AWS doesn't
surface as events; live events handle everything in between.

---

## 2. Goals & non-goals

### Goals

- Reflect AWS resource changes in Port within seconds.
- Reuse `aws/core/exporters/` for the resource fetch — handlers pull an
  identifier off the event and call the same `get_resource` the resync uses.
- Idempotent upserts and deletes; duplicate deliveries must be safe.
- Multi-account (AWS Organizations + standalone) and multi-region from day one.
- Authenticate every inbound event; reject anything that fails verification
  with HTTP 401.
- No blocking work on the resync loop.
- Cheap to extend — a new kind is ~30 lines plus one EventBridge rule.

### Non-goals

- Replacing the resync. Resync still owns initial hydration, reconciliation,
  and anything that doesn't emit events (out-of-band drift, console-only
  changes on services without CloudTrail).
- Data-plane events (per-object S3 PUTs, per-row RDS writes). Scope is
  control-plane changes.
- Polling AWS Config / Security Hub. Both evaluated and rejected below.

---

## 3. Candidate architectures

Three AWS-native designs evaluated end-to-end.

### Option A — EventBridge → SNS → HTTPS webhook (**chosen**)

```
[Member account A, region us-east-1] ┐
[Member account A, region eu-west-1] ┤
[Member account B, region us-east-1] ┼─► EventBridge rules ──► SNS topic ──► HTTPS POST
[Member account B, region ap-south-1]┤    (in each region)     (hub acct)    Ocean webhook
[Member account C, region us-east-1] ┘
```

| Dimension          | Detail                                                                                                                                                                                                                                                                                |
|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mechanism          | Native EventBridge service events + CloudTrail-via-EventBridge for kinds without native lifecycle events. Cross-account `SNS:Publish` to a single hub topic. HTTPS subscription delivers to Ocean's integration endpoint.                                                              |
| Latency            | 2–5 seconds from AWS event to Port upsert.                                                                                                                                                                                                                                             |
| Coverage           | Anything emitted to EventBridge or CloudTrail. Day-one: EC2, ECS Service, Lambda, S3. Each additional kind = one rule + one processor.                                                                                                                                                 |
| Reliability        | SNS retries HTTPS deliveries with exponential backoff for ~1 hour. Exhausted retries land in an SQS DLQ on the hub. Stale state is reconciled on the next resync.                                                                                                                      |
| Customer burden    | One CloudFormation StackSet for member accounts, one stack for the hub. Subscription auto-confirms on first delivery. No long-running customer infra.                                                                                                                                  |
| Multi-account/region | Single hub topic in any account the customer designates. Cross-account policy lets every `events.amazonaws.com` principal in every member account publish. Per-region EventBridge rules forward to the same hub.                                                                       |
| Cost               | SNS: $0.50 per 1M messages + $0.06 per 100k HTTPS notifications. EventBridge: $1 per 1M custom events; AWS service events are free. Realistic monthly cost for 50 accounts × 10 regions × moderate change rate: under $20.                                                             |
| Security           | (a) SNS X.509 signature on every message — re-verified against a cert-URL allowlist. (b) `aws:PrincipalOrgID` condition pins which org can publish to the topic. (c) Optional HMAC over `webhookSecret` is supported by the integration code but requires an API Gateway in front of the webhook endpoint to inject `X-Port-Signature`; not deliverable via pure EventBridge → SNS → HTTPS due to SNS not supporting custom HTTP headers. |

### Option B — EventBridge → SQS, integration polls

| Dimension            | Detail                                                                                                                                                                                                                                                |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mechanism            | EventBridge targets an SQS queue (or per-region queues with org-wide fan-in via the same hub pattern). The integration runs an asyncio consumer task alongside the resync loop, long-polling `receive_message`.                                      |
| Latency              | 10–60 seconds depending on poll cadence and visibility timeout.                                                                                                                                                                                       |
| Reliability          | First-class. SQS gives durable retention (up to 14 days), per-message ack/visibility, and a DLQ after configurable retries. Survives integration restarts without message loss.                                                                       |
| Customer burden      | Slightly higher: queue + queue policy + DLQ + cross-account access for Ocean's IAM principal. Nicer for self-hosted Ocean — no inbound webhook to expose.                                                                                              |
| Multi-account/region | Same hub-and-spoke pattern as Option A. Works equally well.                                                                                                                                                                                            |
| Cost                 | SQS: $0.40 per 1M requests. With long-polling and batched receives, negligible.                                                                                                                                                                       |
| Security             | IAM-authenticated `ReceiveMessage`. No public endpoint. Strictly stronger than HTTPS.                                                                                                                                                                  |
| Trade-off            | Ocean's primary live-event idiom is `AbstractWebhookProcessor` over HTTP (see the GitHub integration). An SQS consumer means a parallel event loop, lifecycle management, graceful shutdown — more moving parts for a framework that doesn't expect them. |

### Option C — AWS Config rules → SNS / EventBridge

| Dimension          | Detail                                                                                                                                                                                                                                              |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mechanism          | Customer enables AWS Config recorder + rules in every (account, region). Config snapshots fan out to SNS or EventBridge.                                                                                                                              |
| Latency            | Minutes. Config evaluates on a periodic snapshot cadence; not a true event source.                                                                                                                                                                   |
| Coverage           | Excellent — Config sees every supported resource type, and `OversizedConfigurationItemChangeNotification` carries full state inline, eliminating a re-describe.                                                                                       |
| Reliability        | Good once enabled.                                                                                                                                                                                                                                   |
| Customer burden    | Very high. Config must be enabled org-wide with an S3 delivery bucket per region. Many customers don't run Config.                                                                                                                                   |
| Cost               | $0.003 per configuration item recorded. At scale, hundreds of dollars per month per account.                                                                                                                                                         |
| Verdict            | Wrong tool. Config is for compliance evaluation, not real-time fan-out. The latency and cost miss the "seconds, not minutes" goal entirely.                                                                                                          |

### Option D (rejected outright) — Per-kind SDK polling

Polling each AWS service's `DescribeX` / `ListX` on a tight interval. This
is what the existing resync already does — running it faster just runs it
more expensively. Dismissed.

---

## 4. Chosen architecture

**Option A: EventBridge → SNS → HTTPS webhook.**

Four reasons:

1. **Framework fit.** `AbstractWebhookProcessor` is Ocean's documented
   live-event extension point (the GitHub integration uses it; the task brief
   references it). Option A maps onto it 1:1 — single endpoint, dispatch by
   `detail-type`, native retry and signature semantics from SNS.

2. **Latency budget.** 2–5 seconds sits inside the "seconds, not minutes"
   goal. Option B would force a choice between tight polling (latency-friendly
   but expensive) and loose polling (cheap but slow). Push avoids the choice.

3. **Multi-account scalability.** A single hub SNS topic with a policy that
   grants `SNS:Publish` to every `events.amazonaws.com` principal in the
   org (via `aws:PrincipalOrgID`) is the cleanest fan-in pattern AWS offers.
   Standalone accounts use the same template with explicit account IDs
   listed in the policy.

4. **Operational simplicity.** One StackSet rollout to the org, one stack
   in the hub account. No long-running customer infra; no Ocean IAM
   principal to grant cross-account queue access.

### Trade-offs against Option B

- **No durable retention.** SNS HTTPS retries for ~1 hour and then drops
  to the DLQ. Events that miss the DLQ window during a long Ocean outage
  are lost.

  *Mitigation*: resync is still the source of truth. Anything live events
  miss is reconciled at the next pass. The DLQ holds 14 days for manual
  replay.

- **Public endpoint required.** Self-hosted customers need to expose
  the HTTPS endpoint. SaaS Ocean already does.

  *Mitigation*: the per-kind processors are transport-agnostic — adding an
  SQS consumer in front of them later is a local change, not a rewrite.

---

## 5. Required customer infrastructure

### 5.1 Topology

```
┌────────────────────── Hub account (chosen by customer) ──────────────────────┐
│                                                                              │
│   SNS Topic: port-aws-v3-live-events                                         │
│      ├── Topic policy: Allow events.amazonaws.com from <OrgID> to Publish    │
│      ├── HTTPS Subscription → https://<ocean-base>/integration/webhook       │
│      └── Redrive policy → SQS DLQ: port-aws-v3-live-events-dlq               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
              ▲                          ▲                          ▲
              │                          │                          │
        publish (cross-acct)       publish (cross-acct)       publish (cross-acct)
              │                          │                          │
┌─── Member account A ──┐    ┌─── Member account B ──┐    ┌─── Member account C ──┐
│  EventBridge rule    │    │  EventBridge rule    │    │  EventBridge rule    │
│  per region:         │    │  per region:         │    │  per region:         │
│   - EC2 state-change │    │   - EC2 state-change │    │   - EC2 state-change │
│   - ECS service ev   │    │   - ECS service ev   │    │   - ECS service ev   │
│   - Lambda CT events │    │   - Lambda CT events │    │   - Lambda CT events │
│   - S3 CT events     │    │   - S3 CT events     │    │   - S3 CT events     │
└──────────────────────┘    └──────────────────────┘    └──────────────────────┘
```

### 5.2 IAM — least privilege

The existing assume-role chain already grants `Describe*` / `Get*` for every
kind covered, so the integration's read path needs no new IAM.

Customer-side IAM stays narrow:

- **EventBridge → SNS**: the `events.amazonaws.com` service principal gets
  `SNS:Publish` on the hub topic, scoped by `aws:SourceArn` per rule and
  (where applicable) by `aws:PrincipalOrgID`.
- **SNS → DLQ**: the `sns.amazonaws.com` service principal gets
  `SQS:SendMessage` on the DLQ, scoped by `aws:SourceArn`.

No customer-managed IAM users; no long-lived credentials.

### 5.3 Provisioning

Two CloudFormation templates under `docs/cloudformation/`:

1. `live-events-hub.yaml` — deployed once to the chosen hub account & region.
   Provisions the SNS topic, topic policy, DLQ, and HTTPS subscription.
   Parameters: `OceanWebhookUrl`, `OrganizationId` (optional),
   `AllowedAccountIds` (for non-org setups).
2. `live-events-member.yaml` — deployed as a StackSet across every member
   account in every region the customer cares about. Provisions per-kind
   EventBridge rules that forward events to the hub SNS topic.

README walks through both, plus `webhookSecret` configuration.

### 5.4 Ocean configuration

Three new fields in `.port/spec.yaml`:

| Field                  | Type    | Default          | Purpose                                                                                                                  |
|------------------------|---------|------------------|--------------------------------------------------------------------------------------------------------------------------|
| `webhookSecret`        | string  | none             | Shared secret for the HMAC layer. When empty, only the SNS X.509 signature is enforced.                                  |
| `liveEventsEnabled`    | bool    | `true`           | Kill-switch. When false, the endpoint stays registered but every event short-circuits with a warning log.                |
| `snsCertHostAllowlist` | string  | `amazonaws.com`  | Comma-separated host suffixes whose certs are trusted. The verifier still pins the `sns.` prefix on top of this.         |

`saas.liveEvents.enabled` flipped to `true` so Ocean SaaS exposes a public
webhook URL.

---

## 6. Supported resource kinds & event mapping

| Kind                     | AWS source                       | EventBridge `detail-type`                                | Identifier path                                            | Delete trigger                                                                                  |
|--------------------------|----------------------------------|----------------------------------------------------------|------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `AWS::EC2::Instance`     | EC2 native                       | `EC2 Instance State-change Notification`                 | `detail.instance-id`                                       | `detail.state ∈ {shutting-down, terminated}`                                                     |
| `AWS::ECS::Service`      | ECS native                       | `ECS Service Action`, `ECS Deployment State Change`      | `resources[0]` (service ARN, parsed for cluster + name)    | `detail.eventName == "SERVICE_DELETED"`                                                          |
| `AWS::Lambda::Function`  | CloudTrail via EventBridge       | `AWS API Call via CloudTrail` (`eventSource = lambda.amazonaws.com`) | `detail.requestParameters.functionName`              | `detail.eventName == "DeleteFunction20150331"`                                                   |
| `AWS::S3::Bucket`        | CloudTrail via EventBridge       | `AWS API Call via CloudTrail` (`eventSource = s3.amazonaws.com`) | `detail.requestParameters.bucketName`                  | `detail.eventName == "DeleteBucket"`                                                             |

### Coverage gaps

- **S3 and Lambda lifecycle aren't native EventBridge events.** Both only
  surface via CloudTrail, so the member StackSet assumes CloudTrail is
  enabled and forwarding management events to the default bus. This is the
  AWS default for new accounts. Flagged as a pre-deployment check in the
  README.
- **`AWS::Account::Info`, `AWS::Organizations::Account`** are resync-only by
  design. They change rarely; the resync cadence is fine for them.
- **`AWS::RDS::DBInstance`, `AWS::EKS::Cluster`, `AWS::SQS::Queue`,
  `AWS::ECR::Repository`, `AWS::EC2::Volume`, `AWS::ECS::Cluster`,
  `AWS::ECS::TaskDefinition`** are extensible: one processor subclass + one
  EventBridge rule each. The framework supports them; the handlers were
  deferred to keep the PR reviewable.
- **Anything else.** The resync still covers it. Unknown `detail-type` values
  are logged with full context and dropped — no silent failures, no retries.

---

## 7. Implementation outline

OOP and SOLID by construction; one responsibility per class.

```
aws/webhook/
├── __init__.py
├── registry.py             # ocean.add_webhook_processor(WEBHOOK_PATH, ...)
├── events.py               # detail-type constants, delete-event predicates
├── signature.py            # SnsSignatureVerifier, HmacSignatureVerifier
├── idempotency.py          # InMemoryIdempotencyStore (TTL LRU)
├── session_resolver.py     # AccountSessionResolver: account_id → AioSession
└── processors/
    ├── __init__.py
    ├── base.py             # AWSLiveEventProcessor(AbstractWebhookProcessor)
    ├── sns_subscription.py # auto-confirms SNS SubscriptionConfirmation
    ├── ec2_instance.py
    ├── ecs_service.py
    ├── lambda_function.py
    └── s3_bucket.py
```

Class responsibilities:

- **`AWSLiveEventProcessor`** (abstract base). Implements `authenticate`,
  `validate_payload`, `should_process_event`, and a templated `handle_event`
  that drives the per-kind subclass through five hooks:
  - `kind: str`
  - `detail_types: frozenset[str]`
  - `event_sources: frozenset[str]` (narrowing for CloudTrail-routed events)
  - `extract_identifier(envelope) → dict | None`
  - `is_delete(envelope) → bool`
  - `build_request(identifier, account_id, region, include) → ResourceRequestModel`
  - `exporter_cls: type[IResourceExporter]`

- **`SnsSignatureVerifier`**. Fetches and caches the SNS signing cert from a
  URL allowlist, rebuilds the canonical string-to-sign per the SNS spec,
  verifies the RSA signature (SHA-1 or SHA-256 depending on
  `SignatureVersion`). Bad cert URL or bad signature → HTTP 401.

- **`HmacSignatureVerifier`** (optional layer). Constant-time
  `HMAC-SHA256(webhookSecret, body)` against `X-Port-Signature`. Only
  enforced when `webhookSecret` is set.

- **`InMemoryIdempotencyStore`**. TTL LRU on SNS `MessageId`. First delivery
  wins; duplicates short-circuit. 10-minute TTL is comfortably wider than
  SNS's per-message retry window.

- **`AccountSessionResolver`**. Wraps `get_all_account_sessions()` with a
  lookup keyed on `account_id`. Refresh-on-miss handles newly-added org
  accounts between resyncs.

- **`SnsSubscriptionConfirmationProcessor`**. Recognises
  `Type=SubscriptionConfirmation`, validates the `SubscribeURL` host against
  the same allowlist as the signing cert, and confirms the subscription.
  Without this, every deploy would leave the subscription in
  `PendingConfirmation`.

### Concurrency & non-blocking

`AbstractWebhookProcessor` instances run in Ocean's webhook task pool — one
asyncio task per inbound POST. Resync runs on its own scheduler. Shared
state is limited to the module-level caches (idempotency, sessions, certs),
all read-mostly with write-side locks.

---

## 8. Failure modes

| Failure                                              | Behavior                                                                                                                       |
|------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| SNS signature invalid                                | HTTP 401, log `outcome=rejected_signature`                                                                                     |
| HMAC mismatch (when configured)                      | HTTP 401, log `outcome=rejected_hmac`                                                                                          |
| Unknown `detail-type`                                | HTTP 200, log `outcome=skipped_unknown`, no further work                                                                       |
| Duplicate `MessageId`                                | HTTP 200, log `outcome=skipped_duplicate`, no further work                                                                     |
| `account_id` not in current strategy                 | One refresh attempt; if still missing, log `outcome=skipped_unknown_account` and let the next resync handle it.                |
| Exporter `get_resource` throttled                    | Raise `RetryableError`; Ocean's framework retries with exponential backoff up to `max_retries`. Past that, SNS DLQ.            |
| Resource gone from AWS (404)                         | Emit a delete payload, log `outcome=delete_on_404`.                                                                            |
| Catalog upsert failure                               | Propagate to the framework; framework handles retries and DLQ semantics.                                                       |

---

## 9. Observability

Structured fields on every event:

- `trace_id` (from `WebhookEvent`)
- `kind`
- `account_id`
- `region`
- `detail_type`
- `outcome` ∈ `upserted`, `deleted`, `skipped_unknown`, `skipped_duplicate`,
  `skipped_unknown_account`, `rejected_signature`, `rejected_hmac`,
  `delete_on_404`, `error_retryable`, `error_fatal`
- `latency_ms` (end-to-end from `WebhookEvent.created_at`)

Plain `extra={...}` on loguru — no new emission channel.

---

## 10. Testing strategy

Tests mirror the implementation tree under `tests/webhook/`:

| Test                                       | Asserts                                                                  |
|--------------------------------------------|--------------------------------------------------------------------------|
| `test_signature.py::test_valid_sns_sig`    | Synthesised signed body + cert → verifier accepts                         |
| `test_signature.py::test_invalid_sns_sig`  | Tampered body rejected; bad signing-cert URL rejected                     |
| `test_signature.py::test_hmac_*`           | Valid / invalid HMAC, constant-time compare                              |
| `test_idempotency.py`                      | First-write wins; TTL eviction; concurrent inserts                       |
| `test_session_resolver.py`                 | Account hit; cache miss triggers single refresh; unknown returns None    |
| `processors/test_ec2_instance.py`          | `running` → upsert; `terminated` → delete                                |
| `processors/test_ecs_service.py`           | Deployment state change → upsert; `SERVICE_DELETED` → delete             |
| `processors/test_lambda_function.py`       | `UpdateFunctionConfiguration` → upsert; `DeleteFunction20150331` → delete |
| `processors/test_s3_bucket.py`             | `CreateBucket` → upsert; `DeleteBucket` → delete                         |
| `test_routing.py`                          | Unknown `detail-type` → skipped; duplicate MessageId → skipped; only the matching processor claims each event |

Every AWS and Port call is mocked. LocalStack remains optional for
end-to-end exploration via the README walkthrough.

---

## 11. Rollout

1. Live events default `liveEventsEnabled: true` in `spec.yaml` for SaaS
   Ocean. Self-hosted operators can flip it off.
2. Customer deploys the hub stack + the member StackSet.
3. Subscription auto-confirms on first delivery via
   `SnsSubscriptionConfirmationProcessor`.
4. Operator validates by grepping logs for `outcome=upserted`.
5. Resync cadence is unchanged for now. Over time the resync interval can
   be relaxed (hourly → daily) once live events have demonstrated their
   freshness in production; that tuning is a customer decision and out of
   scope for this ADR.

---

## 12. Open questions / future work

- **SQS transport for self-hosted Ocean.** Option B as a follow-up. The
  per-kind processors don't care which transport feeds them.
- **Schema drift.** AWS adding fields to a `detail-type` doesn't break the
  integration — identifier extractors only touch a narrow set of keys. New
  fields surface via the existing `get_resource` describe path on the next
  resync.
- **Per-customer EventBridge bus.** Some orgs centralise events on a custom
  bus already. A future iteration could let customers point that bus at the
  hub topic instead of running the member StackSet.
