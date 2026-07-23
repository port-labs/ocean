# GovCloud self-hosted setup scripts

Automation for the Port AWS v3 **self-hosted** installation methods in AWS GovCloud (`aws-us-gov`). Commercial docs use CloudFormation templates and container images hosted outside GovCloud; these scripts mirror images to GovCloud ECR, transform templates for the GovCloud partition, upload to GovCloud S3, deploy stacks, verify resources, and trigger an initial Port resync.

**Out of scope:** Hosted by Port (Port runs the integration; no customer infrastructure).

## Prerequisites

- Python 3.12+ with integration dependencies (`poetry install` from `integrations/aws-v3`).
- AWS credentials for the relevant GovCloud account(s).
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.
- Docker CLI (unless `SKIP_ECR_MIRROR = True` and the image is already in ECR).

## Installation methods

### Single-account

The integration runs in the same GovCloud account it syncs.

| Method | Script | Description |
|--------|--------|-------------|
| ECS | [self_hosted_ecs/run.py](self_hosted_ecs/run.py) | Fargate task running the Ocean container. |
| EC2 | [self_hosted_ec2/run.py](self_hosted_ec2/run.py) | EC2 instance with Docker and systemd. |
| EKS IRSA | [self_hosted_eks/run.py](self_hosted_eks/run.py) | EKS cluster + Helm chart (two phases). |
| IAM user | [self_hosted_iam_user/run.py](self_hosted_iam_user/run.py) | Docker run with access keys (no CloudFormation). |

### Multi-account

Organizations setup: read roles in management and member accounts; integration runs in a dedicated account.

| Method | Script | Phases |
|--------|--------|--------|
| ECS | [multi_account_ecs/run.py](multi_account_ecs/run.py) | IAM roles StackSet, then ECS. |
| EC2 | [multi_account_ec2/run.py](multi_account_ec2/run.py) | IAM roles StackSet, then EC2. |
| EKS IRSA | [multi_account_eks/run.py](multi_account_eks/run.py) | EKS cluster, IRSA StackSet, then Helm. |

## Shared pipeline (CloudFormation methods)

1. Mirror `ghcr.io/port-labs/port-ocean-aws-v3:latest` to GovCloud ECR (`linux/amd64`).
2. Download the commercial template from Port's S3 bucket.
3. Transform `arn:aws:` to `arn:aws-us-gov:` and apply method-specific fixes (container image, `AWS_PARTITION`, event listener).
4. Upload the transformed template to GovCloud S3.
5. Create or update the CloudFormation stack.
6. Verify ECS/EC2/EKS resources (and Helm pod for EKS).
7. Trigger a Port API resync.

Template transforms live in [utils/templates.py](utils/templates.py). General helpers live in [../utils/](../utils/).

## Configuration

Each `run.py` has a configuration block at the top. Edit region, profiles, VPC/subnet IDs, stack names, and Port settings before running:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
poetry run python scripts/govcloud/<method>/run.py
```

See the README in each method directory for method-specific parameters.

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `listRegions` / commercial Account API errors | Container or pod needs `OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov`. Scripts add this automatically for ECS/EC2/Helm. |
| `exec format error` | Re-mirror the image as `linux/amd64` (scripts do this by default). |
| Invalid subnet ID | Use `subnet-xxxxxxxx` IDs, not console display names. |
| Multi-account StackSet failures | Confirm `StackSetTemplateURL` points to your integration-account S3 upload (scripts handle this). Management account does not need its own template bucket. |
| EKS Helm deploy fails | Run `UpdateKubeconfigCommand` from stack outputs; ensure `helm` and `kubectl` are installed. |

See the [AWS v3 installation docs](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/aws-v3/installation/) for the standard commercial flows these scripts adapt for GovCloud.
