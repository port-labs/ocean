# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.4.12 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.3


## 0.4.11 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.2


## 0.4.10 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.1


## 0.4.9 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.0


## 0.4.8 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.12


## 0.4.7 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.11


## 0.4.6 (2025-05-20)


### Bug Fixes

- Added permission check for webhook creation in `JiraClient`
- Updated `create_webhooks` to skip creation and log warning if user lacks `ADMINISTER` permission to prevent 403 stopping resync.


## 0.4.5 (2025-05-20)


### Improvements

- Bumped ocean version to ^0.22.10


## 0.4.4 (2025-05-19)


### Improvements

- Bumped ocean version to ^0.22.9


## 0.4.3 (2025-05-15)


### Improvements

- Bumped ocean version to ^0.22.8


## 0.4.2 (2025-05-12)


### Improvements

- Bumped ocean version to ^0.22.7


## 0.4.1 (2025-05-06)


### Improvements

- Bumped ocean version to ^0.22.6


## 0.4.0 (2025-04-29)


### Improvements

- Updated Jira integration to use new JQL search endpoint (/rest/api/3/search/jql) in preparation for May 1st, 2025 deprecation
- Added support for token-based pagination using nextPageToken
- Ensured consistent field selection with *all default

### Bug Fixes

- Fixed issue where fields parameter wasn't being passed correctly in webhook processor
- Updated tests to properly handle new endpoint parameters


## 0.3.18 (2025-04-27)

### Bug Fixes

- Removed httpx dependency to resolve h11 vulnerability

## 0.3.17 (2025-04-27)

### Bug Fixes

- Resolved "h11 accepts some malformed Chunked-Encoding bodies" h11 vulnerability


### Improvements

- Bumped ocean version to ^0.22.5


## 0.3.16 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.4


## 0.3.15 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.3


## 0.3.14 (2025-04-07)


### Improvements

- Bumped ocean version to ^0.22.2


## 0.3.13 (2025-04-03)


### Improvements

- Bumped ocean version to ^0.22.1


## 0.3.12 (2025-03-24)


### Improvements

- Bumped ocean version to ^0.22.0


## 0.3.11 (2025-03-13)


### Improvements

- Bumped ocean version to ^0.21.5


## 0.3.10 (2025-03-12)


### Improvements

- Bumped ocean version to ^0.21.4


## 0.3.9 (2025-03-10)


### Improvements

- Bumped ocean version to ^0.21.3


## 0.3.8 (2025-03-09)


### Improvements

- Bumped ocean version to ^0.21.1


## 0.3.7 (2025-03-03)


### Improvements

- Bumped ocean version to ^0.21.0


## 0.3.6 (2025-02-27)


### Improvements

- Enabled live events for Jira Ocean SaaS installation


## 0.3.5 (2025-02-26)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.3.4 (2025-02-25)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.3.3 (2025-02-24)


### Improvements

- Bumped ocean version to ^0.20.3


## 0.3.2 (2025-02-24)


### Improvements

- Added support for OAuth live events for Jira using the webhooks api.
  - https://developer.atlassian.com/cloud/jira/platform/webhooks/#registering-a-webhook-using-the-rest-api--for-connect-and-oauth-2-0-apps-


## 0.3.1 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.2


## 0.3.0 (2025-02-23)


### Improvements

- Introduced a standardized abstraction for Jira integration
- Added dedicated webhook processors for issues, projects, and users
- Refactored and modularized code for better maintainability
- Enhanced error handling and logging for webhook events


## 0.2.41 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.1


## 0.2.40 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.20.0


## 0.2.39 (2025-02-19)


### Improvements

- Added base_url reference instead of app_host
- Made JiraClient inherit OAuthClient, and implement external access token prior to local jira token


## 0.2.38 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.3


## 0.2.37 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.2


## 0.2.36 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.1


## 0.2.35 (2025-02-13)


### Improvements

- Bumped cryptography version to ^44.0.1


## 0.2.34 (2025-02-09)


### Improvements

- Bumped ocean version to ^0.18.9


## 0.2.33 (2025-02-04)


### Improvements

- Bumped ocean version to ^0.18.8


## 0.2.32 (2025-01-29)


### Improvements

- Bumped ocean version to ^0.18.6


## 0.2.31 (2025-01-28)


### Improvements

- Bumped ocean version to ^0.18.5


## 0.2.30 (2025-01-23)


### Improvements

- Bumped ocean version to ^0.18.4


## 0.2.29 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.3


## 0.2.28 (2025-01-22)


### Improvements

- Updated mappings to have typed array items


## 0.2.27 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.2


## 0.2.26 (2025-01-21)


### Improvements

- Bumped ocean version to ^0.18.1


## 0.2.25 (2025-01-19)


### Improvements

- Bumped ocean version to ^0.18.0


## 0.2.24 (2025-01-16)


### Bug Fixes

- Updated default mapping for Jira Issue to use by removing `""` to prevent `parentIssue` error spam


## 0.2.23 (2025-01-16)


### Improvements

- Bumped ocean version to ^0.17.8


## 0.2.22 (2025-01-15)


### Improvements

- Added rate limit support to avoid failures due to 429 errors



## 0.2.21 (2025-01-15)


### Improvements

- Bumped jinja version to 3.1.5


## 0.2.20 (2025-1-13)


### Improvements

- Added support to sync Jira teams to Port

## 0.2.19 (2025-01-12)


### Improvements

- Bumped ocean version to ^0.17.7


## 0.2.18 (2025-01-08)


### Bug Fixes

- Fixed a bug where webhook processes issues that are not allowed in a user's integration due to JQL filters


## 0.2.17 (2025-01-08)


### Improvements

- Bumped ocean version to ^0.17.6


## 0.2.16 (2025-01-07)


### Features

- Added support for ingesting other fields apart from the default fields (Jira Sprint support)


## 0.2.15 (2025-01-07)


### Improvements

- Bumped ocean version to ^0.17.5


## 0.2.14 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.4


## 0.2.13 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.3


## 0.2.12 (2024-12-31)


### Improvements

- Bumped ocean version to ^0.17.2


## 0.2.11 (2025-12-30)


### Improvements

- Added title to the configuration properties


## 0.2.10 (2024-12-26)


### Improvements

- Bumped ocean version to ^0.16.1


## 0.2.9 (2024-12-24)


### Improvements

- Bumped ocean version to ^0.16.0


## 0.2.8 (2024-12-24)


### Features

- Added a field to display total issues in a project


## 0.2.7 (2024-12-24)


### Improvements

- Changed issue priority from id to name


## 0.2.6 (2024-12-22)


### Improvements

- Bumped ocean version to ^0.15.3


## 0.2.5 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.2


## 0.2.4 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.1


## 0.2.3 (2024-12-12)


### Improvements

- Bumped ocean version to ^0.15.0


## 0.2.2 (2024-12-10)


### Improvements

- Bumped ocean version to ^0.14.7


## 0.2.1 (2024-12-05)


### Improvements

- Added support to sync Jira users to Port and created relevant relations to jira issues assignee and reporter

## 0.2.0 (2024-12-04)


### Improvements

- Supporting Bearer token for Oauth2 authentication
- Added OAuth installation specification for Port


## 0.1.105 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.6


## 0.1.104 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.5


## 0.1.103 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.3


## 0.1.102 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.2


## 0.1.101 (2024-11-21)


### Improvements

- Bumped ocean version to ^0.14.1


## 0.1.100 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.14.0


## 0.1.99 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.13.1


## 0.1.98 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.13.0


## 0.1.97 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.12.9


## 0.1.96 (2024-11-06)


### Improvements

- Bumped ocean version to ^0.12.8


## 0.1.95 (2024-10-23)


### Improvements

- Bumped ocean version to ^0.12.7


## 0.1.94 (2024-10-22)


### Improvements

- Bumped ocean version to ^0.12.6


## 0.1.93 (2024-10-14)


### Improvements

- Bumped ocean version to ^0.12.4


## 0.1.92 (2024-10-09)


### Improvements

- Bumped ocean version to ^0.12.3


## 0.1.91 (2024-10-08)


### Improvements

- Bumped ocean version to ^0.12.2


## 0.1.90 (2024-10-01)


### Improvements

- Bumped ocean version to ^0.12.1


## 0.1.89 (2024-09-29)


### Improvements

- Bumped ocean version to ^0.11.0


## 0.1.88 (2024-09-22)


### Improvements

- Bumped ocean version to ^0.10.12


## 0.1.87 (2024-09-17)


### Improvements

- Bumped ocean version to ^0.10.11


## 0.1.86 (2024-09-12)


### Improvements

- Bumped ocean version to ^0.10.10 (#1)


## 0.1.85 (2024-09-05)


### Improvements

- Bumped ocean version to ^0.10.9 (#1)


## 0.1.84 (2024-09-04)


### Improvements

- Bumped ocean version to ^0.10.8 (#1)


## 0.1.83 (2024-09-01)


### Improvements

- Bumped ocean version to ^0.10.7 (#1)


## 0.1.82 (2024-08-30)


### Improvements

- Bumped ocean version to ^0.10.5 (#1)


## 0.1.81 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.4 (#1)


## 0.1.80 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.3 (#1)


## 0.1.79 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.2 (#1)


## 0.1.78 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.1 (#1)


## 0.1.77 (2024-08-22)


### Improvements

- Bumped ocean version to ^0.10.0 (#1)


## 0.1.76 (2024-08-20)


### Improvements

- Bumped ocean version to ^0.9.14 (#1)


## 0.1.75 (2024-08-13)


### Improvements

- Bumped ocean version to ^0.9.13 (#1)


## 0.1.74 (2024-08-11)


### Improvements

- Bumped ocean version to ^0.9.12 (#1)


## 0.1.73 (2024-08-05)


### Improvements

- Updated the JQL filter used in the default configuration mapping to also ingest Jira issues that were opened or updated in the past week
- Updated the default mapping for the `issue` kind
- Updated the default blueprints and their properties


## 0.1.72 (2024-08-05)


### Improvements

- Bumped ocean version to ^0.9.11 (#1)


## 0.1.71 (2024-08-04)


### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.1.70 (2024-08-01)


### Improvements

- Added target='blank' attribute to links in config and secrets description to make them open in new tab


## 0.1.69 (2024-07-31)


### Improvements

- Upgraded integration dependencies (#1)


## 0.1.68 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.1.67 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.1.66 (2024-07-24)


### Improvements

- Bumped ocean version to ^0.9.5


## 0.1.65 (2024-07-16)


### Improvements

- Changed description of atlassianUserToken configuration


## 0.1.64 (2024-07-10)


### Improvements

- Bumped ocean version to ^0.9.4 (#1)


## 0.1.63 (2024-07-09)


### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.1.62 (2024-07-07)


### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.1.61 (2024-06-23)


###  Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.1.60 (2024-06-19)


###  Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.1.59 (2024-06-16)


###  Improvements

- Bumped ocean version to ^0.8.0 (#1)


## 0.1.58 (2024-06-13)


###  Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.57 (2024-06-13)


###  Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.56 (2024-06-10)


###  Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.55 (2024-06-05)


###  Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.54 (2024-06-03)


###  Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.53 (2024-06-02)


###  Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.52 (2024-05-30)


###  Improvements

- Updated the JQL filter used in the default configuration mapping to not ingest Jira issues of the `done` statusCategory
- Updated the default mapping for the `issue` kind

## 0.1.51 (2024-05-30)


###  Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


## 0.1.50 (2024-05-29)


###  Improvements

- Bumped ocean version to ^0.5.22 (#1)


## 0.1.49 (2024-05-26)


###  Improvements

- Bumped ocean version to ^0.5.21 (#1)


## 0.1.48 (2024-05-26)


###  Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


## 0.1.47 (2024-05-16)


###  Improvements

- Bumped ocean version to ^0.5.19 (#1)


## 0.1.46 (2024-05-12)


###  Improvements

- Bumped ocean version to ^0.5.18 (#1)


## 0.1.45 (2024-05-01)


###  Improvements

- Bumped ocean version to ^0.5.17 (#1)


## 0.1.44 (2024-05-01)


###  Improvements

- Bumped ocean version to ^0.5.16 (#1)


## 0.1.43 (2024-04-30)


###  Improvements

- Bumped ocean version to ^0.5.15 (#1)


## 0.1.42 (2024-04-24)


###  Improvements

- Bumped ocean version to ^0.5.14 (#1)


## 0.1.41 (2024-04-17)

### Improvements

- Bumped ocean version to ^0.5.12 (#1)


## 0.1.40 (2024-04-11)

### Improvements

- Bumped ocean version to ^0.5.11 (#1)


## 0.1.39 (2024-04-10)

### Improvements

- Bumped ocean version to ^0.5.10 (#1)


## 0.1.38 (2024-04-01)

### Improvements

- Bumped ocean version to ^0.5.9 (#1)


## 0.1.37 (2024-03-28)

### Improvements

- Bumped ocean version to ^0.5.8 (#1)


## 0.1.36 (2024-03-25)

### Improvements

- Updated default blueprints and config mapping to include issue labels (port-7311)


## 0.1.35 (2024-03-20)

### Improvements

- Bumped ocean version to ^0.5.7 (#1)


## 0.1.34 (2024-03-17)

### Improvements

- Bumped ocean version to ^0.5.6 (#1)


## 0.1.33 (2024-03-06)

### Improvements

- Bumped ocean version to ^0.5.5 (#1)


## 0.1.32 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


## 0.1.31 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.3 (#1)


## 0.1.30 (2024-02-21)

### Improvements

- Bumped ocean version to ^0.5.2 (#1)


## 0.1.29 (2024-02-20)

### Improvements

- Bumped ocean version to ^0.5.1 (#1)


## 0.1.28 (2024-02-18)

### Improvements

- Bumped ocean version to ^0.5.0 (#1)


## 0.1.27 (2024-01-23)

### Improvements

- Bumped ocean version to ^0.4.17 (#1)


## 0.1.26 (2024-01-11)

### Improvements

- Bumped ocean version to ^0.4.16 (#1)


## 0.1.25 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.15 (#1)


## 0.1.24 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.14 (#1)


## 0.1.23 (2024-01-01)

### Improvements

- Bumped ocean version to ^0.4.13 (#1)


## 0.1.22 (2023-12-25)

### Improvements

- Fix stale relation identifiers in default blueprints (port-5799)


## 0.1.21 (2023-12-24)

### Improvements

- Updated default blueprints and config mapping to include integration name as blueprint identifier prefix
- Bumped ocean version to ^0.4.12 (#1)


## 0.1.20 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


## 0.1.19 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


v## 0.1.18 (2023-12-20)

### Improvements

- Updated authentication method to use built-in basic auth function
- Added warning message when 0 issues or projects are queried from the Jira API


## 0.1.17 (2023-12-18)

### Improvements

- Updated the Jira issue blueprint by adding entity properties including created datetime, updated datetime and priority (#17)


## 0.1.16 (2023-12-14)

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


## 0.1.15 (2023-12-05)

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


## 0.1.14 (2023-12-04)

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


## 0.1.13 (2023-11-30)

### Improvements

- Bumped ocean version to ^0.4.5 (#1)
- Changed http client default timeout to 30 seconds


## 0.1.12 (2023-11-29)

### Improvements

- Bumped ocean version to ^0.4.4 (#1)
- Changed the httpx client to be the ocean's client for better connection error handling and request retries


## 0.1.11 (2023-11-21)

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


## 0.1.10 (2023-11-08)

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


## 0.1.9 (2023-11-03)

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


## 0.1.8 (2023-11-01)

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener (#1)


## 0.1.7 (2023-10-30)

### Improvements

- Fixed the default mapping to exclude issues with status `Done` (#1)


## 0.1.6 (2023-10-29)

### Improvements

- Bumped ocean version to 0.3.2 (#1)


## 0.1.5 (2023-09-27)

### Improvements

- Bumped ocean to version 0.3.1 (#1)

## 0.1.4 (2023-09-13)

### Improvements

- Bumped ocean to 0.3.0 (#1)

## 0.1.3 (2023-08-29)

### Improvements

- Changed the app_host to not be required for the installation (PORT-4527)
- Bumped Ocean to 0.2.3 (#1)

## 0.1.2 (2023-08-11)

### Improvements

- Optimized dockerfile to produce smaller images (PORT-4485)

## 0.1.1 (2023-08-11)

### Improvements

- Upgraded ocean to version 0.2.2

v## 0.1.0 (2023-08-10)

### Features

- Added Jira integration with support for projects and issues (PORT-4410)
