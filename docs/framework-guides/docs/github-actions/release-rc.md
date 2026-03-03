---
title: Release RC Workflow
sidebar_label: Release RC
sidebar_position: 1
---

# Release RC Workflow

The Release RC (Release Candidate) workflow is a GitHub Actions workflow that creates and publishes release candidate versions of the Ocean framework and its integrations.

## Overview

This workflow automates the process of:
- Creating RC versions of the core Ocean framework
- Publishing RC packages to PyPI
- Building and pushing RC Docker images for integrations
- Creating GitHub releases marked as pre-releases
- Tagging the source branch with the RC version

## Access Requirements

This workflow can only be triggered manually by users with **write access** to the repository (maintainers and administrators). This restriction exists because the workflow:

- Publishes packages to PyPI using repository secrets
- Pushes Docker images to GitHub Container Registry
- Creates Git tags and GitHub releases
- Modifies the repository's release history

If you need to create an RC release and don't have the required permissions, please contact a repository maintainer.

## When to Use

Use this workflow when you want to:
- Test new features before a stable release
- Validate changes in a production-like environment
- Share pre-release versions with beta testers
- Perform integration testing with specific versions

## Workflow Inputs

The workflow accepts the following inputs:

### `source_branch`
- **Description**: Source branch containing core changes (defaults to the branch workflow is run from)
- **Required**: No
- **Type**: String
- **Default**: Current branch

### `rc_number`
- **Description**: RC number (e.g., 1 for -rc1, 2 for -rc2)
- **Required**: Yes
- **Type**: Number
- **Default**: 1

### `dry_run`
- **Description**: Dry run - validate and build without publishing
- **Required**: No
- **Type**: Boolean
- **Default**: false

### `integration_filter`
- **Description**: Build specific integration(s) only (comma-separated, e.g., "aws,github"). Leave empty for all.
- **Required**: No
- **Type**: String
- **Default**: Empty (all integrations)

## How It Works

The workflow consists of several jobs that run in sequence:

### 1. Validate Inputs
- Checks out the source branch
- Validates the RC number format (must be a positive integer)
- Reads the base version from `pyproject.toml`
- Validates the version format (must be X.Y.Z)
- Constructs the full RC version (e.g., `0.38.4-rc1`)
- Checks if the tag already exists

### 2. Publish Core RC
- Sets up Python 3.12
- Checks if the package already exists on PyPI (skips if it does)
- Updates `pyproject.toml` with the RC version
- Builds the package using `make install && make build`
- Publishes to PyPI (unless dry run mode is enabled)
- Waits for the package to be available on PyPI (up to 5 minutes)

### 3. Tag Source Branch
- Creates an annotated Git tag for the RC version (e.g., `v0.38.4-rc1`)
- Pushes the tag to the remote repository
- Creates a GitHub Release marked as a pre-release
- Generates release notes automatically

### 4. Prepare Matrix
- Scans the `integrations/` directory for all integrations
- Filters integrations based on the `integration_filter` input (if provided)
- Skips the `fake-integration` test integration
- Prepares a matrix of integrations to build

### 5. Build RC Integrations
- Runs in parallel (max 5 concurrent builds)
- For each integration:
  - Updates `pyproject.toml` to use the exact RC version of port-ocean
  - Updates the integration's own version to the RC version
  - Regenerates `poetry.lock` with the RC core dependency
  - Builds a multi-platform Docker image (linux/amd64, linux/arm64)
  - Tags the image as `ghcr.io/port-labs/port-ocean-{integration}:rc-{version}`
  - Pushes to GitHub Container Registry

### 6. Summary
- Generates a summary of the release process
- Displays the version, source branch, and integration filter
- Shows the status of all jobs
- Lists published artifacts with installation commands

## Usage Examples

### Creating a Basic RC Release

To create the first release candidate from the main branch:

1. Go to **Actions** → **Release RC** in the GitHub repository
2. Click **Run workflow**
3. Set `rc_number` to `1`
4. Leave other inputs as default
5. Click **Run workflow**

This will create version `X.Y.Z-rc1` based on the version in `pyproject.toml`.

### Creating a Subsequent RC

To create a second release candidate with fixes:

1. Go to **Actions** → **Release RC**
2. Click **Run workflow**
3. Set `rc_number` to `2`
4. Click **Run workflow**

This will create version `X.Y.Z-rc2`.

### Testing a Specific Branch

To create an RC from a feature branch:

1. Go to **Actions** → **Release RC**
2. Click **Run workflow**
3. Set `source_branch` to your branch name (e.g., `feature/new-feature`)
4. Set `rc_number` to `1`
5. Click **Run workflow**

### Building Specific Integrations Only

To build only AWS and GitHub integrations:

1. Go to **Actions** → **Release RC**
2. Click **Run workflow**
3. Set `integration_filter` to `aws,github`
4. Set `rc_number` to `1`
5. Click **Run workflow**

### Dry Run (Validation Only)

To validate the release process without publishing:

1. Go to **Actions** → **Release RC**
2. Click **Run workflow**
3. Set `dry_run` to `true`
4. Set `rc_number` to `1`
5. Click **Run workflow**

This will build everything but skip PyPI publishing, Docker pushing, and tag creation.

## Version Format

The RC version follows this format:
```
{base_version}-rc{rc_number}
```

For example:
- Base version in `pyproject.toml`: `0.38.4`
- RC number: `1`
- Final RC version: `0.38.4-rc1`

## Installing RC Versions

### Python Package

Install the RC version of the Ocean framework:

```bash
pip install port-ocean==0.38.4-rc1
```

### Docker Images

Use the RC version of an integration:

```bash
docker pull ghcr.io/port-labs/port-ocean-aws:rc-0.38.4-rc1
```

## Important Notes

### Idempotency

The workflow is designed to be idempotent:
- If the PyPI package already exists, it skips publishing
- If the Git tag already exists, it skips tag creation
- You can safely re-run the workflow if it fails partway through

### Build Parallelization

Integration builds run in parallel with a maximum of 5 concurrent builds to optimize CI time while respecting resource limits.

### Multi-Platform Support

All Docker images are built for multiple platforms:
- `linux/amd64` (Intel/AMD processors)
- `linux/arm64` (ARM processors, including Apple Silicon)

### Pre-release Status

RC releases are marked as pre-releases on GitHub, making them easily distinguishable from stable releases.

## Troubleshooting

### Package Not Available on PyPI

If the workflow reports that the package isn't available after publishing:
- The workflow waits up to 5 minutes for PyPI to propagate
- If it times out, check PyPI manually to see if it's available
- You can safely re-run the workflow (it will skip publishing if already exists)

### Integration Build Failures

If specific integrations fail to build:
- Check the build logs for that specific integration
- Common issues include:
  - Missing dependencies in `pyproject.toml`
  - Docker build errors
  - Poetry lock conflicts

### Tag Already Exists

If you see a warning about an existing tag:
- This is normal if re-running the workflow
- The workflow will skip tag creation but continue with other jobs
- To create a new RC, increment the `rc_number`

## Related Workflows

- **Release Framework** (`.github/workflows/release-framework.yml`): Creates stable framework releases
- **Release Integrations** (`.github/workflows/release-integrations.yml`): Creates stable integration releases
- **Apply Release** (`.github/workflows/apply-release.yml`): Applies version updates across integrations

## Workflow File

The workflow is defined in `.github/workflows/release-rc.yml`.
