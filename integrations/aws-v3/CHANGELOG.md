# Changelog - Ocean - aws-v3

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.3-dev (TBD)


### Features

- Added OIDC web identity authentication support via new `oidc_token` configuration parameter
- Introduced `WebIdentityCredentialProvider` for federated authentication using AWS STS `assume_role_with_web_identity`
- Enhanced session factory to route OIDC configurations to web identity provider with multi-account strategy
- Static credential provider now requires explicit `aws_access_key_id` and `aws_secret_access_key` instead of falling back to boto3 credential toolchain


## 0.1.2-dev (2025-07-20)


### Improvements

- Bumped ocean version to ^0.26.1


## 0.1.1-dev (2025-07-16)


### Bug Fixes

- Patch `ResyncStrategyFactory.create` in single-account and multi-account session tests to ensure full test isolation. This fixes test flakiness caused by reliance on global state and real factory logic in `TestGetAllAccountSessions` (in `test_session_factory.py`).


## 0.1.0-dev (2025-07-09)


### Features

- Introduced support for both multi-account and single-account resync strategies.
- Enabled authentication using static credentials and IAM roles.
- Removed the requirement for organization/root account-level permissions.
