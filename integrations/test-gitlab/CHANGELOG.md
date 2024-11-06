# Changelog - Ocean - gitlab_v2

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0-beta] - 2024-11-06

### Added
- **Webhook Integration**: Refined webhook setup to handle GitLab group, project, and other relevant events more effectively.
  - Added support for instance-level webhooks to capture events across all GitLab resources.
  - Improved error handling for webhook setup to handle permission errors.
- **Testing Suite Enhancements**:
  - Added unit tests and integration tests for data-fetching methods (`fetch_groups`, `fetch_projects`, `fetch_merge_requests`, `fetch_issues`).
  - Mocked responses in unit tests to simulate API responses, ensuring consistency and isolating logic.
  - Integrated logging in test cases to provide detailed information about test execution progress.

### Fixed
- **Blueprint Availability Issue**: Resolved issues with missing or misconfigured blueprints that could interfere with entity upserts.

### Changed
- **Error Handling**: Enhanced error handling and logging for webhook setup to improve debugging for `403 Forbidden` responses and other potential issues.

## [0.5.0] - 2024-11-06

### Added
- **GitLab Issues Integration**: Added support for syncing GitLab issues into Port Ocean.
  - Fetches issue details, including ID, title, status, author, creation date, update date, close date (if applicable), labels, and description, and maps them to Port Ocean entities.

## [0.4.0] - 2024-11-06

### Added
- **GitLab Merge Requests Integration**: Added support for syncing GitLab merge requests into Port Ocean.
  - Fetches merge request details, including ID, title, status, author, creation date, update date, merge date (if applicable), and associated reviewers, and maps them to Port Ocean entities.

## [0.3.0] - 2024-11-06

### Added
- **GitLab Projects Integration**: Added support for syncing GitLab projects into Port Ocean.
  - Fetches project details, including project ID, name, description, and namespace, and maps them to Port Ocean entities.

## [0.2.0] - 2024-11-05

### Added
- **Webhooks Integration**: Added support for GitLab webhooks to enable real-time updates for projects and groups in Port Ocean.
- **Pagination Support**: Implemented pagination to fetch large data sets from GitLab effectively.
- **Rate Limiting**: Added rate limiting to control API request frequency, avoiding GitLab API rate restrictions.
- **Recursive Fetching for Subgroups**: Enabled recursive fetching of subgroups, allowing hierarchical group structures to be synced completely.

## [0.1.0-beta] - 2024-11-04

### Added
- **GitLab Groups Integration**: Initial support for syncing GitLab groups into Port Ocean.
  - Fetches top-level group details from GitLab and maps them to Port Ocean entities.
