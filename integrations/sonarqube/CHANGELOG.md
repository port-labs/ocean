# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.182 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.3


## 0.1.181 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.2


## 0.1.180 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.1


## 0.1.179 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.0


## 0.1.178 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.12


## 0.1.177 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.11


## 0.1.176 (2025-05-20)


### Improvements

- Bumped ocean version to ^0.22.10


## 0.1.175 (2025-05-19)


### Improvements

- Bumped ocean version to ^0.22.9


## 0.1.174 (2025-05-15)


### Improvements

- Bumped ocean version to ^0.22.8


## 0.1.173 (2025-05-12)


### Improvements

- Bumped ocean version to ^0.22.7


## 0.1.172 (2025-05-06)


### Improvements

- Bumped ocean version to ^0.22.6


## 0.1.171 (2025-04-25)


### Bug Fixes

- Added metrics selector for on-premise analysis to ensure explicit setting of required metricsKey.


## 0.1.170 (2025-04-27)

### Bug Fixes

- Resolved "h11 accepts some malformed Chunked-Encoding bodies" h11 vulnerability


### Improvements

- Bumped ocean version to ^0.22.5


## 0.1.169 (2025-04-15)


### Bug Fixes

- Fixed bug where the integration was trying to fetch more than 10,000 issues from SonarQube API


## 0.1.168 (2025-04-25)


### Bug Fixes

- Fixed handling of `base_url` and `app_host` to strip trailing slashes.
- Corrected `app_host=None` case to set `webhook_invoke_url` to an empty string.


## 0.1.167 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.4


## 0.1.166 (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.3


## 0.1.165 (2025-04-07)


### Improvements

- Bumped ocean version to ^0.22.2


## 0.1.164 (2025-04-03)


### Bug Fixes

- Fixed a bug where `projects_ga` kind wasn't passing `enrich_project=True`


## 0.1.163 (2025-04-03)


### Improvements

- Bumped ocean version to ^0.22.1


## 0.1.162 (2024-03-27)


### Improvements

- Transitioned live events management to ocean’s `LiveEventProcessorManager` to streamline processing


## 0.1.161 (2025-03-24)


### Improvements

- Bumped ocean version to ^0.22.0


## 0.1.160 (2025-03-13)


### Improvements

- Bumped ocean version to ^0.21.5


## 0.1.159 (2025-03-12)


### Improvements

- Bumped ocean version to ^0.21.4


## 0.1.158 (2025-03-10)


### Improvements

- Bumped ocean version to ^0.21.3


## 0.1.157 (2025-03-09)


### Improvements

- Bumped ocean version to ^0.21.1


## 0.1.156 (2025-03-03)


### Improvements

- Bumped ocean version to ^0.21.0


## 0.1.155 (2025-02-26)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.154 (2025-02-25)


### Improvements

- Bumped ocean version to ^0.20.4


## 0.1.153 (2025-02-24)


### Improvements

- Bumped ocean version to ^0.20.3


## 0.1.152 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.2


## 0.1.151 (2025-02-23)


### Improvements

- Bumped ocean version to ^0.20.1


## 0.1.150 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.20.0


## 0.1.149 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.3


## 0.1.148 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.2


## 0.1.147 (2025-02-19)


### Improvements

- Bumped ocean version to ^0.19.1


## 0.1.146 (2025-02-13)


### Improvements

- Bumped cryptography version to ^44.0.1


## 0.1.145 (2025-02-09)


### Improvements

- Bumped ocean version to ^0.18.9


## 0.1.144 (2025-02-04)


### Improvements

- Bumped ocean version to ^0.18.8


## 0.1.143 (2025-02-03)


### Improvements

- Bumped ocean version to ^0.18.6


## 0.1.142 (2025-01-29)


### Bug Fixes

- Fixed a bug where the global sonar_client loses its HTTP header context during scheduled resyncs, triggering 403 errors that ultimately leads to the unintended deletion of ingested entities


## 0.1.141 (2025-01-28)


### Improvements

- Bumped ocean version to ^0.18.5


## 0.1.140 (2025-01-23)


### Improvements

- Bumped ocean version to ^0.18.4


## 0.1.139 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.3


## 0.1.138 (2025-01-22)


### Improvements

- Updated mappings to have typed array items


## 0.1.137 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.2


## 0.1.136 (2025-01-21)


### Improvements

- Bumped ocean version to ^0.18.1


## 0.1.135 (2025-01-19)


### Improvements

- Bumped ocean version to ^0.18.0


## 0.1.134 (2025-01-16)


### Improvements

- Bumped ocean version to ^0.17.8


## 0.1.133 (2025-01-15)


### Improvements

- Bumped jinja version to 3.1.5


## 0.1.132 (2025-01-12)


### Improvements

- Bumped ocean version to ^0.17.7


## 0.1.131 (2025-01-08)


### Improvements

- Bumped ocean version to ^0.17.6


## 0.1.130 (2025-01-07)


### Improvements

- Bumped ocean version to ^0.17.5


## 0.1.129 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.4


## 0.1.128 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.3


## 0.1.127 (2024-12-31)


### Improvements

- Bumped ocean version to ^0.17.2


## 0.1.126 (2026-12-30)


### Improvements

- Added title to the configuration properties


## 0.1.125 (2024-12-26)


### Improvements

- Bumped ocean version to ^0.16.1


## 0.1.124 (2024-12-24)


### Improvements

- Bumped ocean version to ^0.16.0


## 0.1.123 (2024-12-24)


### Improvements

- Added __branches as project attribute in order to map project branches


## 0.1.122 (2024-12-23)


### Improvements

- Increased logs presence in integration
- Replaced calls to internal API for projects to GA version, making the use of internal APIs optional


### Bug Fixes

- Fixed a bug in the pagination logic to use total record count instead of response size, preventing early termination (0.1.121)


## 0.1.121 (2024-12-22)


### Improvements

- Bumped ocean version to ^0.15.3


## 0.1.120 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.2


## 0.1.119 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.1


## 0.1.118 (2024-12-12)


### Improvements

- Bumped ocean version to ^0.15.0


## 0.1.117 (2024-12-10)


### Improvements

- Bumped ocean version to ^0.14.7


## 0.1.116 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.6


## 0.1.115 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.5


## 0.1.114 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.3


## 0.1.113 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.2


## 0.1.112 (2024-11-21)


### Improvements

- Bumped ocean version to ^0.14.1


## 0.1.111 (2024-11-20)


### Bug Fixes

- Added defensive mechanism to fail the resyn event for the kind when no data is fetched from Sonar API

### Improvements

- Added more logs to track the request and response object made to the Sonar API


## 0.1.110 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.14.0


## 0.1.109 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.13.1


## 0.1.108 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.13.0


## 0.1.107 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.12.9


## 0.1.106 (2024-11-06)


### Improvements

- Bumped ocean version to ^0.12.8


## 0.1.105 (2024-10-29)


### Bug Fixes

- Fixed bug where issues/list API is not available for older SonarQube instance versions


## 0.1.104 (2024-10-23)


### Improvements

- Bumped ocean version to ^0.12.7


## 0.1.103 (2024-10-22)


### Improvements

- Bumped ocean version to ^0.12.6


## 0.1.102 (2024-10-21)


### Features

- Added support for portfolios (0.1.102)


## 0.1.101 (2024-10-14)


### Improvements

- Bumped ocean version to ^0.12.4


## 0.1.100 (2024-10-09)


### Improvements

- Bumped ocean version to ^0.12.3


## 0.1.99 (2024-10-08)


### Improvements

- Bumped ocean version to ^0.12.2


## 0.1.98 (2024-10-01)


### Improvements

- Bumped ocean version to ^0.12.1


## 0.1.97 (2024-09-29)


### Improvements

- Bumped ocean version to ^0.11.0


## 0.1.96 (2024-09-22)


### Improvements

- Bumped ocean version to ^0.10.12


## 0.1.95 (2024-09-19)


### Bug Fixes

- Added handling for 400 and 404 HTTP errors to allow the integration to continue processing other requests instead of crashing (0.1.95)


## 0.1.94 (2024-09-17)


### Improvements

- Bumped ocean version to ^0.10.11


## 0.1.93 (2024-09-12)


### Improvements

- Bumped ocean version to ^0.10.10 (#1)


## 0.1.92 (2024-09-05)


### Improvements

- Bumped ocean version to ^0.10.9 (#1)


## 0.1.91 (2024-09-04)


### Improvements

- Bumped ocean version to ^0.10.8 (#1)


## 0.1.90 (2024-09-01)


### Improvements

- Bumped ocean version to ^0.10.7 (#1)


## 0.1.89 (2024-08-30)


### Improvements

- Bumped ocean version to ^0.10.5 (#1)


## 0.1.88 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.4 (#1)


## 0.1.87 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.3 (#1)


## 0.1.86 (2024-08-26)


### Bug Fixes

- Fixed SonarQube client instantiation issue by using a singleton pattern to ensure a single shared instance, resolving bug where the client is unable to find the self.metrics


## 0.1.85 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.2 (#1)


## 0.1.84 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.1 (#1)


## 0.1.83 (2024-08-22)


### Improvements

- Bumped ocean version to ^0.10.0 (#1)


## 0.1.82 (2024-08-20)


### Improvements

- Bumped ocean version to ^0.9.14 (#1)


## 0.1.81 (2024-08-13)


### Improvements

- Bumped ocean version to ^0.9.13 (#1)


## 0.1.80 (2024-08-11)


### Improvements

- Bumped ocean version to ^0.9.12 (#1)


## 0.1.79 (2024-08-05)


### Improvements

- Bumped ocean version to ^0.9.11 (#1)


## 0.1.78 (2024-08-04)


### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.1.77 (2024-08-02)

### Improvements

- Added _target='blank' attribute to html links in the spec.yaml file to open a new browser tab instead of the current browser


## 0.1.76 (2024-08-01)

### Improvements

- Allow users to define their own Sonar project metric keys


## 0.1.75 (2024-07-31)

### Improvements

- Upgraded integration dependencies (#1)


## 0.1.74 (2024-07-31)

### Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.1.73 (2024-07-31)

### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.1.72 (2024-07-24)

### Improvements

- Bumped ocean version to ^0.9.5


## 0.1.71 (2024-07-22)

### Bug Fixes

- Added checks to ensure that api filters for projects are applied to only on-premise instance


## 0.1.70 (2024-07-22)

### Bug Fixes

- Added conditions to handle instances when the API response does not have pagination object


## 0.1.69 (2024-07-10)

### Improvements

- Bumped ocean version to ^0.9.4 (#1)


## 0.1.68 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.1.67 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.1.66 (2024-06-26)

### Improvements

- Updated the onpremise issue kind API endpoint from /search to /list to overcome the 10k limit imposed by SonarQube


## 0.1.65 (2024-06-25)

### Improvements

- Added quality gate status to the project blueprint


## 0.1.64 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.1.63 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.1.62 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)


## 0.1.61 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.60 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.59 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.58 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.57 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.56 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.55 (2024-06-02)

### Bug Fixes

- Fixed an error in the sonarqube client that was causing the integration to fail when setting up the webhooks for live events

### Improvements

- Updated the inheritance of the resource configs for better validations


## 0.1.54 (2024-05-30)

### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


## 0.1.53 (2024-05-29)

### Improvements

- Bumped ocean version to ^0.5.22 (#1)


## 0.1.52 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.21 (#1)


## 0.1.51 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


## 0.1.50 (2024-05-16)

### Improvements

- Added support for filtering SonarQube projects and issues


## 0.1.49 (2024-05-16)

### Improvements

- Bumped ocean version to ^0.5.19 (#1)


## 0.1.48 (2024-05-12)

### Improvements

- Bumped ocean version to ^0.5.18 (#1)


## 0.1.47 (2024-05-02)

### Bug Fixes

- Fixed an issue with the integration startup when the sanity-check return a non json response


## 0.1.46 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.17 (#1)


## 0.1.45 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.16 (#1)


## 0.1.44 (2024-04-30)

### Improvements

- Bumped ocean version to ^0.5.15 (#1)


## 0.1.43 (2024-04-24)

### Improvements

- Bumped ocean version to ^0.5.14 (#1)


## 0.1.42 (2024-04-17)

### Improvements

- Bumped ocean version to ^0.5.12 (#1)


## 0.1.41 (2024-04-11)

### Improvements

- Bumped ocean version to ^0.5.11 (#1)


## 0.1.40 (2024-04-10)

### Improvements

- Bumped ocean version to ^0.5.10 (#1)


## 0.1.39 (2024-04-01)

### Improvements

- Bumped ocean version to ^0.5.9 (#1)


## 0.1.38 (2024-03-28)

### Improvements

- Bumped ocean version to ^0.5.8 (#1)


## 0.1.37 (2024-03-20)

### Improvements

- Bumped ocean version to ^0.5.7 (#1)


## 0.1.36 (2024-03-17)

### Improvements

- Bumped ocean version to ^0.5.6 (#1)


## 0.1.35 (2024-03-06)

### Improvements

- Bumped ocean version to ^0.5.5 (#1)


## 0.1.34 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


## 0.1.33 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.3 (#1)


## 0.1.32 (2024-02-21)

### Features

- Added functionality for syncing Sonar onpremise analysis data using Pull Request and Measures API (#1)


## 0.1.31 (2024-02-21)

### Improvements

- Bumped ocean version to ^0.5.2 (#1)


## 0.1.30 (2024-02-20)

### Improvements

- Bumped ocean version to ^0.5.1 (#1)


## 0.1.29 (2024-02-18)

### Improvements

- Bumped ocean version to ^0.5.0 (#1)


## 0.1.28 (2024-02-15)

### Improvements

- Add Sonarqube component object sonarQube analysis data (PORT-6656)


## 0.1.27 (2024-02-04)

### Improvements

- Added aggregation properties to the sonar project resources of number of open critical issues and number of open blocker issues (#1)


## 0.1.26 (2024-01-23)

### Improvements

- Bumped ocean version to ^0.4.17 (#1)


## 0.1.25 (2024-01-11)

### Improvements

- Bumped ocean version to ^0.4.16 (#1)


## 0.1.24 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.15 (#1)


## 0.1.23 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.14 (#1)


## 0.1.22 (2024-01-01)

### Improvements

- Bumped ocean version to ^0.4.13 (#1)


## 0.1.21 (2023-12-24)

### Improvements

- Bumped ocean version to ^0.4.12 (#1)


## 0.1.20 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


## 0.1.19 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


## 0.1.18 (2023-12-14)

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


## 0.1.17 (2023-12-06)

### Bug Fixes

- Corrected SonarQube On-Premise authentication to resolve 401 error codes previously experienced by users. This fix now properly utilizes Basic authentication (#17)


## 0.1.16 (2023-12-05)

### Bug Fixes

- Update startup code to skip initializing integration resources when organization_id is not specified for SonarCloud. (#16)


## 0.1.15 (2023-12-05)

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


## 0.1.14 (2023-12-04)

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


## 0.1.13 (2023-11-30)

### Improvements

- Bumped ocean version to ^0.4.5 (#1)


## 0.1.12 (2023-11-29)

### Improvements

- Bumped ocean version to ^0.4.4 (#1)
- Changed the httpx client to be the ocean's client for better connection error handling and request retries


## 0.1.11 (2023-11-21)

### Improvements

- Added retry mechanism for sonarqube client (#1)

## 0.1.10 (2023-11-21)

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


## 0.1.9 (2023-11-08)

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


## 0.1.8 (2023-11-03)

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


## 0.1.7 (2023-11-01)

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener(#1)


## 0.1.6 (2023-10-29)

### Improvements

- Bumped ocean version to 0.3.2 (#1)


## 0.1.5 (2023-10-22)

### Features

- Added a sanity check for sonarqube to check the sonarqube instance is accessible before starting the integration (PORT4908)

### Improvements

- Updated integration default port app config to have the `createMissingRelatedEntities` & `deleteDependentEntities` turned on by default (PORT-4908)
- Change organizationId configuration to be optional for on prem installation (PORT-4908)
- Added more verbose logging for the http request errors returning from the sonarqube (PORT-4908)
- Updated integration default port app config to have the  &  turned on by default (PORT4908)

### Bug Fixes

- Changed the sonarqube api authentication to use basic auth for on prem installations (PORT-4908)


# Sonarqube 0.1.4 (2023-10-15)

### Improvements

- Changed print in the http error handling to log info


# Sonarqube 0.1.3 (2023-10-04)

### Improvements

- Skip analysis resync for onpremise Sonarqube (#3)


# Sonarqube 0.1.2 (2023-09-27)

### Improvements

- Bumped ocean to version 0.3.1 (#1)


# Sonarqube 0.1.1 (2023-09-13)

### Improvements

- Bumped ocean to 0.3.0 (#1)

# Sonarqube 0.1.0 (2023-08-09)

### Features

- Implemented Sonarqube integration using Ocean
