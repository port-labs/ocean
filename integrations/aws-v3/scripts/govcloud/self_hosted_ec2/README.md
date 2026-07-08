# Self-hosted EC2 (GovCloud)

Deploy the Port AWS v3 self-hosted EC2 integration in AWS GovCloud.

The commercial installation docs rely on CloudFormation templates and container images hosted outside GovCloud. This script automates the GovCloud-specific steps for the EC2 installation method.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure AWS credentials for your GovCloud account (profile or environment variables).
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Identify your VPC ID and subnet ID (`subnet-xxxxxxxx`, not display names).
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials, VPC ID format, and subnet ID format.
2. [ ] **Mirrors the container image to ECR** - pulls `ghcr.io/port-labs/port-ocean-aws-v3:latest` as `linux/amd64`, creates the `port-ocean-aws-v3` ECR repository if needed, and pushes the image to GovCloud ECR.
3. [ ] **Downloads the CloudFormation template** - fetches the commercial EC2 template from Port's S3 bucket.
4. [ ] **Transforms the template for GovCloud** - rewrites `arn:aws:` to `arn:aws-us-gov:`, adds a `ContainerImage` parameter, injects `AWS_PARTITION`, and applies the event listener env var fixes.
5. [ ] **Caches the transformed template** - saves a copy under `~/.cache/port-aws-govcloud-setup/templates/`.
6. [ ] **Uploads the template to GovCloud S3** - creates the `port-cfn-templates-<account-id>-<region>` bucket if needed and uploads the template.
7. [ ] **Deploys the CloudFormation stack** - creates or updates `port-aws-ec2-integration` with your Port credentials, VPC, subnet, and image URI.
8. [ ] **Waits for the stack** - blocks until CloudFormation reports `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
9. [ ] **Verifies the EC2 instance** - waits for instance health checks to pass.
10. [ ] **Triggers an initial Port resync** - calls the Port API so the first sync starts automatically.
11. [ ] **Prints stack outputs** - instance ID, role ARN, and helper commands.

### What CloudFormation creates

- [ ] EC2 instance that runs the Ocean container.
- [ ] IAM instance profile and role for runtime permissions.
- [ ] IAM read-only role for AWS discovery.
- [ ] Security group for outbound HTTPS.
- [ ] CloudWatch logs integration wiring from template outputs.

### After the script succeeds

- [ ] Check the EC2 service status output and logs.
- [ ] Open your Port catalog and confirm AWS resources are appearing.
- [ ] In Port, verify the integration registered under your `INTEGRATION_IDENTIFIER`.

### To tear down and start over

- [ ] Delete the CloudFormation stack: `port-aws-ec2-integration`.
- [ ] Empty and delete the S3 template bucket: `port-cfn-templates-<account-id>-<region>`.
- [ ] Delete the ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete the integration and synced entities in Port.
- [ ] Optionally remove the local cache: `~/.cache/port-aws-govcloud-setup`.

## Prerequisites

- Python 3.12+ with the integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS credentials for your GovCloud account.
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.
- Docker CLI (unless you set `SKIP_ECR_MIRROR = True` and provide `CONTAINER_IMAGE`).
- An existing VPC and subnet with outbound internet access.

## Usage

1. Open `run.py` and edit the configuration section at the top (`REGION`, `VPC_ID`, `SUBNET_ID`, and related settings).
2. Export your Port credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
```

3. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/self_hosted_ec2/run.py
```

## Configuration

All settings are defined as module-level variables at the top of `run.py`. Port credentials are read from environment variables only.

| Variable | Description |
|----------|-------------|
| `REGION` | GovCloud region (for example `us-gov-west-1`). |
| `AWS_PROFILE` | AWS CLI profile name, or `None` for default credentials. |
| `VPC_ID` | VPC where the EC2 instance runs. |
| `SUBNET_ID` | Subnet where the EC2 instance runs. |
| `INSTANCE_TYPE` | EC2 instance type for the integration host. |
| `SKIP_ECR_MIRROR` | Set to `True` to skip Docker pull and push if the image is already in ECR. |
| `CONTAINER_IMAGE` | ECR image URI when `SKIP_ECR_MIRROR` is `True`. |
| `UPDATE_STACK` | Set to `True` to update an existing CloudFormation stack. |
| `TRIGGER_PORT_RESYNC` | Set to `False` to skip the automatic Port API resync after deploy. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `AccessDenied` during stack create | Your IAM principal needs permissions to create CloudFormation stacks, IAM roles, EC2 resources, and CloudWatch logs resources. |
| `ROLLBACK_COMPLETE` / stack create failed | Delete the failed stack, fix the error, and re-run. Common issues are invalid `SUBNET_ID` values or network routing. |
| `exec format error` | The ECR image was likely pushed for the wrong CPU architecture. Re-mirror as `linux/amd64`. |
| `Unable to find image` / `ImagePullBackOff` on EC2 | The GovCloud transform adds ECR pull IAM permissions and `docker login` in userdata. If you deployed before this fix, update the stack with `UPDATE_STACK = True` and replace the EC2 instance, or run ECR login manually on the host. |
| Instance starts but no entities sync | The container must include `OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov`. The script injects this in the transformed template. |
| Integration cannot reach Port | Verify outbound HTTPS from the subnet and confirm `PORT_BASE_URL` is correct. |
