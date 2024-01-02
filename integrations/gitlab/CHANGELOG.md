# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

0.1.41 (2024-01-01)
===================

### Improvements

- Bumped ocean version to ^0.4.13 (#1)

### Bug Fixes

- Fixed handling not found error when trying to get tree for commit sha of newly created project (#1)


v0.1.40 (2023-12-27)
====================

### Improvements

- Increased log verbosity for gitlab webhook bootstrap (#2)
- Added handling for fetching errors (PORT-5813)

### Bug Fixes

- Fixed 404 error when trying to get tree for commit sha of newly created project (#1)


v0.1.39 (2023-12-25)
====================

### Improvements

- Fix stale relation identifiers in default blueprints (PORT-5799)


v0.1.38 (2023-12-24)
====================

### Improvements

- Updated default blueprints and config mapping to include integration name as blueprint identifier prefix
- Bumped ocean version to ^0.4.12 (#1)


0.1.37 (2023-12-21)
===================

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


0.1.36 (2023-12-21)
===================

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


0.1.35 (2023-12-14)
===================

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


0.1.34 (2023-12-12)

### Improvements

- Added support for system hooks, this capability can be enabled using the useSystemHook flag. Enabling this capability will create system hooks instead of group webhooks (PORT-5220)


0.1.33 (2023-12-05)
===================

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


0.1.32 (2023-12-04)
===================

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


0.1.31 (2023-11-30)
===================

### Improvements

- Bumped ocean version to ^0.4.5 (#1)


0.1.30 (2023-11-29)
===================

### Improvements

- Bumped ocean version to ^0.4.4 (#1)


0.1.29 (2023-11-21)
===================

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


0.1.28 (2023-11-16)
===================

### Improvements

- Aligned default resources and mapping with Port docs examples (#1)

0.1.27 (2023-11-08)
===================

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


0.1.26 (2023-11-07)
===================

### Bug Fixes

- Fixed a bug caused status code 404 when trying to sync merge requests on hook event (#1)
- Fixed a bug that caused reading file with GitOps to fail (#2)
- Fixed a bug of type validation that caused skipping merge requests on resync (#3)


0.1.25 (2023-11-03)
===================

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


0.1.24 (2023-11-01)
===================

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener (#1)


0.1.23 (2023-10-30)
===================

### Features

- Added support for project folders (PORT-5060)


0.1.22 (2023-10-30)
===================

### Improvements

- Bumped ocean version to 0.3.2 (#1)


0.1.21 (2023-10-29)
===================

### Features

- Added support for project languages (PORT-4749)


0.1.20 (2023-10-24)
===================

### Bug Fixes

- Fixed wrong useage of project object when checking if it is included in the filter (PORT-5028)


0.1.19 (2023-10-11)
===================

### Improvements

- Added more logs to the integration to indecate the current state better (PORT-4930)
- Added pagination to all integration exported types for better performance (PORt-4930)


# 0.1.18 (2023-10-02)

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
