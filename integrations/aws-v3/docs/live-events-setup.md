```markdown
# AWS-V3 Integration — Live Events (Quick Setup)

This document shows the minimum steps to wire AWS EventBridge/SNS to Ocean for near real-time updates.

1) Create an SNS topic and an HTTPS subscription to your Ocean webhook endpoint:

   - Endpoint: https://<OCEAN_BASE>/integration/webhook
   - Use raw message delivery = false (default) so the SNS envelope is sent as JSON.

2) Create an EventBridge rule to forward relevant events to the SNS topic.

   Example EventPattern for EC2 state changes:

   ```json
   {
     "source": ["aws.ec2"],
     "detail-type": ["EC2 Instance State-change Notification"]
   }
   ```

3) Configure the `webhookSecret` in the aws-v3 integration settings in Ocean. This secret is used to compute an HMAC-SHA256 signature over the canonical JSON body of the inner EventBridge message. Ocean verifies the signature and rejects messages with invalid signatures.

4) Confirm subscription in SNS (SNS will POST a SubscriptionConfirmation message; Ocean expects to receive it and will accept it — ensure your webhook endpoint is reachable during setup).

5) (Optional) Use EventBridge API Destinations for signed HTTPS delivery instead of SNS if you prefer direct EventBridge delivery.

Notes
-----
- The integration supports EC2 instances, ECS services, Lambda functions, and S3 buckets.
- The integration will use the configured AWS account/region information in the event to fetch the current resource state using the existing exporters.
- The integration provides in-process deduplication for SNS MessageId. For multi-instance deployments you should provision a durable dedupe store (Redis, DynamoDB) if you expect duplicate suppression across processes.

See `adr-live-events.md` for the architecture decision record and `../templates/live-events.yaml` for an example CloudFormation template.

``` 
