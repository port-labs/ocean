# Multi-account EKS IRSA (GovCloud)

Deploy the Port AWS v3 multi-account self-hosted EKS IRSA integration in AWS GovCloud.

This method has three phases:

1. Integration account EKS stack deployment.
2. Management account IRSA role rollout with StackSet.
3. Helm deployment on the EKS cluster.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure both AWS profiles (`MANAGEMENT_AWS_PROFILE` and `INTEGRATION_AWS_PROFILE`) or equivalent credentials.
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Ensure `helm`, `kubectl`, and AWS CLI are installed.
- [ ] Set `TARGET_OU_IDS` and `SUBNET_IDS` (at least two EKS-supported AZs).
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials and subnet ID format.
2. [ ] **Mirrors container image to integration ECR** - prepares GovCloud `linux/amd64` image URI.
3. [ ] **Transforms and uploads integration EKS template** - uploads GovCloud `eks-irsa.yaml` to integration S3 bucket.
4. [ ] **Deploys integration EKS stack** - creates or updates `port-aws-eks-integration`, verifies EKS health, and captures `OidcProviderUrl` plus `ServiceAccountRoleArn`.
5. [ ] **Transforms and uploads management StackSet template** - uploads GovCloud `stackset/irsa.yaml` to management S3 bucket.
6. [ ] **Transforms and uploads management IRSA template** - injects GovCloud StackSet URL into `irsa.yaml`.
7. [ ] **Deploys management IRSA stack** - creates or updates `port-ocean-irsa` and captures `ManagementAccountRoleArn`.
8. [ ] **Runs kubeconfig command** - executes `UpdateKubeconfigCommand` from integration stack outputs when available.
9. [ ] **Installs or upgrades Helm release** - deploys `port-ocean` with IRSA annotation, GovCloud partition, ECR image, and `accountRoleArn`.
10. [ ] **Waits for pod readiness** - blocks until Ocean pod is ready.
11. [ ] **Triggers an initial Port resync** - calls the Port API so first sync starts automatically.

### What CloudFormation creates

- [ ] Integration account EKS cluster, node group, OIDC provider, and service account role.
- [ ] Management account read role and StackSet rollout to member accounts for IRSA trust.
- [ ] Member account OIDC provider and read role resources created by StackSet.

### After the script succeeds

- [ ] Confirm EKS cluster and node group are active in integration account.
- [ ] Confirm IRSA stack and StackSet operations are complete in management account.
- [ ] Confirm Ocean pod is ready in `port-ocean` namespace.
- [ ] Open your Port catalog and confirm resources from member accounts appear.

### To tear down and start over

- [ ] Uninstall Helm release: `helm uninstall aws-v3 -n port-ocean`.
- [ ] Delete integration EKS stack: `port-aws-eks-integration`.
- [ ] Delete management IRSA stack: `port-ocean-irsa`.
- [ ] Delete the integration-account template bucket: `port-cfn-templates-<integration-account-id>-<region>`.
- [ ] Delete integration ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete integration and synced entities in Port.

## Prerequisites

- Python 3.12+ with integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS permissions in management account for IAM roles, StackSets, and Organizations.
- AWS permissions in integration account for EKS, CloudFormation, S3, and ECR.
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.
- `helm`, `kubectl`, and AWS CLI.

## Usage

1. Open `run.py` and configure profile, OU, subnet, and cluster settings.
2. Export your Port credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
```

3. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/multi_account_eks/run.py
```

`TRUSTED_ROLE_NAME` is not used for EKS IRSA. The management stack trusts the integration account EKS OIDC issuer instead.

## Configuration

All settings are defined as module-level variables at the top of `run.py`.

| Variable | Description |
|----------|-------------|
| `MANAGEMENT_AWS_PROFILE` | AWS profile for management account IRSA stack and StackSet deployment. |
| `INTEGRATION_AWS_PROFILE` | AWS profile for integration account EKS and Helm phases. |
| `SUBNET_IDS` | Two or more subnets for EKS in supported availability zones. |
| `TARGET_OU_IDS` | OU or root IDs targeted by StackSet role rollout. |
| `DEPLOY_HELM` | Set to `False` to stop after CloudFormation and skip Helm deployment. |
| `HELM_CHART_VERSION` | Set to a chart version string to pin Helm; leave `None` to install latest. |
| `ORGANIZATION_ID` | AWS Organizations ID (`o-...`). Leave `None` to resolve from the management account. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `You must enable organizations access to operate a service managed stack set` | Run from the **management** account: `aws cloudformation activate-organizations-access --region <region> --profile <management-profile>`. The script also enables this automatically before StackSet deployment. |
| `OIDCIssuerURL` errors in management stack | Ensure the script receives `OidcProviderUrl` from integration stack outputs and strips `https://`. |
| StackSet rollout fails in member accounts | Confirm OU IDs, Organizations permissions, and integration bucket policy for cross-account template access. |
| Helm deploy fails | Ensure kubeconfig points to the integration account cluster and `helm repo update` succeeds. |
| Member account resources missing in Port | Confirm `ManagementAccountRoleArn` was set in Helm values as `accountRoleArn` and StackSet completed. |
