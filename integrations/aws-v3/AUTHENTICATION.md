# AWS Integration Authentication Guide

This document explains how the AWS v3 integration authenticates to AWS, which scenarios are supported, what permissions are needed, and how to troubleshoot failures.

---

## How It Works — The Big Picture

At startup, the integration makes **two independent decisions**:

1. **Credential Provider** — how does the integration prove its identity to AWS?
2. **Account Strategy** — how many AWS accounts does it connect to, and how does it find them?

These are selected automatically based on your configuration and environment. The selected combination runs a health check before any data is synced.

---

## Part 1: Credential Providers

A credential provider is responsible for getting valid AWS credentials. The integration picks one automatically in this priority order:

### 1. Web Identity Provider (highest priority)
**Triggered by:** `AWS_WEB_IDENTITY_TOKEN_FILE` environment variable being set.

Used in **Kubernetes with IRSA** (IAM Roles for Service Accounts), GitHub Actions OIDC, or any environment where a short-lived JWT token is provided as a file. The integration reads the token from that file and exchanges it with AWS STS for temporary credentials. The token file is re-read on every refresh, so token rotation works transparently.

**If this fails, check:**
- The file path in `AWS_WEB_IDENTITY_TOKEN_FILE` actually exists and is readable.
- The token inside the file is not empty.
- An OIDC provider is configured in IAM that trusts the token issuer.
- The role's trust policy allows `sts:AssumeRoleWithWebIdentity` from that OIDC provider.

---

### 2. Static Credential Provider
**Triggered by:** `aws_access_key_id` + `aws_secret_access_key` set in the integration config.

Uses a fixed IAM user key pair. Simple and explicit, but **not auto-refreshing** — if the keys are rotated or expire, the integration breaks until the config is updated.

**If this fails, check:**
- The keys are correct and belong to an active IAM user.
- The IAM user's permissions are sufficient.
- `aws_session_token` is also set if you're using short-lived session credentials.

---

### 3. Default Credential Chain (fallback)
**Triggered by:** No web identity token file, no static keys in config.

boto3 (the AWS SDK) searches for credentials automatically in this order, stopping at the first one it finds:

| Priority | Source | How it works |
|---|---|---|
| 1 | Environment variables | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (optionally `AWS_SESSION_TOKEN`) |
| 2 | `~/.aws/credentials` file | Created when you run `aws configure` on the host |
| 3 | `~/.aws/config` file | Similar; used by some tools like aws-vault |
| 4 | IAM Instance Profile | If running on an EC2 instance with a role attached — credentials are injected automatically |
| 5 | ECS Task Role | If running in an ECS container with a task role — credentials are injected automatically |

Think of it as "boto3 tries to answer the question: who am I on this machine?"

**If this fails, check:**
- The environment the integration is running in actually has one of the above.
- The instance/task role (if applicable) has the necessary IAM permissions.
- There's no conflicting or stale credential source earlier in the chain.

---

## Part 2: Account Strategies

An account strategy decides **how many accounts** the integration connects to and **how it gets a session for each one**.

> **Important:** Regardless of which strategy is used, it is always the **base identity** (resolved by the credential provider above) that performs all `sts:AssumeRole` calls — including into member accounts. The management account role (in the Organizations strategy) is only used to call the Organizations API.

---

### Single Account Strategy
**Triggered by:** Neither `accountRoleArn` nor `accountRoleArns` set in config.

The integration uses the base identity directly. It calls `sts:GetCallerIdentity` to confirm it has valid credentials and to discover its account ID, then scans that single account.

```
[Base Identity]
       ↓ sts:GetCallerIdentity (health check)
[Scans resources in the same account]
```

**Required permissions on the base identity:**
- `sts:GetCallerIdentity`
- Read permissions for each resource type you want to sync (see [Resource Permissions](#resource-permissions))

**If this fails:**
- The base identity has no valid credentials (see credential provider chain above).
- `sts:GetCallerIdentity` is blocked by an SCP (rare).

---

### Multi-Account Strategy
**Triggered by:** `accountRoleArns` (a list) set in config.

You explicitly provide a list of role ARNs — one per account you want to access. The integration assumes each role concurrently (up to 10 at a time) and skips any that fail. It only fails entirely if **zero** roles can be assumed.

```
[Base Identity]
       ↓ sts:AssumeRole → [Role in Account A]
       ↓ sts:AssumeRole → [Role in Account B]
       ↓ sts:AssumeRole → [Role in Account C]
```

**Required permissions on the base identity:**
- `sts:AssumeRole` on each ARN in `accountRoleArns`

**Required trust policy on each member role** (trust the base identity):
```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::<BASE_ACCOUNT_ID>:root"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "<your_external_id>"
    }
  }
}
```
> Remove the `Condition` block if you are not using `externalId`.

> You can also scope the Principal to a specific IAM role or user instead of `:root` if preferred.

**If this fails:**
- Check the integration logs — each failed ARN is logged individually as a warning.
- A partial failure (some accounts inaccessible) is non-fatal and logged; only zero successes causes a hard failure.

---

### Organizations Strategy
**Triggered by:** `accountRoleArn` (a single ARN) set in config.

The most complex strategy — designed for AWS Organizations. It runs in two phases:

**Phase 1 — Discover accounts:**
The base identity assumes the management account role, then uses that session to call `organizations:ListAccounts` and discover all ACTIVE member accounts.

**Phase 2 — Access each member account:**
The base identity (not the management account role) then directly assumes the same-named role in each discovered member account concurrently.

```
[Base Identity]
       ↓ sts:AssumeRole → [Management Account Role]
                                  ↓ organizations:ListAccounts
                                  → discovers Account B, C, D...

[Base Identity]
       ↓ sts:AssumeRole → [Same-named Role in Account B]
       ↓ sts:AssumeRole → [Same-named Role in Account C]
       ↓ sts:AssumeRole → [Same-named Role in Account D]
```

> The role name in every member account **must match** the role name in the management account ARN. The integration builds member ARNs by taking the role name from `accountRoleArn` and substituting each discovered account ID.

**Fallback:** If the Organizations API returns `AccessDenied` or `AWSOrganizationsNotInUse`, the integration automatically falls back to single-account mode using just the management account role.

**Required permissions on the base identity:**
- `sts:AssumeRole` on the management account role ARN
- `sts:AssumeRole` on the same-named role in every member account

**Required trust policy on the management account role** (trust the base identity):
```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::<BASE_ACCOUNT_ID>:root"
  },
  "Action": "sts:AssumeRole"
}
```

**Required permissions on the management account role:**
- `organizations:ListAccounts`

**Required trust policy on each member account role** (trust the base identity, not the management account role):
```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::<BASE_ACCOUNT_ID>:root"
  },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "<your_external_id>"
    }
  }
}
```
> Remove the `Condition` block if you are not using `externalId`.

**If this fails:**
- Phase 1 failure: management account role doesn't exist, trust policy wrong, or `organizations:ListAccounts` not permitted.
- Phase 2 partial failure: some member roles inaccessible — logged as warnings, others continue.
- Phase 2 total failure: no member roles accessible — raises hard error.

---

## Part 3: Resource Permissions

Once inside an account, the assumed role (or base identity in single-account mode) needs read access to each resource type. These go in the **permission policy** of the role.

| Resource Kind | Required Permissions |
|---|---|
| S3 Buckets | `s3:ListAllMyBuckets`, `s3:GetBucketLocation`, `s3:GetBucketTagging` |
| EC2 Instances | `ec2:DescribeInstances`, `ec2:DescribeRegions` |
| ECS Clusters | `ecs:ListClusters`, `ecs:DescribeClusters` |
| ECS Services | `ecs:ListServices`, `ecs:DescribeServices` |
| ECS Task Definitions | `ecs:ListTaskDefinitions`, `ecs:DescribeTaskDefinition` |
| EKS Clusters | `eks:ListClusters`, `eks:DescribeCluster` |
| RDS Instances | `rds:DescribeDBInstances` |
| Lambda Functions | `lambda:ListFunctions`, `lambda:GetFunction` |
| SQS Queues | `sqs:ListQueues`, `sqs:GetQueueAttributes` |
| ECR Repositories | `ecr:DescribeRepositories` |
| Account/Region discovery | `account:ListRegions` |

---

## Part 4: Integration Configuration Reference

These fields are set in the Port integration config UI:

| Field | Type | What It Does |
|---|---|---|
| `accountRoleArn` | string | Single role ARN for the management account. Activates **OrganizationsStrategy** (auto-discovers all accounts via AWS Organizations, falls back to single account if Organizations is not available). |
| `accountRoleArns` | string[] | Explicit list of role ARNs (one per account). Activates **MultiAccountStrategy**. |
| `externalId` | string | Passed as `ExternalId` in every `sts:AssumeRole` call. Must match the `sts:ExternalId` condition in the role's trust policy if one is set. |
| `aws_access_key_id` | string (sensitive) | IAM user Access Key ID. Activates **StaticCredentialProvider**. |
| `aws_secret_access_key` | string (sensitive) | IAM user Secret Access Key. Activates **StaticCredentialProvider**. |
| `aws_session_token` | string (sensitive) | Optional. Short-lived session token for temporary static credentials. |

These fields are set in the Port App Config (per-resource mapping):

| Field | Type | What It Does |
|---|---|---|
| `regionPolicy.allow` | string[] | Allowlist of regions to scan. If set without `deny`, only these regions are scanned. |
| `regionPolicy.deny` | string[] | Denylist of regions to never scan. If set without `allow`, all other regions are scanned. |
| `maxConcurrentAccounts` | int (default: 5) | How many AWS accounts are processed in parallel during a resync. |

### Region policy logic

| `allow` | `deny` | Result |
|---|---|---|
| empty | empty | All regions scanned |
| `[us-east-1]` | empty | Only `us-east-1` |
| empty | `[eu-west-1]` | Everything except `eu-west-1` |
| `[us-east-1]` | `[eu-west-1]` | Only `us-east-1`; `eu-west-1` and everything else denied |
| `[us-east-1]` | `[us-east-1]` | Deny wins — `us-east-1` is denied |

---

## Part 5: Choosing the Right Setup

| Your Situation | What to Configure |
|---|---|
| Single account, running on EC2/ECS with an instance/task role | Nothing required — boto3 picks up credentials automatically |
| Single account, IAM user with static keys | `aws_access_key_id` + `aws_secret_access_key` |
| Multiple accounts, no AWS Organizations | `accountRoleArns` = list of all role ARNs (one per account) |
| Multiple accounts via AWS Organizations | `accountRoleArn` = management account role ARN |
| Kubernetes with IRSA | Set `AWS_WEB_IDENTITY_TOKEN_FILE` env var + configure `accountRoleArn` or `accountRoleArns` |
| Role assumption with an ExternalId condition in trust policy | Add `externalId` matching the value in the trust policy |

---

## Part 6: Troubleshooting

### The integration fails immediately on startup
The health check failed. This happens before any data is synced.
- **Single account:** `sts:GetCallerIdentity` failed → base credentials are invalid or missing.
- **Multi-account:** All role ARNs failed to assume → check trust policies and base identity permissions.
- **Organizations:** Management account role assumption failed, or `organizations:ListAccounts` denied.

### Some accounts are missing but others sync fine
Individual role assumption failures are non-fatal. Check the logs for warnings like:
```
Cannot assume role 'arn:aws:iam::XXXX:role/...' in account XXXX
```
This means the trust policy on that account's role is wrong, the role doesn't exist, or the base identity lacks `sts:AssumeRole` permission for that ARN.

### No regions are being scanned in an account
Either `regionPolicy` is too restrictive, or `account:ListRegions` is denied in that account.

### Web identity fails in Kubernetes
- Verify `AWS_WEB_IDENTITY_TOKEN_FILE` points to a valid, non-empty file.
- Verify the EKS cluster has an OIDC provider configured in IAM.
- Verify the role trust policy references the correct OIDC provider ARN and service account subject.

### Integration worked before, now fails mid-run
Likely a credential refresh failure. Static credentials never refresh — rotate them and update the config. For assume-role credentials, check if STS is throttling or if the session limit (1-hour default) is being hit under high concurrency.

### Organizations strategy only syncs the management account
The Organizations API returned `AccessDenied` or `AWSOrganizationsNotInUse`, so the integration fell back to single-account mode. Check:
- The management account role has `organizations:ListAccounts` permission.
- The account running the integration is actually the management (master) account of an AWS Organization.
