# ADR: AWS Live Events Support for Port Ocean AWS-V3 Integration
 
**Date:** 2026-05-09  
**Authors:** Sikiru Ayinlade

---

## Context

The AWS-V3 Ocean integration is currently poll-based: a full resync scans every account, every region, and every resource kind on a schedule. For customers who need timely visibility into infrastructure changes (deployments, EC2 state changes, Lambda updates, S3 bucket lifecycle), this approach is:

- **Slow** — up to 30–60 minutes between a real change and its reflection in Port
- **Expensive** — AWS API calls scale with accounts × regions × kinds × polling frequency
- **Noisy** — unchanged resources are repeatedly fetched and compared

The goal is to add an event-driven update path that reflects changes within seconds, without replacing or disrupting the existing resync loop.

---

## 1. Candidate Architectures

### Option A: EventBridge → SNS → Ocean HTTPS Endpoint *(Chosen)*

```
AWS Event Source
    │
    ▼
EventBridge Rule (per region/account)
    │  matches resource-specific patterns
    ▼
SNS Topic (central, or per-account)
    │  HTTPS subscription to Ocean endpoint
    ▼
Ocean /webhook endpoint
    │  validates signature, dispatches handler
    ▼
Port catalog upsert / delete
```

| Dimension | Detail |
|---|---|
| **Mechanism** | EventBridge Rules match CloudWatch Events and CloudTrail API calls; SNS delivers to Ocean HTTPS endpoint |
| **Latency** | 2–10 seconds end-to-end (EventBridge rule evaluation ~1s + SNS delivery ~1s + processing) |
| **Coverage** | EC2 Instance state-change, ECS Service deployment/action, Lambda CloudTrail (create/update/delete), S3 CloudTrail (create/delete), and any future EventBridge-emitting service |
| **Reliability** | SNS retries failed HTTPS deliveries up to 3 times with exponential backoff; messages persist in SNS for up to 23 days during outages |
| **Customer Burden** | One CloudFormation StackSet per account/region; SNS HTTPS subscription auto-confirmed via CloudFormation; ~15 min setup |
| **Multi-account/region** | Deploy EventBridge rules in each account/region; all rules target a SNS Topic in a central account, or a per-account SNS that fans into the same Ocean endpoint; AWS Organizations StackSets automate this |
| **Cost** | EventBridge: $1/million events evaluated; SNS: $0.50/million deliveries. For typical customers (<100k changes/day) cost is negligible (<$5/month) |
| **Security** | Ocean validates HMAC-SHA256 signature (computed by a Lambda shim between SNS and Ocean that adds `x-hub-signature-256` header); SNS subscription uses HTTPS; topic policy restricts publishing to EventBridge only |

**Drawbacks:**
- Requires a small Lambda shim to inject the HMAC header (SNS cannot add custom headers natively)
- SNS HTTPS subscriptions require a publicly reachable Ocean endpoint

---

### Option B: EventBridge → SQS → Polling Worker in Ocean

```
EventBridge Rule → SQS Queue → Ocean polls SQS → processes events
```

| Dimension | Detail |
|---|---|
| **Mechanism** | EventBridge puts events into SQS; Ocean runs a background polling task (every N seconds) to drain the queue |
| **Latency** | 5–30 seconds (polling interval adds delay on top of EventBridge evaluation) |
| **Coverage** | Same as Option A — any EventBridge-emitting service |
| **Reliability** | SQS provides at-least-once delivery with configurable retry (DLQ); survives Ocean restarts (messages queue up) |
| **Customer Burden** | SQS queue + EventBridge rule + IAM role to let Ocean poll. Slightly more infrastructure. Requires Ocean to have `sqs:ReceiveMessage` permission |
| **Multi-account/region** | Central SQS queue in one account; cross-account EventBridge targets forward events to it. Or per-account queues with cross-account Ocean polling |
| **Cost** | SQS: $0.40/million requests. Polling adds request costs (1 req/poll regardless of events). With 5s polling = ~500k requests/month ≈ $0.20/month per queue |
| **Security** | IAM role authentication (no HMAC needed); queue policy restricts access to specific EventBridge bus |

**Drawbacks:**
- Polling loop inside Ocean adds complexity and adds latency
- Requires Ocean process to have long-lived AWS credentials to poll SQS
- Not truly event-driven — still has polling overhead

---

### Option C: EventBridge API Destinations (Direct HTTPS with Auth)

```
EventBridge Rule → API Destination → Ocean /webhook with Authorization header
```

| Dimension | Detail |
|---|---|
| **Mechanism** | EventBridge API Destinations send events directly to the Ocean HTTPS endpoint with a configurable authorization header (API key / OAuth) |
| **Latency** | 1–5 seconds; fastest option (no intermediate service) |
| **Coverage** | Same as Option A |
| **Reliability** | EventBridge retries for up to 24 hours with configurable retry policy; dead-letter SQS queue optional |
| **Customer Burden** | API Destination + Connection resource per account; Ocean endpoint must be public HTTPS; slightly more CloudFormation per rule |
| **Multi-account/region** | Each account needs its own API Destination and EventBridge rule; no cross-account fan-in without an event bus |
| **Cost** | EventBridge: $0.01/100k invocations for API Destinations. More expensive at high volumes than SNS |
| **Security** | API Destination supports `API_KEY` header auth; configure Ocean's `webhookSecret` as the key value; no HMAC but shared bearer token |

**Drawbacks:**
- Higher cost at scale (API Destination invocations are billed separately)
- Per-account/region setup without a clean central fan-in like SNS
- No built-in message batching

---

### Option D: AWS Config + Config Rules → SNS

Uses AWS Config to record every configuration change and stream to SNS. More comprehensive but much higher cost and latency (Config recording is ~5 min delay).

---

## 2. Chosen Architecture & Justification

**Chosen: Option A — EventBridge → SNS → Ocean HTTPS**

### Rationale for choosing Option A

| Factor | Reason                                                                                          |
|---|-------------------------------------------------------------------------------------------------|
| **Latency** | 2–10s matches "seconds, not minutes" requirement                                                |
| **Reliability** | SNS retry + durable buffering covers Ocean restarts                                             |
| **Coverage** | EventBridge natively emits events for all 4 required resource kinds                             |
| **Multi-account/region** | Per-account topics are deployed consistently with StackSets across many accounts and regions    |
| **Customer burden** | Single CloudFormation StackSet; Ocean endpoint URL + secret are the only customer inputs        |
| **Cost** | Negligible for typical customers                                                                |
| **Security** | Lambda shim adds HMAC header; SNS uses HTTPS; topic policy is least-privilege                   |
| **Non-blocking** | Webhook processing runs in Ocean's async worker pool, completely independent of the resync loop |

Option B was rejected because polling inside Ocean re-introduces the polling-latency problem and the SQS queue becomes a single point of failure if the connection is misconfigured. Option C was rejected because it requires per-account API Destinations without a convenient fan-in.

### Architecture Decision

**For customers that prefer zero-Lambda setup**, the SNS HTTPS subscription can point directly at Ocean without the HMAC Lambda shim. In this case, Ocean validates the native SNS payload signature using the `Signature`, `SignatureVersion`, and `SigningCertURL` fields in the SNS envelope, and the `webhookSecret` check is skipped.

**For customers that require HMAC validation**, the CloudFormation template includes a Lambda function (`OceanForwardingLambda`) that:
1. Receives SNS messages
2. Computes `HMAC-SHA256(body, webhookSecret)` and adds it as `x-hub-signature-256` header
3. Forwards to the Ocean endpoint via HTTP POST

---

## 3. Required Customer Infrastructure

### CloudFormation Template

See `cloudformation/live-events-setup.yaml` in this integration directory.

The template provisions:

#### IAM Resources
- **`EventBridgeToSNSRole`** — IAM Role allowing EventBridge to publish to the SNS topic
  - Trust: `events.amazonaws.com`
  - Permissions: `sns:Publish` on the specific topic ARN
- **`OceanForwardingLambdaRole`** — IAM Role for the forwarding Lambda
  - Permissions: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`, `sns:*` (subscribe)

#### EventBridge Rules (per account/region)
- `EC2StateChangeRule` — matches `EC2 Instance State-change Notification`
- `ECSDeploymentRule` — matches `ECS Deployment State Change` and `ECS Service Action`
- `LambdaCloudTrailRule` — matches CloudTrail API calls for `lambda.amazonaws.com`
- `S3CloudTrailRule` — matches CloudTrail API calls for `s3.amazonaws.com` (CreateBucket/DeleteBucket)

#### SNS Resources
- **`OceanLiveEventsTopic`** — SNS topic for receiving all live events
- **`OceanTopicPolicy`** — restricts publishing to EventBridge service only
- **`OceanHTTPSSubscription`** — HTTPS subscription pointing to `{OceanEndpointURL}/webhook`
  - (Or a Lambda subscription if HMAC forwarding Lambda is enabled)

#### Parameters

| Parameter | Description | Default |
|---|---|---|
| `OceanEndpointURL` | Public HTTPS URL of the Ocean integration endpoint | (required) |
| `WebhookSecret` | Shared HMAC secret (also set in Ocean `webhook_secret` config) | `""` (empty = use native SNS signature validation) |
| `EnableHMACLambda` | Whether to deploy the HMAC-signing forwarding Lambda | `false` |
| `CloudTrailEnabled` | Whether to create the CloudTrail-backed Lambda and S3 EventBridge rules | `true` |

### Console Walkthrough (Alternative to CloudFormation)

1. **Create SNS Topic** in `us-east-1` (or your primary region):
   - Name: `port-ocean-live-events`
   - Create HTTPS subscription: `https://<ocean-endpoint>/webhook`
   - Confirm subscription (AWS sends a SubscriptionConfirmation — Ocean logs and accepts it)

2. **Create EventBridge Rule** in each region you want live events from:
   - Event bus: default
   - Event pattern: see patterns below
   - Target: SNS topic ARN (above)
   - Create a new IAM role allowing `sns:Publish`

3. **Enable CloudTrail** (for Lambda and S3 events):
   - Create a Trail (or use existing)
   - Enable CloudWatch Logs delivery

4. **Set Ocean config**:
  - `webhookSecret`: same value as `WebhookSecret` parameter if HMAC forwarding is enabled
  - leave `webhookSecret` empty to use native SNS signature validation for direct HTTPS delivery

#### EventBridge Patterns

**EC2 state changes:**
```json
{
  "source": ["aws.ec2"],
  "detail-type": ["EC2 Instance State-change Notification"]
}
```

**ECS service events:**
```json
{
  "source": ["aws.ecs"],
  "detail-type": ["ECS Deployment State Change", "ECS Service Action"]
}
```

**Lambda CloudTrail:**
```json
{
  "source": ["aws.cloudtrail"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["lambda.amazonaws.com"],
    "eventName": [
      "CreateFunction20150331",
      "UpdateFunctionCode20150331v2",
      "UpdateFunctionConfiguration20150331v2",
      "PublishVersion",
      "UpdateAlias",
      "DeleteFunction20150331"
    ]
  }
}
```

**S3 CloudTrail:**
```json
{
  "source": ["aws.cloudtrail"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventSource": ["s3.amazonaws.com"],
    "eventName": ["CreateBucket", "DeleteBucket"]
  }
}
```

### Multi-Account Setup with AWS Organizations

For organizations with many accounts, deploy the same per-account stack with StackSets:

1. **Deploy StackSet** targeting all OUs or specific accounts:
   ```bash
   aws cloudformation create-stack-set \
     --stack-set-name port-ocean-live-events \
     --template-body file://cloudformation/live-events-setup.yaml \
     --parameters ParameterKey=OceanEndpointURL,ParameterValue=https://your-ocean-host/webhook \
     --capabilities CAPABILITY_NAMED_IAM \
     --permission-model SERVICE_MANAGED
   ```

For **standalone accounts** (non-Organization), deploy the CloudFormation template independently in each account, each pointing to the same Ocean endpoint.

---

## 4. Supported Resource Kinds & Event Mapping

| Kind | AWS Source | EventBridge Detail-Type | Event Names / States | Action |
|---|---|---|---|---|
| `AWS::EC2::Instance` | EC2 | `EC2 Instance State-change Notification` | All states | `running/stopped/...` → upsert; `terminated/shutting-down` → delete |
| `AWS::ECS::Service` | ECS | `ECS Deployment State Change` | `SERVICE_DEPLOYMENT_COMPLETED`, `SERVICE_DEPLOYMENT_FAILED`, etc. | upsert |
| `AWS::ECS::Service` | ECS | `ECS Service Action` | `SERVICE_TASK_PLACEMENT_FAILURE`, etc. | upsert |
| `AWS::Lambda::Function` | CloudTrail | `AWS API Call via CloudTrail` | `CreateFunction20150331`, `UpdateFunctionCode20150331v2`, `UpdateFunctionConfiguration20150331v2` | upsert |
| `AWS::Lambda::Function` | CloudTrail | `AWS API Call via CloudTrail` | `DeleteFunction20150331` | delete |
| `AWS::S3::Bucket` | CloudTrail | `AWS API Call via CloudTrail` | `CreateBucket` | upsert |
| `AWS::S3::Bucket` | CloudTrail | `AWS API Call via CloudTrail` | `DeleteBucket` | delete |

### Unsupported Kinds (Fallback: Scheduled Resync)

The following resource kinds do not have native EventBridge event sources for all lifecycle changes. They continue to rely on the scheduled resync loop:

| Kind | Limitation | Fallback |
|---|---|---|
| `AWS::EKS::Cluster` | No fine-grained EventBridge events for cluster updates (only creation via CloudTrail) | Scheduled resync |
| `AWS::RDS::DBInstance` | RDS events via EventBridge are limited (no direct CloudTrail for describe calls) | Scheduled resync |
| `AWS::SQS::Queue` | No EventBridge source for queue attribute changes | Scheduled resync |
| `AWS::ECR::Repository` | ECR events via CloudTrail only; no lifecycle events | Scheduled resync |
| `AWS::EC2::Volume` | EBS volume events available via CloudTrail but not included in v1 | Future enhancement |
| `AWS::Organizations::Account` | Account events available but not included in v1 | Scheduled resync |

**Recommended fallback strategy:** Reduce the resync interval for unsupported kinds (e.g., every 15 minutes instead of every hour) to compensate for the lack of live events.
