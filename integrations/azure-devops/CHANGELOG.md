# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.4 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.3


## 0.2.3 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.2


## 0.2.2 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.1


## 0.2.1 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.0


## 0.2.0 (2025-05-26)

### Features

 Transitioned live events management to ocean’s `LiveEventProcessorManager` to streamline processing

## 0.1.156 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.12


## 0.1.155 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.11


## 0.1.154 (2025-05-21)


### Improvements

- Added support for monorepo


## 0.1.153 (2025-05-20)

### Improvements

- Bumped ocean version to ^0.22.10


## 0.1.152 (2025-05-19)


### Improvements

- Bumped ocean version to ^0.22.9


## 0.1.151 (2025-05-15)


### Improvements

- Bumped ocean version to ^0.22.8


## 0.1.150 (2025-05-12)


### Improvements

- Bumped ocean version to ^0.22.7


## 0.1.149 (2025-05-07)


### Bug Fixes

- Fixed `AzureDevopsClient` to support self-hosted Azure DevOps instances to preserve base URLs for self-hosted cases.


## 0.1.148 (2025-05-06)


### Improvements

- Bumped ocean version to ^0.22.6


## 0.1.147 (2025-04-27)


### Bug Fixes

- Resolved "h11 accepts some malformed Chunked-Encoding bodies" h11 vulnerability

### Improvements

- Bumped ocean version to ^0.22.5


## 0.1.146 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.4


## 0.1.145 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.3


## 0.1.144 (2025-04-07)


### Improvements

- Bumped ocean version to ^0.22.2


## 0.1.143 (2025-04-03)


### Improvements

- Added support for fetching pull requests concurently


## 0.1.142 (2025-04-03)


### Improvements

- Bumped ocean version to ^0.22.1


## 0.1.141 (2025-03-24)


### Improvements

- Bumped ocean version to ^0.22.0


## 0.1.140 (2025-03-18)


### Improvements

- Added support for ingesting files from Azure DevOps repositories


## 0.1.139 (2025-03-13)


### Bug Fixes

- Fixed bug where other resource types fail JSON decoding due to lack of response body in 404 errors


## 0.1.138 (2025-03-13)


### Improvements

- Bumped ocean version to ^0.21.5


## 0.1.137 (2025-03-12)


### Improvements

- Bumped ocean version to ^0.21.4


## 0.1.136 (2025-03-10)


### Improvements

- Bumped ocean version to ^0.21.3


## 0.1.135 (2025-03-09)


### Improvements

- Bumped ocean version to ^0.21.1


## 0.1.134 (2025-03-04)


### Bug Fixes

- Fixed bug causing repositories of disabled projects to be fetched, causing failure to retrieve child objects of the repositories


## 0.1.133 (2025-03-03)


### Improvements

- Bumped ocean version to ^0.21.0


## 0.1.132 (2025-02-26)


### Bug Fixes

- Fixed bug causing repositories of disabled projects to be fetched, causing failure to retrieve child objects of the repositories


## 0.1.131 (2025-02-26)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.130 (2025-02-25)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.129 (2025-02-24)


### Improvements

- Bumped ocean version to ^0.20.3


## 0.1.128 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.2


## 0.1.127 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.1


## 0.1.126 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.20.0


## 0.1.125 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.3


## 0.1.124 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.2


## 0.1.123 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.1


## 0.1.122 (2025-02-18)


### Bug Fixes

- Fixed bug where inappropriate log level is used leading to the integration crashing


## 0.1.121 (2025-02-13)


### Improvements

- Bumped cryptography version to ^44.0.1


## 0.1.120 (2025-02-11)


### Bug Fixes

- Fixed an issue where if the organization URL was formatted like https://org.visualstudio.com pulling release would return 404


## 0.1.119 (2025-02-11)


### Bug Fixes

- Modified the work item fetching logic to retrieve work items in paginated batches rather than loading up to 19,999 items in a single request.


## 0.1.118 (2025-02-11)


### Bugfix

- Fixed an issue where if the organization url was formatted like https://XXX.visualstudio.com pulling users would return 404


## 0.1.117 (2025-02-09)


### Improvements

- Bumped ocean version to ^0.18.9


## 0.1.116 (2025-02-5)


### Improvements

- Added support for User kind
- Added selector `includeMembers` to enable enriching team with members


## 0.1.115 (2025-02-04)


### Improvements

- Bumped ocean version to ^0.18.8


## 0.1.114 (2025-01-29)


### Improvements

- Bumped ocean version to ^0.18.6


## 0.1.113 (2025-01-28)


### Improvements

- Bumped ocean version to ^0.18.5


## 0.1.112 (2025-01-23)


### Improvements

- Bumped ocean version to ^0.18.4


## 0.1.111 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.3


## 0.1.110 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.2


## 0.1.109 (2025-01-21)


### Improvements

- Bumped ocean version to ^0.18.1


## 0.1.108 (2025-01-19)


### Improvements

- Bumped ocean version to ^0.18.0


## 0.1.107 (2025-01-16)


### Improvements

- Bumped ocean version to ^0.17.8


## 0.1.106 (2025-01-15)


### Improvements

- Bumped jinja version to 3.1.5


## 0.1.105 (2025-01-12)


### Improvements

- Bumped ocean version to ^0.17.7


## 0.1.104 (2025-01-08)


### Bug Fixes

- Fixed bug where push events for port.yml file aren't processed for default branches


## 0.1.103 (2025-01-07)


### Improvements

- Bumped ocean version to ^0.17.5


## 0.1.102 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.4


## 0.1.101 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.3


## 0.1.100 (2024-12-31)


### Improvements

- Bumped ocean version to ^0.17.2


## 0.1.99 (2024-12-30)


### Improvements

- Added title to the configuration properties


## 0.1.98 (2024-12-26)


### Improvements

- Bumped ocean version to ^0.16.1


## 0.1.97 (2024-12-24)


### Improvements

- Bumped ocean version to ^0.16.0


## 0.1.96 (2024-12-22)


### Improvements

- Bumped ocean version to ^0.15.3


## 0.1.95 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.2


## 0.1.94 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.1


## 0.1.93 (2024-12-12)


### Bug Fixes

- Fixed pagination in Azure DevOps integration by replacing `skip` pagination with `continuationToken` for `generate_releases` method.

## 0.1.92 (2024-12-12)


### Improvements

- Bumped ocean version to ^0.15.0


## 0.1.91 (2024-12-10)


### Improvements

- Added support for expanding the work item response


## 0.1.90 (2024-12-10)


### Improvements

- Bumped ocean version to ^0.14.7


## 0.1.89 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.6


## 0.1.88 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.5


## 0.1.87 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.3


## 0.1.86 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.2


## 0.1.85 (2024-11-21)


### Improvements

- Bumped ocean version to ^0.14.1


## 0.1.84 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.14.0


## 0.1.83 (2024-11-12)


### Improvements

- Updated wiql base query to use immutable fields for fetching work items related to a project


## 0.1.82 (2024-11-12)


### Improvements


- Bumped ocean version to ^0.13.1


## 0.1.81 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.13.0


## 0.1.80 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.12.9


## 0.1.79 (2024-11-07)


### Bug Fixes

- Fixed the API endpoint used in the boards kind to iterate through all project teams, ensuring non-default team boards and columns are ingested


## 0.1.78 (2024-11-06)


### Improvements

- Bumped ocean version to ^0.12.8


## 0.1.77 (2024-10-23)


### Improvements

- Bumped ocean version to ^0.12.7


## 0.1.76 (2024-10-22)


### Improvements

- Bumped ocean version to ^0.12.6


## 0.1.75 (2024-10-14)


### Improvements

- Bumped ocean version to ^0.12.4


## 0.1.74 (2024-10-10)


### Improvements


- Added support for ingesting boards and columns


## 0.1.73 (2024-10-09)


### Improvements


- Bumped ocean version to ^0.12.3


## 0.1.72 (2024-10-08)


### Improvements


- Bumped ocean version to ^0.12.2


## 0.1.71 (2024-10-01)


### Improvements


- Bumped ocean version to ^0.12.1


## 0.1.70 (2024-09-29)


### Improvements

- Bumped ocean version to ^0.11.0


## 0.1.69 (2024-09-22)


### Improvements

- Bumped ocean version to ^0.10.12


## 0.1.68 (2024-09-17)


### Improvements

- Bumped ocean version to ^0.10.11


## 0.1.67 (2024-09-12)


### Improvements

- Bumped ocean version to ^0.10.10 (#1)


## 0.1.66 (2024-09-06)


### Improvements

- Updated the query for fetching work items such that no more than 20,000 work items can be returned per project using the `$top` API query param (0.1.66)


## 0.1.65 (2024-09-05)


### Improvements

- Updated the work item query langauge to fetch works items per project using System.AreaPath instead of all projects in the current implementation (0.1.65)


## 0.1.64 (2024-09-05)


### Improvements

- Bumped ocean version to ^0.10.9 (#1)


## 0.1.63 (2024-09-05)


### Bug Fixes

- Updated Azure DevOps mapping to handle special characters, fixed project ID references, added work-item logging, and enriched work-item with project data.


## 0.1.62 (2024-09-04)


### Improvements

- Bumped ocean version to ^0.10.8 (#1)


## 0.1.61 (2024-09-01)


### Improvements

- Bumped ocean version to ^0.10.7 (#1)


## 0.1.60 (2024-08-30)


### Improvements

- Bumped ocean version to ^0.10.5 (#1)


## 0.1.59 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.4 (#1)


## 0.1.58 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.3 (#1)


## 0.1.57 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.2 (#1)


## 0.1.56 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.1 (#1)


## 0.1.55 (2024-08-22)


### Improvements

- Bumped ocean version to ^0.10.0 (#1)


## 0.1.54 (2024-08-21)

### Features

- Added work items to get issues, tasks, and epics

## 0.1.53 (2024-08-20)


### Improvements

- Bumped ocean version to ^0.9.14 (#1)


## 0.1.52 (2024-08-13)


### Improvements

- Bumped ocean version to ^0.9.13 (#1)


## 0.1.51 (2024-08-11)


### Improvements

- Bumped ocean version to ^0.9.12 (#1)


## 0.1.50 (2024-08-05)


### Improvements

- Bumped ocean version to ^0.9.11 (#1)


## 0.1.49 (2024-08-04)


### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.1.48 (2024-08-01)

### Improvements

- Added target='blank' attribute to links in config and secrets description to make them open in new tab


## 0.1.47 (2024-07-31)

### Improvements

- Upgraded ##  dependencies (#1)


## 0.1.46 (2024-07-31)

### Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.1.45 (2024-07-31)

### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.1.44 (2024-07-25)

### Bug Fixes

- Fixed case where comparing events failed because ADO returns unexpected additional keys inside the PublisherInputs.


## 0.1.43 (2024-07-24)

### Improvements

- Bumped ocean version to ^0.9.5


## 0.1.41 (2024-07-18)

### Bug Fixes

- Fixed `visibility` property in mapping which had a typo and changed the default relation to required `false` to be more permissive


## 0.1.41 (2024-07-10)

### Improvements

- Set the `isProjectsLimited` paramater to True by default
- Revise the configuration parameters' descriptions.

## 0.1.40 (2024-07-09)

### Improvements

- Added description to the ##  configuration variables

## 0.1.39 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.1.38 (2024-07-08)

### Features

- Make webhook creation project-scoped by default

## 0.1.37 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.1.36 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.1.35 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.1.34 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)


## 0.1.33 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.32 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.31 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.30 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.29 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.28 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.27 (2024-05-30)

### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during ##  scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


## 0.1.26 (2024-05-29)

### Improvements

- Bumped ocean version to ^0.5.22 (#1)


## 0.1.25 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.21 (#1)


## 0.1.24 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


## 0.1.23 (2024-05-16)

### Improvements

- Bumped ocean version to ^0.5.19 (#1)


## 0.1.22 (2024-05-15)

### Bug Fixes

- Fixed default relation mapping between service and project (#1)

## 0.1.21 (2024-05-12)

### Improvements

- Bumped ocean version to ^0.5.18 (#1)


## 0.1.20 (2024-05-10)

### Improvements

- Enhanced the jq functionality for both 'repository' and 'repository-policy' identifiers, automatically removing spaces and converting all characters to lowercase by default. (PORT-7916)


## 0.1.19 (2024-05-08)

### Improvements

- Removed spaces from service identifier field (#1)


## 0.1.18 (2024-05-08)

### Improvements

- Changed url to service from api url to remoteUrl (#1)


## 0.1.17 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.17 (#1)


## 0.1.16 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.16 (#1)


## 0.1.15 (2024-04-30)

### Improvements

- Bumped ocean version to ^0.5.15 (#1)


## 0.1.14 (2024-04-24)

### Improvements

- Bumped ocean version to ^0.5.14 (#1)


## 0.1.13 (2024-04-17)

### Improvements

- Bumped ocean version to ^0.5.12 (#1)


## 0.1.12 (2024-04-15)

### Features

- Added project kind as well as relation between repo and project, to get the team mirror property (PORT-7573)


## 0.1.11 (2024-04-15)

### Bug Fixes

- Made defaultBranch not required in the repository body when fetching repository policies


## 0.1.10 (2024-04-11)

### Improvements

- Bumped ocean version to ^0.5.11 (#1)


## 0.1.9 (2024-04-10)

### Improvements

- Bumped ocean version to ^0.5.10 (#1)


## 0.1.8 (2024-04-01)

### Improvements

- Bumped ocean version to ^0.5.9 (#1)


## 0.1.7 (2024-03-28)

### Improvements

- Bumped ocean version to ^0.5.8 (#1)


## 0.1.6 (2024-03-20)

### Improvements

- Bumped ocean version to ^0.5.7 (#1)


## 0.1.5 (2024-03-17)

### Improvements

- Bumped ocean version to ^0.5.6 (#1)


## 0.1.4 (2024-03-07)

### Bug Fixes

- Fixed issue causing disabled repositories to fail resynchronization for pull requests, policies, and item content (#413)


## 0.1.3 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


## 0.1.2 (2024-03-03)

### Improvements
- Fixed the default scorecard to match the rule

## 0.1.1 (2024-03-03)

### Bugs

- Fix compatibility issue with None type and operand "|"

## 0.1.0 (2024-03-03)

### Features

- Created Azure DevOps ##  using Ocean (PORT-4585)
