# Self-hosted ECS (GovCloud)

Deploy the Port AWS v3 self-hosted ECS integration in AWS GovCloud.

The commercial installation docs rely on CloudFormation templates and container images hosted outside GovCloud. This script automates the GovCloud-specific steps that the standard docs cannot complete on their own.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure AWS credentials for your GovCloud account (profile or environment variables).
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Identify your VPC ID and subnet IDs (`subnet-xxxxxxxx`, not display names).
- [ ] Use **public subnets** with internet access (the template sets `AssignPublicIp: ENABLED`).
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials, VPC ID format, and subnet ID format.
2. [ ] **Mirrors the container image to ECR** - pulls `ghcr.io/port-labs/port-ocean-aws-v3:latest` as `linux/amd64`, creates the `port-ocean-aws-v3` ECR repository if needed, and pushes the image to GovCloud ECR.
3. [ ] **Downloads the CloudFormation template** - fetches the commercial ECS template from Port's S3 bucket.
4. [ ] **Transforms the template for GovCloud** - rewrites `arn:aws:` to `arn:aws-us-gov:`, adds a `ContainerImage` parameter, sets `AWS_PARTITION`, and fixes the Ocean event listener env vars.
5. [ ] **Caches the transformed template** - saves a copy under `~/.cache/port-aws-govcloud-setup/templates/`.
6. [ ] **Uploads the template to GovCloud S3** - creates the `port-cfn-templates-<account-id>-<region>` bucket if needed and uploads the template.
7. [ ] **Deploys the CloudFormation stack** - creates or updates `port-aws-ecs-integration` with your Port credentials, VPC, subnets, and image URI.
8. [ ] **Waits for the stack** - blocks until CloudFormation reports `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
9. [ ] **Verifies the ECS service** - confirms the `port-ocean-aws-v3` service has a running task.
10. [ ] **Triggers an initial Port resync** - calls the Port API (same as clicking **Resync** in the UI) so the first sync starts automatically.
11. [ ] **Prints stack outputs** - cluster name, read role ARN, log group name, and service name.

### What CloudFormation creates

- [ ] CloudWatch log group: `/ecs/port-aws-ecs-integration-port-ocean-aws-v3`.
- [ ] IAM execution role: `port-aws-ecs-integration-ExecutionRole`.
- [ ] IAM task role: `port-aws-ecs-integration-TaskRole`.
- [ ] IAM read-only role: `port-aws-ecs-integration-ReadRole` (with `ReadOnlyAccess`).
- [ ] ECS cluster: `port-aws-ecs-integration-cluster`.
- [ ] ECS Fargate service: `port-ocean-aws-v3`.
- [ ] Security group for outbound HTTPS from the task.

### After the script succeeds

- [ ] Check CloudWatch Logs at `/ecs/port-aws-ecs-integration-port-ocean-aws-v3` for sync activity.
- [ ] Open your Port catalog and confirm AWS resources are appearing (first sync may take a few minutes).
- [ ] In Port, verify the integration registered under your `INTEGRATION_IDENTIFIER` (default `my-aws-v3`).

### To tear down and start over

- [ ] Delete the CloudFormation stack: `port-aws-ecs-integration`.
- [ ] Empty and delete the S3 template bucket: `port-cfn-templates-<account-id>-<region>`.
- [ ] Delete the ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete the integration and synced entities in Port.
- [ ] Optionally remove the local cache: `~/.cache/port-aws-govcloud-setup`.

## Prerequisites

- Python 3.12+ with the integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS credentials for your GovCloud account.
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.
- Docker CLI (unless you set `SKIP_ECR_MIRROR = True` and provide `CONTAINER_IMAGE`).
- An existing VPC and subnets with outbound internet access.

## Usage

1. Open `run.py` and edit the configuration section at the top (`REGION`, `VPC_ID`, `SUBNET_IDS`, and so on).
2. Export your Port credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
```

3. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/self_hosted_ecs/run.py
```

## Configuration

All settings are defined as module-level variables at the top of `run.py`. Port credentials are read from environment variables only.

| Variable | Description |
|----------|-------------|
| `REGION` | GovCloud region (for example `us-gov-west-1`). |
| `AWS_PROFILE` | AWS CLI profile name, or `None` for default credentials. |
| `VPC_ID` | VPC where the ECS task runs. |
| `SUBNET_IDS` | Subnets for the ECS task (at least one; two recommended). |
| `SKIP_ECR_MIRROR` | Set to `True` to skip Docker pull/push if the image is already in ECR. |
| `CONTAINER_IMAGE` | ECR image URI when `SKIP_ECR_MIRROR` is `True`. |
| `UPDATE_STACK` | Set to `True` to update an existing CloudFormation stack. |
| `TRIGGER_PORT_RESYNC` | Set to `False` to skip the automatic Port API resync after deploy. |
| `PORT_RESYNC_WAIT_SECONDS` | Seconds to wait after ECS is healthy before triggering the resync (default `45`). |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `AccessDenied` during stack create | Your IAM principal needs permissions to create CloudFormation stacks, IAM roles, ECS resources, and CloudWatch Logs. |
| `ROLLBACK_COMPLETE` / stack create failed | Delete the failed stack, fix the error, and re-run. Common issues: invalid `SUBNET_IDS`, or a stale transformed template in S3 (re-run the full script to re-upload). |
| Invalid IAM managed policy ARN | The script only changes the partition (`arn:aws:` to `arn:aws-us-gov:`). AWS-managed policies keep the `aws` account ID in the ARN path. |
| `exec format error` in CloudWatch Logs | The ECR image was likely pushed for the wrong CPU architecture (common on Apple Silicon). Re-mirror with `docker pull --platform linux/amd64` and redeploy. The script does this automatically. |
| ECS task fails to start | Confirm the ECR image exists, is `linux/amd64`, and the execution role can pull from ECR. |
| Integration cannot reach Port | Verify outbound HTTPS from the task subnets and that `PORT_BASE_URL` is correct. |
| Container starts but no entities sync | The task needs `OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov`. Without it, Ocean calls the commercial Account API (`listRegions`) which fails in GovCloud. The script adds this to the template automatically. |
| Docker pull fails | Run from a host with internet access to GHCR, or mirror the image manually and set `SKIP_ECR_MIRROR = True`. |
| SSL certificate verification failed | The script uses the `certifi` CA bundle by default. If you are behind a corporate proxy, set `SSL_CA_BUNDLE` in the script or environment to your CA bundle path. As a last resort, set `VERIFY_SSL = False` in the script. |

See the [AWS v3 installation docs](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/aws-v3/installation/) for the standard self-hosted ECS flow this script replaces in GovCloud.
