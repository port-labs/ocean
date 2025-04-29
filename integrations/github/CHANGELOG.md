# Changelog - Ocean - GitHub

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0-beta (2025-03-27)

### Features

- Created GitHub Ocean integration with support for Repository, Pull Request, Issue, Team, and Workflow kinds
- Implemented GitHubRateLimiter class for efficient API rate limit handling
- Added concurrent request limiting with configurable thresholds
- Implemented efficient pagination using GitHub's Link header
- Added support for webhook event processors with individual handlers