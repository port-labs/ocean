# Self-hosted IAM user (GovCloud)

Run the Port AWS v3 integration with IAM user access keys and a GovCloud ECR image.

This method does not use CloudFormation. The script focuses on image mirroring and generating a GovCloud-correct `docker run` command.

## Checklist

### Before you run

- [ ] Install dependencies: `poetry install` from `integrations/aws-v3`.
- [ ] Configure AWS credentials for your GovCloud account (profile or environment variables).
- [ ] Export `PORT_CLIENT_ID` and `PORT_CLIENT_SECRET`.
- [ ] Export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for the IAM user used by Ocean.
- [ ] Ensure Docker is available on the host where you run the container.
- [ ] Edit the configuration section at the top of `run.py`.

### What the script does

1. [ ] **Validates credentials** - checks required Port and AWS access key environment variables.
2. [ ] **Mirrors the container image to ECR** - pulls `ghcr.io/port-labs/port-ocean-aws-v3:latest` as `linux/amd64`, creates `port-ocean-aws-v3` ECR repository if needed, and pushes to GovCloud ECR.
3. [ ] **Builds a Docker command** - includes Port credentials, AWS access keys, and `OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov`.
4. [ ] **Runs or prints the command** - executes `docker run` when `RUN_DOCKER = True`, or prints it for manual execution.
5. [ ] **Optionally triggers Port resync** - calls Port API when enabled in configuration.

### What this method creates

- [ ] GovCloud ECR repository and mirrored image (when mirroring is enabled).
- [ ] Docker container command with GovCloud partition and IAM access key settings.

### After the script succeeds

- [ ] Verify the container is running with `docker ps`.
- [ ] Check integration logs with `docker logs`.
- [ ] Open your Port catalog and confirm AWS resources are appearing.

### To tear down and start over

- [ ] Stop and remove the container.
- [ ] Delete the ECR repository: `port-ocean-aws-v3` (optional).
- [ ] Optionally delete the integration and synced entities in Port.

## Prerequisites

- IAM user with `ReadOnlyAccess` and access keys.
- Docker installed on the host running the container.
- `PORT_CLIENT_ID`, `PORT_CLIENT_SECRET`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` environment variables.

## Usage

1. Export required credentials:

```bash showLineNumbers
export PORT_CLIENT_ID="your-client-id"
export PORT_CLIENT_SECRET="your-client-secret"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

2. Run the script from the `integrations/aws-v3` directory:

```bash showLineNumbers
poetry run python scripts/govcloud/self_hosted_iam_user/run.py
```

By default, the script prints the generated `docker run` command. Set `RUN_DOCKER = True` in `run.py` to execute it directly.

## Configuration

All settings are defined as module-level variables at the top of `run.py`.

| Variable | Description |
|----------|-------------|
| `AWS_PROFILE` | AWS CLI profile name used for ECR operations, or `None` for default credentials. |
| `SKIP_ECR_MIRROR` | Set to `True` to skip Docker pull and push if the image is already in ECR. |
| `CONTAINER_IMAGE` | ECR image URI when `SKIP_ECR_MIRROR` is `True`. |
| `RUN_DOCKER` | Set to `True` to execute `docker run` from the script. |
| `EVENT_LISTENER_TYPE` | Controls polling mode such as `POLLING` or `ONCE`. |
| `TRIGGER_PORT_RESYNC` | Set to `False` to skip the automatic Port API resync. |

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Docker authentication fails for ECR | Re-run `aws ecr get-login-password` for your GovCloud account and region. |
| Container starts but no entities sync | Confirm `OCEAN__INTEGRATION__CONFIG__AWS_PARTITION=aws-us-gov` is present in the generated command. |
| Access key errors in logs | Confirm `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are exported in the shell where the container runs. |
| Integration cannot reach Port | Verify outbound HTTPS and confirm `PORT_BASE_URL` is correct. |
