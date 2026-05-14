# aws-v3

An integration used to import AWS resources into Port.

Two ingestion paths run side-by-side:

| Path        | Mechanism                                                                        | Latency                       | When it runs                                           |
| ----------- | -------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------ |
| Resync      | Scheduled full crawl across accounts × regions × kinds.                          | minutes (depends on scope)    | On Ocean's resync schedule + manual trigger.           |
| Live events | EventBridge → central SNS topic → HTTPS webhook → `AbstractWebhookProcessor`.    | ~seconds                      | Whenever AWS emits a covered change.                   |

Resync remains the source of truth for full reconciliation. Live events keep
the catalog warm between full passes. See
[`docs/adr-live-events.md`](docs/adr-live-events.md) for the full
architecture, trade-off analysis, and supported resource matrix.

## Live events — quick setup

1. **Deploy the hub** (one stack, in the account & region you choose):

   ```bash
   aws cloudformation deploy \
     --stack-name port-aws-v3-live-events-hub \
     --template-file docs/cloudformation/live-events-hub.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       OceanWebhookUrl=https://<your-ocean>/integration/webhook \
       OrganizationId=o-xxxxxxxx
   ```

2. **Deploy the member rules** (as a StackSet across every account/region):

   ```bash
   aws cloudformation create-stack-set \
     --stack-set-name port-aws-v3-live-events-member \
     --template-body file://docs/cloudformation/live-events-member.yaml \
     --permission-model SERVICE_MANAGED \
     --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false \
     --parameters \
       ParameterKey=AwsLiveEventsTopicArn,ParameterValue=<topic-arn-from-step-1>
   ```

3. **Configure Ocean** — set `webhookSecret` in the integration config to
   enable the optional HMAC layer; otherwise SNS X.509 signature verification
   is the only auth required.

4. **Confirm subscription** — the integration auto-confirms the SNS HTTPS
   subscription on first delivery. Look for `outcome=subscription_confirmed`
   in the logs.

5. **Verify** — make an AWS change (e.g., start an EC2 instance). The
   corresponding Port entity should update within seconds; log line:
   `outcome=upserted kind=AWS::EC2::Instance ...`.

## Develop

```bash
cd integrations/aws-v3
poetry install
ocean sail
```

## Test

```bash
poetry run pytest tests/
```

All tests mock AWS and Port — no live calls.

### References

- [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/aws-v3/Overview)
- [Live Events ADR](docs/adr-live-events.md)
- [Adding a new kind](ADDING_NEW_KINDS.md)
- [Ocean integration development](https://ocean.getport.io/develop-an-integration/)
