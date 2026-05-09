# ADR: AWS-V3 Live Events (EventBridge -> Ocean)

Date: 2026-05-08

Status: Proposed

Context
-------
The current aws-v3 integration is poll/resync-based. Customers need near real-time catalog updates when AWS resources change.

Decision
--------
We will implement an event-driven path that accepts AWS events forwarded to Ocean over HTTPS. The recommended customer architecture is: AWS EventBridge (or native service events) -> EventBridge Rule -> SNS (optional) -> HTTPS Target (Ocean integration endpoint) OR use EventBridge API Destinations to send signed HTTPS requests directly to Ocean. For multi-account support, customers will create EventBridge rules in each account/region or configure Organizations EventBridge in the management account to forward events.

Candidate Architectures
-----------------------

1) EventBridge -> API Destination (signed request) -> Ocean
  - Mechanism: EventBridge API Destination with an API key/secret. EventBridge signs events.
  - Latency: very low (seconds)
  - Coverage: all EventBridge-supported services (CloudTrail, S3, EC2 state-change, ECS, Lambda)
  - Reliability: EventBridge built-in retry/dlq
  - Customer Burden: minimal console/CloudFormation setup
  - Multi-account/region: Use EventBridge in each account or Organizations
  - Cost: EventBridge invocation costs + API Destination costs
  - Security: API Destination supports auth (API Key); additionally we validate HMAC secrets on the Ocean side

2) EventBridge -> SNS -> HTTPS (Ocean) (recommended for broad compatibility)
  - Mechanism: EventBridge rule to SNS topic; SNS subscription is HTTPS to Ocean
  - Latency: low (seconds)
  - Coverage: same as EventBridge
  - Reliability: SNS retries and DLQ options
  - Customer Burden: moderate (create SNS topic, subscription confirmation)
  - Multi-account/region: Topics per account/region or cross-account SNS
  - Cost: SNS + EventBridge
  - Security: SNS supports subscription verification; we additionally require a webhookSecret and validate HMAC

3) CloudTrail -> EventBridge -> SQS -> Lambda -> Ocean (fan-out + buffering)
  - Mechanism: CloudTrail events captured by EventBridge → SQS for buffering → Lambda to transform and POST to Ocean
  - Latency: moderate (seconds to tens of seconds)
  - Coverage: CloudTrail-supported management/data events
  - Reliability: SQS persists events; Lambda retries
  - Customer Burden: higher setup complexity
  - Multi-account/region: SQS centralization possible via cross-account
  - Cost: SQS + Lambda + EventBridge
  - Security: IAM roles, signing from Lambda to Ocean; validate payload signature

Chosen Architecture & Justification
----------------------------------
We choose EventBridge -> SNS -> HTTPS (Ocean) as the primary recommended pattern for customers, with EventBridge API Destination as an alternative. SNS provides reliable delivery, simple DLQ configuration, and wide compatibility. It also allows customers to keep event routing within AWS and avoid building Lambdas. We will support events delivered via HTTPS POST to Ocean and require a webhookSecret (HMAC) validation to authenticate events.

Required Customer Infrastructure (CloudFormation Walkthrough)
-----------------------------------------------------------
This minimal template shows SNS + EventBridge rule + IAM least-privilege roles. See `../templates/live-events.yaml` for a full template.

Key resources customers must create (summary):
- IAM Role allowing EventBridge to publish to SNS (if cross-account)
- EventBridge Rule with appropriate EventPattern for resource types (e.g., EC2 state-change, S3, ECS, Lambda)
- SNS Topic and HTTPS subscription to Ocean endpoint: https://<OCEAN_BASE>/integration/webhook
- Store the webhook secret in a secure place and provide it in Port integration settings (webhookSecret)

Security
--------
- Ocean validates HMAC-SHA256 signatures using `webhookSecret` configured in `spec.yaml` (client shared secret). Requests with invalid signatures return 401.
- Customers should create an IAM policy with least privilege (only put events to the SNS topic / EventBridge) and avoid embedding broad credentials.

Supported Resource Kinds & Event Mapping
---------------------------------------
| Kind | AWS Source | Event Names / Detail-Type |
|------|------------|---------------------------|
| AWS::EC2::Instance | EC2 (EventBridge state-change) | EC2 Instance State-change Notification (detail-type: "EC2 Instance State-change Notification") |
| AWS::ECS::Service | ECS (EventBridge) | ECS Deployment/Service events (ECS has event patterns) |
| AWS::Lambda::Function | Lambda (EventBridge) | Lambda Function State-change (Create, Update, Delete) |
| AWS::S3::Bucket | S3 via EventBridge (Object-level events or Bucket events) | ObjectCreated, ObjectRemoved, BucketCreated, BucketRemoved (limited coverage) |

Fallbacks & Limitations
-----------------------
- Not all S3 object-level events may be routed via EventBridge depending on bucket settings; the resync remains the fallback.
- Some services don't emit resource-level events for all mutations; in those cases we will fall back to initiating small resyncs for the specific account/region/kind.

Operational Notes
-----------------
- The webhook endpoint supports multi-account by including accountId and region in the event payload; handlers will lookup the right AWS session using the session factory and fetch full resource state via existing exporters.
- Handlers must be idempotent and handle duplicated events (SNS may deliver duplicates).
