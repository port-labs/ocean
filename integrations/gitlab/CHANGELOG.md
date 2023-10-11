# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

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
