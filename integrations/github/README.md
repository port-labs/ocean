# github

An integration used to import github resources into Port.

## Features

- **Incremental Sync** - Efficiently sync only changed resources using cursor-based filtering
  - Repositories: Client-side cutoff strategy with `updated_at` filtering
  - Workflows: Per-repo commit-path filtering to detect `.github/workflows` changes
  - Alerts (Secret Scanning, Dependabot, Code Scanning): Server-side timestamp filtering
- **Comprehensive Resource Sync** - Pull requests, issues, workflows, repositories, and more
- **Flexible Configuration** - Search filters, repository selection, and relationship enrichment

## How Workflow Incremental Sync Works

The workflow incremental sync uses an efficient two-step approach:
1. **Pre-filtering**: Check each repository for commits touching `.github/workflows` since the cursor
   - Uses `GET /repos/{owner}/{repo}/commits?path=.github/workflows&since={cursor}`
   - Only includes repositories with actual changes
2. **Fetch**: Fetch and sync workflows only from changed repositories
   - Uses `GET /repos/{owner}/{repo}/actions/workflows`
   - Full pagination to ensure all workflows are synced

This approach reduces API calls by skipping repositories with no workflow changes.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)