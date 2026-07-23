# Self-hosted EKS IRSA (GovCloud)

Deploy the Port AWS v3 self-hosted EKS IRSA integration in AWS GovCloud.

This method has two phases: CloudFormation provisions EKS and IAM resources, then Helm deploys the Ocean chart into the cluster.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure AWS credentials for your GovCloud account (profile or environment variables).
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Ensure Docker is available (unless `SKIP_ECR_MIRROR = True`).
- [ ] Ensure `helm`, `kubectl`, and AWS CLI are installed.
- [ ] Identify at least two subnet IDs in EKS-supported availability zones.
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates configuration** - checks Port credentials and subnet ID format.
2. [ ] **Mirrors the container image to ECR** - pulls `ghcr.io/port-labs/port-ocean-aws-v3:latest` as `linux/amd64`, creates the ECR repository if needed, and pushes to GovCloud ECR.
3. [ ] **Downloads and transforms the EKS template** - applies GovCloud partition rewrite for `eks-irsa.yaml`.
4. [ ] **Uploads the transformed template to GovCloud S3** - creates the template bucket if needed.
5. [ ] **Deploys the EKS CloudFormation stack** - creates or updates `port-aws-eks-integration`.
6. [ ] **Verifies EKS health** - waits for cluster and node group readiness.
7. [ ] **Runs kubeconfig command** - executes `UpdateKubeconfigCommand` from stack outputs when available.
8. [ ] **Installs or upgrades Helm release** - deploys `port-ocean` with IRSA annotation, GovCloud partition, and ECR image.
9. [ ] **Waits for pod readiness** - blocks until Ocean pod is ready.
10. [ ] **Triggers an initial Port resync** - calls the Port API so the first sync starts automatically.

### What CloudFormation creates

- [ ] EKS cluster.
- [ ] Managed node group.
- [ ] OIDC provider for IRSA.
- [ ] Service account role for Ocean pod.
- [ ] Read role for AWS resource discovery.

### After the script succeeds

- [ ] Confirm node group and pod health in EKS and Kubernetes.
- [ ] Check Ocean pod logs in `port-ocean` namespace.
- [ ] Open your Port catalog and confirm AWS resources are appearing.

### To tear down and start over

- [ ] Uninstall Helm release: `helm uninstall aws-v3 -n port-ocean`.
- [ ] Delete CloudFormation stack: `port-aws-eks-integration`.
- [ ] Empty and delete the S3 template bucket: `port-cfn-templates-<account-id>-<region>`.
- [ ] Delete the ECR repository: `port-ocean-aws-v3`.
- [ ] Optionally delete the integration and synced entities in Port.

## Prerequisites

- Python 3.12+ with integration dependencies installed (`poetry install` from `integrations/aws-v3`).
- AWS credentials for your GovCloud account.
- `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET` environment variables.
- Docker CLI for image mirror flow.
- `helm`, `kubectl`, and AWS CLI for cluster deployment and chart installation.

## Usage

1. Open `run.py` and edit `SUBNET_IDS`, cluster settings, and ECR options.
2. Export your Port credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
```

3. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/self_hosted_eks/run.py
```

## Configuration

All settings are defined as module-level variables at the top of `run.py`.

| Variable | Description |
|----------|-------------|
| `SUBNET_IDS` | Two or more subnets for EKS in supported availability zones. |
| `DEPLOY_HELM` | Set to `False` to stop after CloudFormation and skip Helm deployment. |
| `HELM_CHART_VERSION` | Set to a chart version string to pin Helm; leave `None` to install latest. |
| `SKIP_ECR_MIRROR` | Set to `True` to skip Docker pull and push if image already exists in ECR. |
| `TRIGGER_PORT_RESYNC` | Set to `False` to skip automatic Port API resync. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| EKS stack deploy is slow | `CREATE_COMPLETE` can take 10 to 15 minutes, especially on first cluster creation. |
| `kubectl` fails after stack deployment | Re-run the `UpdateKubeconfigCommand` output and verify active AWS profile context. |
| Helm deploy fails | Ensure `helm repo add` and `helm repo update` succeed, and kubeconfig points to the new cluster. |
| Pod starts but no entities sync | Confirm Helm values include `integration.config.awsPartition=aws-us-gov`. |
