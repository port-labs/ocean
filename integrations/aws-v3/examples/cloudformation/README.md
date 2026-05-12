# AWS-V3 live events CloudFormation

This directory contains the customer-side infrastructure templates required to forward AWS events into the AWS-V3 Ocean integration webhook.

## Templates

- `live-events-management-account.yml`: deploy once in the **management** account. Provisions:
  - EventBridge custom bus
  - SQS queue + DLQ
  - Rule from bus → SQS
  - Lambda forwarder (SQS trigger) that POSTs to the Ocean webhook with `X-Port-Signature: sha256=<hex>`
  - Secrets Manager secret holding the shared `webhookSecret`

- `live-events-member-account.yml`: deploy per **member** account (and per region, if using StackSets). Provisions:
  - EventBridge rule on the default bus matching the supported events
  - IAM role allowing EventBridge to `events:PutEvents` to the management bus ARN

## Deployment order (high level)

1. Configure `webhookSecret` in the Port integration (`integrations/aws-v3/.port/spec.yaml` exposes it).
2. Deploy the management account template and copy the `ManagementEventBusArn` output.
3. Deploy the member account template with `ManagementEventBusArn` set to the output from step 2.

For the full walkthrough, see `integrations/aws-v3/docs/live-events-setup.md`.

