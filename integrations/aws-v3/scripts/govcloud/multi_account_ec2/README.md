# Multi-account EC2 (GovCloud)

Deploy the Port AWS v3 multi-account self-hosted EC2 integration in AWS GovCloud.

This method uses the same management-account IAM roles rollout as multi-account ECS, then deploys an EC2-based integration host in the integration account.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure both AWS profiles (`MANAGEMENT_AWS_PROFILE` and `INTEGRATION_AWS_PROFILE`) or equivalent credentials.
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Set `TARGET_OU_IDS`, `INTEGRATION_ACCOUNT_ID`, `TRUSTED_ROLE_NAME`, `VPC_ID`, and `SUBNET_ID`.
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials, VPC ID, and subnet ID format.
2. [ ] **Mirrors container image to integration ECR** - prepares GovCloud `linux/amd64` image URI.
3. [ ] **Transforms and uploads StackSet template** - uploads `stackset/iam-roles.yaml` into GovCloud S3.
4. [ ] **Transforms and uploads IAM roles template** - injects GovCloud StackSet URL into `iam-roles.yaml`.
5. [ ] **Deploys management stack** - creates or updates `port-ocean-iam-roles` and captures `ManagementAccountRoleArn`.
6. [ ] **Transforms and uploads integration EC2 template** - injects GovCloud partition and container image settings.
7. [ ] **Deploys integration EC2 stack** - creates or updates `port-aws-ec2-integration` with `AccountRoleArn`.
8. [ ] **Verifies EC2 instance health** - waits for instance checks to pass.
9. [ ] **Triggers an initial Port resync** - calls the Port API so first sync starts automatically.

### What CloudFormation creates

- [ ] Management account IAM role and StackSet for member account read roles.
- [ ] Integration account EC2 instance and instance profile.
- [ ] Integration account IAM read role linkage to management role output.
- [ ] Security group and log integration resources.

### After the script succeeds

- [ ] Confirm management stack and StackSet operation succeeded.
- [ ] Confirm EC2 instance passed status checks.
- [ ] Open your Port catalog and confirm resources from member accounts appear.

### To tear down and start over

- [ ] Delete integration EC2 stack: `port-aws-ec2-integration`.
- [ ] Delete management IAM roles stack: `port-ocean-iam-roles`.
- [ ] Delete the integration-account template bucket: `port-cfn-templates-<integration-account-id>-<region>`.
- [ ] Delete integration ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete integration and synced entities in Port.

## Prerequisites

- Python 3.12+ with integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS permissions in management account for IAM roles and StackSets.
- AWS permissions in integration account for EC2, CloudFormation, S3, and ECR.
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.

## Usage

1. Open `run.py` and configure account profiles, OU scope, and network settings.
2. Export your Port credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
```

3. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/multi_account_ec2/run.py
```

## Configuration

All settings are defined as module-level variables at the top of `run.py`.

| Variable | Description |
|----------|-------------|
| `MANAGEMENT_AWS_PROFILE` | AWS profile for management account IAM and StackSet deployment. |
| `INTEGRATION_AWS_PROFILE` | AWS profile for integration account EC2 deployment. |
| `TARGET_OU_IDS` | OU or root IDs targeted by StackSet role rollout. |
| `INTEGRATION_ACCOUNT_ID` | GovCloud account ID where EC2 integration runs. |
| `TRUSTED_ROLE_NAME` | Must match EC2 instance role name, usually `port-aws-ec2-integration-InstanceRole`. |
| `VPC_ID` | VPC where EC2 integration instance runs. |
| `SUBNET_ID` | Subnet where EC2 integration instance runs. |
| `ORGANIZATION_ID` | AWS Organizations ID (`o-...`). Leave `None` to resolve from the management account. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `You must enable organizations access to operate a service managed stack set` | Run from the **management** account: `aws cloudformation activate-organizations-access --region <region> --profile <management-profile>`. The script also enables this automatically before StackSet deployment. |
| StackSet operation fails | Confirm OU IDs are valid, management account has Organizations plus StackSet permissions, and integration bucket policy allows management and member CloudFormation access. |
| Integration stack cannot assume role | Confirm `TRUSTED_ROLE_NAME` matches integration instance role name exactly. |
| EC2 instance unhealthy | Verify subnet route table, security group egress, and image architecture. |
| Member account resources missing in Port | Confirm StackSet finished in member accounts and `ManagementAccountRoleArn` was passed as `AccountRoleArn`. |
