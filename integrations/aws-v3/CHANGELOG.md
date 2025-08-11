# Changelog - Ocean - aws-v3

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.5-dev (2025-08-11)


### Improvements

- Bumped ocean version to ^0.27.2


## 0.2.4-dev (2025-08-07)


### Improvements

- Bumped ocean version to ^0.27.1


## 0.2.3-dev (2025-08-05)


### Improvements

- Bumped ocean version to ^0.27.0


## 0.2.2-dev (2025-08-04)


### Improvements

- Bumped ocean version to ^0.26.3


## 0.2.1-dev (2025-08-03)


### Improvements

- Bumped ocean version to ^0.26.2


## 0.2.0-dev (2025-07-20)


### Improvements

- Add assume role with web identity provider

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
