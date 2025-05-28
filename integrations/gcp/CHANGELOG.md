# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.136 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.3


## 0.1.135 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.2


## 0.1.134 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.1


## 0.1.133 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.0


## 0.1.132 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.12


## 0.1.131 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.11


## 0.1.130 (2025-05-20)


### Improvements

- Bumped ocean version to ^0.22.10


## 0.1.129 (2025-05-19)


### Improvements

- Bumped ocean version to ^0.22.9


## 0.1.128 (2025-05-15)


### Improvements

- Bumped ocean version to ^0.22.8


## 0.1.127 (2025-05-12)


### Improvements

- Bumped ocean version to ^0.22.7


## 0.1.126 (2025-05-06)


### Improvements

- Bumped ocean version to ^0.22.6


## 0.1.125 (2025-04-27)

### Bug Fixes

- Resolved "h11 accepts some malformed Chunked-Encoding bodies" h11 vulnerability

### Improvements

- Bumped ocean version to ^0.22.5


## 0.1.124 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.4


## 0.1.123 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.3


## 0.1.122 (2025-04-07)


### Improvements

- Bumped ocean version to ^0.22.2


## 0.1.121 (2025-04-03)


### Improvements

- Bumped ocean version to ^0.22.1


## 0.1.120 (2025-03-24)


### Improvements

- Bumped ocean version to ^0.22.0


## 0.1.119 (2025-03-13)


### Improvements

- Bumped ocean version to ^0.21.5


## 0.1.118 (2025-03-12)


### Improvements

- Bumped ocean version to ^0.21.4


## 0.1.117 (2025-03-10)


### Improvements

- Bumped ocean version to ^0.21.3


## 0.1.116 (2025-03-09)


### Improvements

- Bumped ocean version to ^0.21.1


## 0.1.115 (2025-03-04)


### Improvements

- Improved logs for handled exceptions by adding the stringified version of such exception


## 0.1.114 (2025-03-03)


### Improvements

- Bumped ocean version to ^0.21.0


## 0.1.113 (2025-02-26)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.112 (2025-02-25)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.111 (2025-02-24)


### Improvements

- Bumped ocean version to ^0.20.3


## 0.1.110 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.2


## 0.1.109 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.1


## 0.1.108 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.20.0


## 0.1.107 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.3


## 0.1.106 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.2


## 0.1.105 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.1


## 0.1.104 (2025-02-14)


### Bug Fixes

- Improved the performance by setting a threshold for the number of background queue
- Added checks that returns server busy when queue exceeds limit
- Updated the rate limiter in `GCPResourceRateLimiter` to actually use the effective limit value rather than the quota value.


## 0.1.103 (2025-02-13)


### Improvements

- Bumped cryptography version to ^44.0.1


## 0.1.102 (2025-02-09)


### Improvements

- Bumped ocean version to ^0.18.9


## 0.1.101 (2025-02-04)


### Improvements

- Bumped ocean version to ^0.18.8


## 0.1.100 (2025-01-29)


### Improvements

- Bumped ocean version to ^0.18.6


## 0.1.99 (2025-01-28)


### Improvements

- Bumped ocean version to ^0.18.5


## 0.1.98 (2025-01-24)


### Improvements

- Added rate limiting support for `ProjectsV3GetRequestsPerMinutePerProject` to handle GCP project quota limits during real-time event processing.
- Implemented a shared `AsyncLimiter` instance to ensure consistent rate limiting across real-time events
- Moved real-time event processing to run in the background, preventing timeouts and ensuring smoother handling of rate-limited operations.


## 0.1.97 (2025-01-23)


### Improvements

- Bumped ocean version to ^0.18.4


## 0.1.96 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.3


## 0.1.95 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.2


## 0.1.94 (2025-01-21)


### Improvements

- Bumped ocean version to ^0.18.1


## 0.1.93 (2025-01-19)


### Improvements

- Bumped ocean version to ^0.18.0


## 0.1.92 (2025-01-16)


### Improvements

- Bumped ocean version to ^0.17.8


## 0.1.91 (2025-01-15)


### Improvements

- Bumped jinja version to 3.1.5


## 0.1.90 (2025-01-12)


### Improvements

- Bumped ocean version to ^0.17.7


## 0.1.89 (2025-01-08)


### Improvements

- Bumped ocean version to ^0.17.6


## 0.1.88 (2025-01-07)


### Improvements

- Bumped ocean version to ^0.17.5


## 0.1.87 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.4


## 0.1.86 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.3


## 0.1.85 (2024-12-31)


### Improvements

- Bumped ocean version to ^0.17.2


## 0.1.84 (2025-12-30)


### Improvements

- Added title to the configuration properties


## 0.1.83 (2024-12-29)


### Bug Fixes

- Fixed the issue with `get_current_resource_config()` and the `preserveApiResponseCaseStyle` selector in real-time event which leads to the failure of the event processing


## 0.1.82 (2024-12-26)


### Improvements

- Bumped ocean version to ^0.16.1


## 0.1.81 (2024-12-24)


### Improvements

- Bumped ocean version to ^0.16.0


## 0.1.80 (2024-12-22)


### Improvements

- Bumped ocean version to ^0.15.3


## 0.1.79 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.2


## 0.1.78 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.1


## 0.1.77 (2024-12-12)


### Improvements

- Bumped ocean version to ^0.15.0


## 0.1.76 (2024-12-09)


### Improvements

- Bumped ocean version to ^0.14.7
- Added `preserveApiResponseCaseStyle` selector to optionally convert resource fields to and from `snake_case` and `camelCase` for non-cloud asset APIs.


## 0.1.75 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.6


## 0.1.74 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.5


## 0.1.73 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.3


## 0.1.72 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.2


## 0.1.71 (2024-11-21)


### Improvements

- Bumped ocean version to ^0.14.1


## 0.1.70 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.14.0


## 0.1.69 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.13.1


## 0.1.68 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.13.0


## 0.1.67 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.12.9


## 0.1.66 (2024-11-06)


### Improvements

- Bumped ocean version to ^0.12.8


## 0.1.65 (2024-10-23)


### Improvements

- Bumped ocean version to ^0.12.7


## 0.1.64 (2024-10-22)


### Improvements

- Bumped ocean version to ^0.12.6


## 0.1.63 (2024-10-14)


### Improvements

- Bumped ocean version to ^0.12.4


## 0.1.62 (2024-10-09)


### Improvements

- Bumped ocean version to ^0.12.3


## 0.1.61 (2024-10-08)


### Improvements

- Bumped ocean version to ^0.12.2


## 0.1.60 (2024-10-01)


### Improvements

- Bumped ocean version to ^0.12.1


## 0.1.59 (2024-09-29)


### Improvements

- Bumped ocean version to ^0.11.0


## 0.1.58 (2024-09-22)


### Improvements

- Bumped ocean version to ^0.10.12


## 0.1.57 (2024-09-17)


### Improvements

- Bumped ocean version to ^0.10.11


## 0.1.56 (2024-09-15)


### Improvements

- Extracted the subscription from the asset inventory and added specific fetching via the GCP's SubscriberAPI.
- Changed realtime's default non-specific behavior to rely on the asset's data in the feed.


## 0.1.55 (2024-09-12)


### Improvements

- Bumped ocean version to ^0.10.10 (#1)


## 0.1.54 (2024-09-06)


### Bug Fixes

- Added an alternative key `project_id` for retrieving the quota project id, preventing failure in identifying the associated GCP quota project when `quota_project_id` isn't present in configuration.
- Fixed bug causing failure in retrieving cloud asset quota from GCP.


## 0.1.53 (2024-09-05)


### Improvements

- Bumped ocean version to ^0.10.9 (#1)


## 0.1.52 (2024-09-04)


### Improvements

- Bumped ocean version to ^0.10.8 (#1)


## 0.1.51 (2024-09-04)


### Improvements

- Improved user experience when using GCP Quotas- Added validation and used environmental variables in order to get the information the integration needs to get the project + quota of that project.


## 0.1.50 (2024-09-01)


### Improvements

- Introduced AsyncGeneratorRetry, a custom retry mechanism designed to handle resource retrieval retries instead of individual page retries. This change addresses the recurring DEADLINE_EXCEEDED errors that occurred with GCP's AsyncRetry which works for page-based retries, significantly improving reliability in GCP integrations.
- Implemented a sophisticated rate limiting system based on quota levels, allowing for precise control over request limits per project, per service, and per quota.
- Added a `searchAllResourcesPerMinuteQuota` integration config for controlling the rate limit quota should the integration fail to query quota from GCP as stated in the last point. Default is 400


## 0.1.49 (2024-09-01)


### Improvements

- Bumped ocean version to ^0.10.7 (#1)


## 0.1.48 (2024-08-30)


### Improvements

- Bumped ocean version to ^0.10.5 (#1)


## 0.1.47 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.4 (#1)


## 0.1.46 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.3 (#1)


## 0.1.45 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.2 (#1)


## 0.1.44 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.1 (#1)


## 0.1.43 (2024-08-25)


### Improvements

- Changed tf module in order to detach provider creation from the module and QOL changes with the module (#1)


## 0.1.42 (2024-08-22)


### Improvements

- Bumped ocean version to ^0.10.0 (#1)


## 0.1.41 (2024-08-20)


### Improvements

- Bumped ocean version to ^0.9.14 (#1)


## 0.1.40 (2024-08-13)


### Improvements

- Added rate limit strategy to api calls


## 0.1.39 (2024-08-13)


### Improvements

- Bumped ocean version to ^0.9.13 (#1)


## 0.1.38 (2024-08-11)


### Improvements

- Bumped ocean version to ^0.9.12 (#1)


## 0.1.37 (2024-08-05)


### Improvements

- Bumped ocean version to ^0.9.11 (#1)


## 0.1.36 (2024-08-04)


### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.1.35 (2024-08-01)


### Improvements

- Added _target='blank' attribute to spec links to open a new browser tab instead of the current browser


## 0.1.34 (2024-07-31)


### Improvements

- Upgraded integration dependencies (#1)


## 0.1.33 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.1.32 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.1.31 (2024-07-24)


### Improvements

- Bumped ocean version to ^0.9.5


## 0.1.30 (2024-07-17)


### Improvements

- Added labels property to the default blueprint and mapping


## 0.1.29 (2024-07-10)


### Improvements

- Bumped ocean version to ^0.9.4 (#1)


## 0.1.28 (2024-07-09)


### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.1.27 (2024-07-07)


### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.1.26 (2024-06-23)


### Improvements

- Added support for default installation methods ( Helm, docker, githubworkflow and gitlabCI ) to improve ease of use (#1)


## 0.1.25 (2024-06-23)


### Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.1.24 (2024-06-19)


### Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.1.23 (2024-06-16)


### Improvements

- Updated spec.yaml indication that saas installation is not supported


## 0.1.22 (2024-06-16)


### Improvements

- Bumped ocean version to ^0.8.0 (#1)


## 0.1.21 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.20 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.19 (2024-06-10)


### Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.18 (2024-06-05)


### Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.17 (2024-06-03)


### Bug Fixes

- Bump terraform provider version to 0.0.25 (#1)
- Change Service icon to Microservice (#2)


## 0.1.16 (2024-06-03)


### Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.15 (2024-06-02)


### Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.14 (2024-05-30)


### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


## 0.1.13 (2024-05-29)


### Improvements

- Bumped ocean version to ^0.5.22 (#1)


## 0.1.12 (2024-05-26)


### Improvements

- Bumped ocean version to ^0.5.21 (#1)


## 0.1.11 (2024-05-26)


### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


## 0.1.10 (2024-05-23)


### Breaking Changes

- Updated the returned response from the GCP integration to reflect the latest known resource version as identified by the GCP Asset Inventory. Removed the need for `.versioned_resources | max_by(.version).resource | .<property_name>`, now only requiring `.<property_name>` (#1)

## 0.1.9 (2024-05-22)


### Improvements

- Replaced GCP tf variable names to more readable ones (#1)


## 0.1.8 (2024-05-22)


### Bug Fixes

- Fixed single resource fetching for Topics, Projects, Folders and Organizations by fixing ids parsing (#1)


## 0.1.7 (2024-05-16)


### Improvements

- Bumped ocean version to ^0.5.19 (#1)


## 0.1.6 (2024-05-12)


### Improvements

- Bumped ocean version to ^0.5.18 (#1)


## 0.1.5 (2024-05-02)


### Features

- Added Terraform deployment method as main deployment method (#1)
- Added logs for Project/Folder/Org Injestion (#1)

## 0.1.4 (2024-05-01)


### Improvements

- Bumped ocean version to ^0.5.17 (#1)


## 0.1.3 (2024-05-01)


### Improvements

- Bumped ocean version to ^0.5.16 (#1)


## 0.1.2 (2024-04-30)


### Improvements

- Bumped ocean version to ^0.5.15 (#1)


## 0.1.1 (2024-04-24)


### Improvements

- Bumped ocean version to ^0.5.14 (#1)


## 0.1.0 (2024-04-22)


### Features

- Created GCP integration using Ocean (PORT-6501)
