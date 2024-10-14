# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

0.1.131 (2024-10-09)
====================

### Improvements

- Bumped ocean version to ^0.12.3


0.1.130 (2024-10-08)
====================

### Improvements

- Bumped ocean version to ^0.12.2


0.1.129 (2024-10-02)
====================

### Bug Fixes

- Removed keyset pagination parameters from the listing of repository tree so the application can paginate data using the standard page index and page size parameters in the AsyncFetcher.fetch_batch (0.1.129)


0.1.128 (2024-10-02)
====================

### Improvements

- Improved real time event handling and added more verbosity on event handling


0.1.127 (2024-10-01)
====================

### Improvements

- Bumped ocean version to ^0.12.1


0.1.126 (2024-09-29)
====================

### Improvements

- Bumped ocean version to ^0.11.0


0.1.125 (2024-09-25)
====================

### Improvements

- Added log for when file kind's project iteration found a relevant project, and for when the batch entirely isn't relevant


0.1.124 (2024-09-24)
====================

### Improvements

- Added more logs and implemented the webhook creation in async (0.1.124)


0.1.123 (2024-09-22)
====================

### Improvements

- Bumped ocean version to ^0.10.12


0.1.122 (2024-09-17)
====================

### Improvements

- Updated the webhook creation logic to recreate hooks for urls that are disabled by GitLab (0.1.122)


0.1.121 (2024-09-17)
====================

### Improvements

- Improved on the way the integration handles GitOps push events by using only files that have been changed in the push even rather than fetching the entire repository tree (0.1.121)


0.1.120 (2024-09-17)
====================

### Improvements

- Bumped ocean version to ^0.10.11


0.1.119 (2024-09-12)
====================

### Improvements

- Bumped ocean version to ^0.10.10 (#1)


0.1.118 (2024-09-05)
====================

### Improvements

- Bumped ocean version to ^0.10.9 (#1)


0.1.117 (2024-09-05)
====================

### Bugfixes

- Fixed case the project should be collected from the token but not from the repos specification (#1)
- Added log for empty pages of projects and didn't return them (#1)

0.1.116 (2024-09-04)
====================

### Improvements

- Bumped ocean version to ^0.10.8 (#1)


0.1.114 (2024-08-29)
====================

### Improvements

- Improved Resync performance for file-kind: Now will search if the project has a file-base name for the searched file-kind, and only after the metadata object gets filtered as relevant, we pull the file kind. (#1)
- Improved Resync stability using an aiolimiter to make sure calls to the Gitlab API aren't getting rate-limited, In a way that's not blocking the event loop (as Gitlab's way of handling a rate-limit is a time.sleep, which blocks the entire event loop)
- Improved verbosity for the resync, as more logs and pagination were taken place.
- Improved Real-time mechanism - now paginating through a file instead of waiting for Gitlab's api to return the entire repository tree.


0.1.115 (2024-09-01)
====================

### Improvements

- Bumped ocean version to ^0.10.7 (#1)


0.1.114 (2024-08-30)
====================

### Improvements

- Bumped ocean version to ^0.10.5 (#1)


0.1.113 (2024-08-28)
====================

### Improvements

- Bumped ocean version to ^0.10.4 (#1)


0.1.112 (2024-08-28)
====================

### Improvements

- Bumped ocean version to ^0.10.3 (#1)


0.1.111 (2024-08-26)
====================

### Improvements

- Bumped ocean version to ^0.10.2 (#1)


0.1.110 (2024-08-26)
====================

### Improvements

- Bumped ocean version to ^0.10.1 (#1)


0.1.109 (2024-08-22)
====================

### Improvements

- Bumped ocean version to ^0.10.0 (#1)


0.1.108 (2024-08-20)
====================

### Improvements

- Bumped ocean version to ^0.9.14 (#1)


0.1.107 (2024-08-19)
====================

### Bug Fixes

- Fixed merge requests and issue resync methods to use an async method of listing root groups to avoid blocking the event loop


0.1.106 (2024-08-19)
====================

### Bug Fixes

- Fixed an issue when we were still processing a file larger than the allowed file size
- Added more verbosity to the logs of the file kind


0.1.105 (2024-08-15)
===================

### Improvements

- Added description to configuration properties in spec.yaml (PORT-9538)


0.1.104 (2024-08-14)
====================

### Improvements

- Fixed issue with webhook not syncing repository languages


0.1.103 (2024-08-14)
====================

### Improvements

- Added support for exporting files


0.1.102 (2024-08-13)
====================

### Improvements

- Changed default action creation json to new v2 format


0.1.101 (2024-08-13)
====================

### Improvements

- Bumped ocean version to ^0.9.13 (#1)


0.1.100 (2024-08-11)
====================

### Improvements

- Bumped ocean version to ^0.9.12 (#1)


0.1.99 (2024-08-05)
===================

### Improvements

- Bumped ocean version to ^0.9.11 (#1)


0.1.98 (2024-08-04)
===================

### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.1.97 (2024-07-31)


### Improvements

- Upgraded integration dependencies (#1)


## 0.1.96 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.1.95 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.1.94 (2024-07-24)


### Improvements

- Bumped ocean version to ^0.9.5


## 0.1.93 (2024-07-23)


### Bug Fixes

- Search gitops file paths in all repo tree (added missing parameter)


## 0.1.92 (2024-07-23)


### Bug Fixes

- Search gitops file paths recursively


## 0.1.91 (2024-07-10)

### Improvements

- Bumped ocean version to ^0.9.4 (#1)


## 0.1.90 (2024-07-09)


### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.1.89 (2024-07-07)


### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.1.88 (2024-06-23)


### Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.1.87 (2024-06-19)


### Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.1.86 (2024-06-16)


### Improvements

- Bumped ocean version to ^0.8.0 (#1)


## 0.1.85 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.84 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.83 (2024-06-10)


### Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.82 (2024-06-05)


### Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.81 (2024-06-03)


### Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.80 (2024-06-02)


### Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.79 (2024-05-30)


### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


## 0.1.78 (2024-05-29)


### Improvements

- Bumped ocean version to ^0.5.22 (#1)


## 0.1.77 (2024-05-26)


### Improvements

- Bumped ocean version to ^0.5.21 (#1)


## 0.1.76 (2024-05-26)


### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


## 0.1.75 (2024-05-19)


### Bug Fixes

- Fixed webhooks responses timeouts to gitlab using queue to return immediate response


## 0.1.74 (2024-05-16)


### Improvements

- Bumped ocean version to ^0.5.19 (#1)


## 0.1.73 (2024-05-12)


### Improvements

- Bumped ocean version to ^0.5.18 (#1)


## 0.1.72 (2024-05-05)


### Improvements

- Added try-catch blocks to api endpoints

## 0.1.71 (2024-05-01)


### Improvements

- Bumped ocean version to ^0.5.17 (#1)


## 0.1.70 (2024-05-01)


### Improvements

- Bumped ocean version to ^0.5.16 (#1)


## 0.1.69 (2024-04-30)


### Improvements

- Bumped ocean version to ^0.5.15 (#1)


## 0.1.68 (2024-04-24)


### Improvements

- Bumped ocean version to ^0.5.14 (#1)


## 0.1.67 (2024-04-17)


### Improvements

- Bumped ocean version to ^0.5.12 (#1)


## 0.1.66 (2024-04-11)


### Improvements

- Bumped ocean version to ^0.5.11 (#1)


## 0.1.65 (2024-04-10)


### Improvements

- Bumped ocean version to ^0.5.10 (#1)


## 0.1.64 (2024-04-09)


### Features

- Added more logs in event handling and webhook creation (PORT-7600)


## 0.1.63 (2024-04-02)


### Features

- Added the ability to cofigure which events to listen to on group webhook (PORT-7417)


## 0.1.62 (2024-04-01)


### Improvements

- Bumped ocean version to ^0.5.9 (#1)


## 0.1.61 (2024-03-28)


### Improvements

- Bumped ocean version to ^0.5.8 (#1)


## 0.1.60 (2024-03-25)


### Features

- Changed listening to default branch unless mentioned otherwise in mapping (PORT-7141)


## 0.1.59 (2024-03-24)


### Bug Fixes

- Fix bug that could not run on startup when not configuring param tokenGroupsHooksOverridMapping (PORT-7326)


## 0.1.58 (2024-03-20)


### Features

- Added support for webhooks creation by specified groups through the config (PORT-7140)


## 0.1.57 (2024-03-20)


### Improvements

- Bumped ocean version to ^0.5.7 (#1)


## 0.1.56 (2024-03-17)


### Improvements

- Bumped ocean version to ^0.5.6 (#1)


## 0.1.55 (2024-03-06)


### Improvements

- Bumped ocean version to ^0.5.5 (#1)


## 0.1.54 (2024-03-03)


### Improvements

- Bumped ocean version to ^0.5.4 (#1)


## 0.1.53 (2024-03-03)


### Improvements

- Bumped ocean version to ^0.5.3 (#1)


## 0.1.52 (2024-02-21)


### Improvements

- Bumped ocean version to ^0.5.2 (#1)


## 0.1.51 (2024-02-20)


### Improvements

- Bumped ocean version to ^0.5.1 (#1)


## 0.1.50 (2024-02-18)


### Improvements

- Bumped ocean version to ^0.5.0 (#1)


## 0.1.49 (2024-01-23)


### Features

- Added group & subgroup webhook support (PORT-6229)

### Bug Fixes

- Fixed a bug when checking whether a group should be synced or not (#1)


## 0.1.48 (2024-01-23)


### Improvements

- Bumped ocean version to ^0.4.17 (#1)


## 0.1.47 (2024-01-12)


### Features

- Added group & subgroup resource support (#1)


## 0.1.46 (2024-01-11)


### Improvements

- Bumped ocean version to ^0.4.16 (#1)


## 0.1.45 (2024-01-07)


### Improvements

- Bumped ocean version to ^0.4.15 (#1)


## 0.1.44 (2024-01-07)


### Improvements

- Bumped ocean version to ^0.4.14 (#1)


## 0.1.43 (2024-01-04)


### Improvements

- Updated templates to have description in scorecard rules and pie charts (#1)


## 0.1.42 (2024-01-01)


### Features

- Added onboarding templates, including blueprints, scorecards, actions and pages (#1)

### Improvements

- Added special handling for project resync batch size to 10, to reduce the time it takes to show data in the UI (#3)


## 0.1.41 (2024-01-01)


### Improvements

- Bumped ocean version to ^0.4.13 (#1)

### Bug Fixes

- Fixed handling not found error when trying to get tree for commit sha of newly created project (#1)


## v0.1.40 (2023-12-27)


### Improvements

- Increased log verbosity for gitlab webhook bootstrap (#2)
- Added handling for fetching errors (PORT-5813)

### Bug Fixes

- Fixed 404 error when trying to get tree for commit sha of newly created project (#1)


## v0.1.39 (2023-12-25)


### Improvements

- Fix stale relation identifiers in default blueprints (PORT-5799)


## v0.1.38 (2023-12-24)


### Improvements

- Updated default blueprints and config mapping to include integration name as blueprint identifier prefix
- Bumped ocean version to ^0.4.12 (#1)


## 0.1.37 (2023-12-21)


### Improvements

- Bumped ocean version to ^0.4.11 (#1)


## 0.1.36 (2023-12-21)


### Improvements

- Bumped ocean version to ^0.4.10 (#1)


## 0.1.35 (2023-12-14)


### Improvements

- Bumped ocean version to ^0.4.8 (#1)


## 0.1.34 (2023-12-12)


### Improvements

- Added support for system hooks, this capability can be enabled using the useSystemHook flag. Enabling this capability will create system hooks instead of group webhooks (PORT-5220)


## 0.1.33 (2023-12-05)


### Improvements

- Bumped ocean version to ^0.4.7 (#1)


## 0.1.32 (2023-12-04)


### Improvements

- Bumped ocean version to ^0.4.6 (#1)


## 0.1.31 (2023-11-30)


### Improvements

- Bumped ocean version to ^0.4.5 (#1)


## 0.1.30 (2023-11-29)


### Improvements

- Bumped ocean version to ^0.4.4 (#1)


## 0.1.29 (2023-11-21)


### Improvements

- Bumped ocean version to ^0.4.3 (#1)


## 0.1.28 (2023-11-16)


### Improvements

- Aligned default resources and mapping with Port docs examples (#1)

## 0.1.27 (2023-11-08)


### Improvements

- Bumped ocean version to ^0.4.2 (#1)


## 0.1.26 (2023-11-07)


### Bug Fixes

- Fixed a bug caused status code 404 when trying to sync merge requests on hook event (#1)
- Fixed a bug that caused reading file with GitOps to fail (#2)
- Fixed a bug of type validation that caused skipping merge requests on resync (#3)


## 0.1.25 (2023-11-03)


### Improvements

- Bumped ocean version to ^0.4.1 (#1)


## 0.1.24 (2023-11-01)


### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener (#1)


## 0.1.23 (2023-10-30)


### Features

- Added support for project folders (PORT-5060)


## 0.1.22 (2023-10-30)


### Improvements

- Bumped ocean version to 0.3.2 (#1)


## 0.1.21 (2023-10-29)


### Features

- Added support for project languages (PORT-4749)


## 0.1.20 (2023-10-24)


### Bug Fixes

- Fixed wrong useage of project object when checking if it is included in the filter (PORT-5028)


## 0.1.19 (2023-10-11)


### Improvements

- Added more logs to the integration to indecate the current state better (PORT-4930)
- Added pagination to all integration exported types for better performance (PORt-4930)


## 0.1.18 (2023-10-02)

- Changed gitlab resync to async batch iteration (#1)


  # 0.1.17 (2023-09-27)

- Bumped ocean to version 0.3.1 (#1)


  # 0.1.16 (2023-09-13)

### Improvements

- Added owned & visibility flags to project configurations (#1)
- Masking token at the startup log (#2)
- Bumped Ocean to 0.3.0 (#3)

### Bug Fixes

- Fixed the default mapping so it will not fail with required relation


  # 0.1.15 (2023-09-04)

### Improvements

- Added more logs to gitops parsing errors (#1)

### Bug Fixes

- Fixed a bug that caused the gitops parsing to fail (#1)


  # 0.1.14 (2023-09-01)

### Bug Fixes

- Fixed an issue causing the push event listener to fail for a key error (#1)


  # 0.1.13 (2023-08-31)

### Bug Fixes

- Fixed an issue causing the push event listener to fail (#1)


  # 0.1.12 (2023-08-30)

### Improvements

- Updated the default microservice blueprint to be project blueprint (PORT-4555)


  # 0.1.11 (2023-08-30)

### Improvements

- Removed ingressRequired from the spec.yaml file (PORT-4527)
- Bumped Ocean to 0.2.3 (#1)


  # 0.1.10 (2023-08-29)

### Features

- Added support for search:// capability when parsing entities (PORT-4597)


  # 0.1.9 (2023-08-11)

### Improvements

- Made the webhook live events feature optional


  # 0.1.8 (2023-08-11)

### Improvements

- Optimized dockerfile to produce smaller images (PORT-4485)


  # 0.1.7 (2023-08-11)

### Improvements

- Upgraded ocean to version 0.2.2


  # 0.1.6 (2023-08-10)

### Improvements

- Implemented some performance enhancement by fetching only the open merge requests or merge request from the last 2 weeks & pipelines only from the last 2 weeks


  # 0.1.5 (2023-08-09)

### Improvements

- Upgraded ocean version to use the optimized `on_resync` generator


  # 0.1.4 (2023-07-27)

### Package Version Bump

- Changed the usage of the config according to ocean 0.1.2


  # 0.1.3 (2023-07-26)

### Bug Fixes

- Fixed the api issue that caused live events not to sync (PORT-4366)


  # 0.1.2 (2023-07-26)

### Package Version Bump

- Bump ocean framework to v0.1.1


  # 0.1.1 (2023-07-23)

### Breaking Changes

- Changed the mergeRequest kind to merge-request (PORT-4327)

### Bug Fixes

- Creating the gitlab webhook with more event triggers (job_events, pipeline_events, etc...) (PORT-4325)

  1.0.1 (2023-07-20)

### Features

- Implemented gitlab integration using ocean (PORT-4307)
