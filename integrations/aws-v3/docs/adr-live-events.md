# ADR: AWS-V3 Live Events Support

**Status:** Accepted  
**Date:** 2026-05-07  
**Author:** Sunday Goodnews (Geddy)

---

## Context

The existing AWS-V3 integration is poll-based. A full resync scans every account,
every region, and every resource kind on a schedule. For customers who need timely
visibility — deployments, scaling events, security changes — this introduces
unacceptable lag (minutes to hours depending on resync interval).

We need a real-time event-driven path that sits alongside the existing resync
mechanism without disrupting it.

---

## Candidate Architectures

### Option 1: AWS CloudTrail + EventBridge + Lambda

| Dimension | Assessment |
|---|---|
| Mechanism | CloudTrail records every API call. EventBridge rules filter CloudTrail events and invoke a Lambda that calls Ocean's webhook endpoint. |
| Latency | 15–60 seconds (CloudTrail has inherent delivery delay) |
| Coverage | Only tracks API-level calls — misses console or SDK actions that don't produce CloudTrail events. Also misses state changes not triggered by API calls (e.g. instance health check failures). |
| Reliability | Lambda cold starts can add latency. Failed invocations need DLQ configuration. |
| Customer Burden | High — customer must deploy a Lambda function per account, configure CloudTrail in each region, and manage Lambda IAM roles. |
| Multi-account/region | Complex — Lambda must be deployed per account. Centralized via Organizations Service Control Policies adds further setup. |
| Cost | CloudTrail data events are expensive at scale ($2/100k events). Lambda invocations add cost. |
| Security | Lambda must validate that events genuinely come from EventBridge (resource policy). |

**Verdict:** High latency, expensive, operationally heavy. Ruled out.

---

### Option 2: AWS Config + EventBridge

| Dimension | Assessment |
|---|---|
| Mechanism | AWS Config tracks configuration changes. EventBridge rules on Config events push to an SNS/SQS/webhook target. |
| Latency | 1–3 minutes — Config evaluates on a schedule or on change, but delivery is not instantaneous. |
| Coverage | Only covers configuration changes (what a resource looks like), not operational state changes (an EC2 instance failing a health check does not produce a Config event). |
| Reliability | Config has its own delivery guarantees. EventBridge adds durability. |
| Customer Burden | Medium — Config Recorder must be enabled per region/account (costs money per configuration item recorded). |
| Multi-account/region | AWS Config Aggregator supports multi-account but adds setup complexity. |
| Cost | $0.003 per configuration item recorded. For large environments this adds up quickly. |
| Security | EventBridge resource policies control who can receive events. |

**Verdict:** Too slow and misses operational events. Ruled out.

---

### Option 3: EventBridge + SNS + SQS → Ocean Webhook (Chosen)

| Dimension | Assessment |
|---|---|
| Mechanism | EventBridge default event bus captures native AWS service events (EC2 state changes, ECS deployments, Lambda updates, S3 events) in near-real-time. EventBridge rules forward matched events to an SNS topic. SNS fans out to an SQS queue. Ocean polls the SQS queue and calls its own webhook handler — OR EventBridge sends directly to the Ocean HTTP endpoint via an HTTPS target. |
| Latency | Under 5 seconds end-to-end from AWS resource change to Port catalog update. |
| Coverage | All native AWS service events — EC2 state changes, ECS service deployments and scaling, Lambda create/update/delete, S3 bucket create/delete, and many more. Does not require API-call-level tracking. |
| Reliability | SQS provides durability and at-least-once delivery. Dead-letter queues catch failures. EventBridge retries on delivery failure. |
| Customer Burden | Medium — customer deploys a CloudFormation stack that creates EventBridge rules, SNS topic, SQS queue, and IAM role. One-time setup, works across all regions via EventBridge global endpoints or per-region stacks. |
| Multi-account/region | EventBridge supports cross-account event buses natively. A central event bus in a management account can aggregate events from all member accounts via resource policies and cross-account EventBridge rules. |
| Cost | EventBridge: $1/million events. SNS: $0.50/million. SQS: $0.40/million. Negligible at typical infrastructure change rates. |
| Security | SNS message signing (X-Amz-Sns-Message-Signature header) allows the Ocean webhook to verify that messages genuinely came from SNS. Webhook secret provides a second layer. |

**Verdict:** Best latency, best coverage, operationally manageable, cost-effective. **Selected.**

---

## Chosen Architecture: EventBridge → SNS → Ocean Webhook

```
AWS Resource Change (EC2, ECS, Lambda, S3, ...)
    │
    ▼
EventBridge Default Event Bus (per region, per account)
    │  EventBridge rule with event pattern filter
    ▼
SNS Topic  (port-live-events)
    │  HTTPS subscription
    ▼
Ocean Webhook Endpoint  POST /integration/live-events/webhook
    │  Signature validation → event routing → handler dispatch
    ▼
Per-Kind Handler (EC2 / ECS / Lambda / S3)
    │  fetch full resource state via existing exporters
    ▼
Port API  (upsert or delete entity)
```

### Multi-account flow

Each member account deploys the CloudFormation stack (EventBridge rule → SNS).
The SNS topic in each account sends to the **same** Ocean webhook endpoint.
Ocean identifies the account via the `account` field in the EventBridge envelope.
Sessions are resolved using the existing `get_all_account_sessions()` mechanism.

For AWS Organizations customers, a single EventBridge cross-account rule in the
management account can aggregate all member account events, reducing per-account
setup to zero.

---

## Required Customer Infrastructure

### CloudFormation stack

See `cloudformation/live-events.yaml` in this directory.

#### What it creates

- **EventBridge rules** (one per resource kind) on the default event bus in each region
- **SNS topic** — `port-live-events` — with an HTTPS subscription pointing to the Ocean endpoint
- **SQS dead-letter queue** for failed SNS deliveries
- **IAM role** — least-privilege: `events:PutTargets` on the SNS topic, `sns:Publish` from EventBridge

#### IAM policy (least privilege)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEventBridgePublishToSNS",
      "Effect": "Allow",
      "Principal": { "Service": "events.amazonaws.com" },
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:*:ACCOUNT_ID:port-live-events"
    }
  ]
}
```

Ocean's IAM role (for fetching full resource state) needs only:
- `ec2:DescribeInstances`
- `ecs:DescribeServices`, `ecs:ListClusters`, `ecs:ListServices`
- `lambda:GetFunction`, `lambda:ListFunctions`
- `s3:GetBucketLocation`, `s3:GetBucketTagging`

No write permissions required.

---

## Supported Resource Kinds & Event Mapping

| Kind | AWS Source | Event detail-type | Live events supported |
|---|---|---|---|
| `AWS::EC2::Instance` | EC2 | `EC2 Instance State-change Notification` | ✅ upsert on state change, delete on terminated |
| `AWS::ECS::Service` | ECS | `ECS Service Action`, `ECS Deployment State Change` | ✅ upsert on deployment/scaling |
| `AWS::Lambda::Function` | Lambda | `AWS API Call via CloudTrail` (CreateFunction, UpdateFunctionCode, DeleteFunction) | ✅ upsert on create/update, delete on delete |
| `AWS::S3::Bucket` | S3 | `AWS API Call via CloudTrail` (CreateBucket, DeleteBucket) | ✅ upsert on create, delete on delete |
| `AWS::RDS::DBInstance` | RDS | `RDS DB Instance Event` | ❌ not in scope — fallback to resync |
| `AWS::EKS::Cluster` | EKS | No native EventBridge events | ❌ no native events — fallback to resync |
| `AWS::SQS::Queue` | SQS | No native EventBridge events | ❌ no native events — fallback to resync |
| `AWS::ECR::Repository` | ECR | `ECR Repository Action` | ❌ not in scope — fallback to resync |

### Fallback strategy for unsupported kinds

Resources without native EventBridge events (EKS, SQS, ECR, RDS) continue to be
served by the existing scheduled resync mechanism. This is documented in the
integration's README and spec.yaml. No data loss occurs — they are simply not
updated in real-time.

---

## Consequences

- The existing resync mechanism is unchanged. Live events supplement it.
- Customers who do not deploy the CloudFormation stack see no change in behaviour.
- Customers who deploy the stack get sub-5-second updates for the four supported kinds.
- The webhook endpoint must be exposed publicly (or via a reverse proxy) for SNS to deliver.
- SNS signature validation ensures only genuine AWS events are processed.
