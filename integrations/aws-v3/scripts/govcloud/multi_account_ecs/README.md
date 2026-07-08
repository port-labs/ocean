# Multi-account ECS (GovCloud)

Deploy the Port AWS v3 multi-account self-hosted ECS integration in AWS GovCloud.

This method has two account contexts:

- Management account for IAM role rollout and StackSet operation.
- Integration account for ECS task deployment.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure both AWS profiles (`MANAGEMENT_AWS_PROFILE` and `INTEGRATION_AWS_PROFILE`) or equivalent credentials.
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Set `TARGET_OU_IDS`, `INTEGRATION_ACCOUNT_ID`, `TRUSTED_ROLE_NAME`, `VPC_ID`, and `SUBNET_IDS`.
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials, VPC ID, and subnet ID formats.
2. [ ] **Mirrors container image to integration ECR** - prepares GovCloud `linux/amd64` image URI.
3. [ ] **Transforms and uploads StackSet template** - uploads `stackset/iam-roles.yaml` into GovCloud S3.
4. [ ] **Transforms and uploads IAM roles template** - injects GovCloud StackSet URL into `iam-roles.yaml`.
5. [ ] **Deploys management stack** - creates or updates `port-ocean-iam-roles` and captures `ManagementAccountRoleArn`.
6. [ ] **Transforms and uploads integration ECS template** - injects GovCloud partition and container image settings.
7. [ ] **Deploys integration ECS stack** - creates or updates `port-aws-ecs-integration` with `AccountRoleArn`.
8. [ ] **Verifies ECS service** - waits for desired running task count.
9. [ ] **Triggers an initial Port resync** - calls the Port API so first sync starts automatically.

### What CloudFormation creates

- [ ] Management account IAM role and StackSet for member account read roles.
- [ ] Integration account ECS cluster and service.
- [ ] Integration account ECS task and execution roles.
- [ ] Log group and networking resources for ECS runtime.

### After the script succeeds

- [ ] Confirm management stack and StackSet operation succeeded.
- [ ] Confirm ECS service is healthy in integration account.
- [ ] Open your Port catalog and confirm resources from member accounts appear.

### To tear down and start over

- [ ] Delete integration ECS stack: `port-aws-ecs-integration`.
- [ ] Delete management IAM roles stack: `port-ocean-iam-roles`.
- [ ] Delete template bucket objects in both accounts.
- [ ] Delete integration ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete integration and synced entities in Port.

## Prerequisites

- Python 3.12+ with integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS permissions in management account for IAM roles and StackSets.
- AWS permissions in integration account for ECS, CloudFormation, S3, and ECR.
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
poetry run python scripts/govcloud/multi_account_ecs/run.py
```

## Configuration

All settings are defined as module-level variables at the top of `run.py`.

| Variable | Description |
|----------|-------------|
| `MANAGEMENT_AWS_PROFILE` | AWS profile for management account IAM and StackSet deployment. |
| `INTEGRATION_AWS_PROFILE` | AWS profile for integration account ECS deployment. |
| `TARGET_OU_IDS` | OU or root IDs targeted by StackSet role rollout. |
| `INTEGRATION_ACCOUNT_ID` | GovCloud account ID where ECS integration runs. |
| `TRUSTED_ROLE_NAME` | Integration role trusted by member account read roles. |
| `STACKSET_NAME` | Name for StackSet resource in management account. |
| `UPDATE_STACK` | Set to `True` to update existing stacks. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| StackSet operation fails | Confirm OU IDs are valid and management account has Organizations plus StackSet permissions. |
| Integration stack cannot assume role | Confirm `TRUSTED_ROLE_NAME` matches the integration task role name exactly. |
| ECS service unhealthy | Verify subnet routing, image URI, and task role permissions in integration account. |
| Member account resources missing in Port | Confirm StackSet finished in member accounts and `ManagementAccountRoleArn` was passed as `AccountRoleArn`. |
