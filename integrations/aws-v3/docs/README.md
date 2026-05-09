```markdown
# aws-v3 integration — Live Events docs

This folder contains documentation for the aws-v3 integration live events support.

- `adr-live-events.md` — Architecture Decision Record describing candidate architectures and the chosen approach (EventBridge -> SNS -> Ocean).
- `live-events-setup.md` — Quick start guide and minimal steps to wire EventBridge/SNS to Ocean.
- `../templates/live-events.yaml` — Example CloudFormation template showing EventBridge -> SNS -> HTTPS subscription.

Follow `live-events-setup.md` for the minimal steps to configure your AWS accounts and the Ocean integration.

``` 
