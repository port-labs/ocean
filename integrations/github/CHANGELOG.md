# Changelog - Ocean - github

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.3-dev (2025-06-01)


### Improvements

- Bumped ocean version to ^0.23.5


## 0.1.2-dev (2025-05-30)

### Bug Fixes

- Fix timezone inconsistency issue while checking for expired Github App token (PORT-14913)

### Improvements

- Removed `Optional` from `AbstractGithubExporter` options to enforce stricter type adherence for concrete exporters.


## 0.1.1-dev (2025-05-29)

### Improvements

- Bumped ocean version to ^0.23.4


## 0.1.0-dev (2025-05-28)

### Features

- Created GitHub Ocean integration with support for Repository
- Added support for repository webhook event processor
- Add Tests for client and base webhook processor
- Added support for authenticating as a GitHub App
- Add support for Github workflows
- Add support for Github workflow runs
