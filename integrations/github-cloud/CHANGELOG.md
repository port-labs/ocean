# Changelog

All notable changes to the GitHub Cloud integration will be documented in this file.

## 0.1.6-dev (2024-04-04)

### Added
- Implemented webhook processors for:
  - Repository events
  - Issue events
  - Pull Request events
  - Team events
  - Workflow events
- Added proper event handling for all webhook types
- Added organization and state filtering for webhook events
- Added proper error handling and logging for webhook events

### Changed
- Moved `get_client` function from `main.py` to `client.py` for better code organization
- Updated webhook processor initialization in `main.py`
- Improved error handling in webhook processors
- Enhanced logging throughout the integration

### Fixed
- Fixed import errors in webhook processors
- Fixed event parameter handling in webhook processors
- Fixed resource configuration handling in webhook processors

## 0.1.5-dev (2024-04-03)

### Added
- Added comprehensive logging to all resource fetching methods (repositories, pull requests, issues, teams, workflows)
- Added proper error handling and logging for webhook operations

### Changed
- Refactored `get_workflows` to use `fetch_with_retry` instead of `_fetch_paginated_api` to handle GitHub API response structure correctly
- Updated `fetch_with_retry` to properly handle different HTTP methods (GET, POST, DELETE)
- Improved error handling for non-existent repositories in webhook operations
- Standardized logging patterns across all resource fetching methods

### Fixed
- Fixed "unexpected keyword argument 'method'" error in HTTP requests
- Fixed incorrect handling of GitHub API response structure in workflows endpoint
- Fixed pagination handling in resource fetching methods

## 0.1.4-dev (2024-04-02)

### Added
- Implemented abstract methods in all webhook processors to match parent class interface
- Added proper validation for webhook payloads in all processors
- Added support for both workflow and workflow_run events in WorkflowWebhookProcessor
- Added comprehensive error handling and logging across all processors

### Changed
- Updated repository name handling in PullRequestWebhookProcessor to use `name` instead of `full_name`
- Improved payload validation to include sender and organization information where required
- Enhanced event processing logic to handle both create/update and delete events consistently
- Standardized error messages and logging across all processors

### Fixed
- Fixed workflow event handling to support both workflow and workflow_run events
- Fixed pull request delete event handling
- Fixed team webhook payload validation to properly check for organization information
- Fixed repository webhook payload validation to properly check for sender information

### Security
- Added proper payload validation to prevent processing of malformed webhook events
- Enhanced error handling to prevent information leakage in error messages

### Tests
- All webhook processor tests now passing
- Added comprehensive test coverage for all webhook event types
- Improved test fixtures to better simulate real webhook events

## 0.1.3-dev (2024-04-02)

### Improvements
- Refactored webhook processors to use a pipeline-based approach for better modularity and maintainability.
- Modify `process_webhook_event` across all webhook processors for clarity.
- Enhanced test discovery and execution setup.

## 0.1.2-dev (2024-03-30)

### Improvements
- Enhanced webhook processors with improved error handling and edge cases
- Added comprehensive test coverage for all webhook processors
- Fixed handling of missing data in repository, issue, and workflow processors
- Improved client test suite with async iteration support

## 0.1.1-dev (2025-03-29)

### Improvements
- Added rate limiting to the GitHub Cloud integration.
- Added support for Webhook Events and API calls
- Added helpers functions

## 0.1.0-dev (2025-03-22)

### Features
### Initial Integration:
Created the GitHub Ocean integration.
Added support for the following 
- kinds:
- Repository
- Issue
- Pull Request
- Workflow

