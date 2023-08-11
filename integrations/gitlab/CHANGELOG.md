# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

0.1.7 (2023-08-11)
==================

### Improvements

- Upgraded ocean to version 0.2.2


0.1.6 (2023-08-10)
==================

### Improvements

- Implemented some performance enhancement by fetching only the open merge requests or merge request from the last 2 weeks & pipelines only from the last 2 weeks


0.1.5 (2023-08-09)
==================

### Improvements

- Upgraded ocean version to use the optimized `on_resync` generator


0.1.4 (2023-07-27)
==================

### Package Version Bump

- Changed the usage of the config according to ocean 0.1.2


0.1.3 (2023-07-26)
==================

### Bug Fixes

- Fixed the api issue that caused live events not to sync (PORT-4366)


0.1.2 (2023-07-26)
==================

### Package Version Bump

- Bump ocean framework to v0.1.1


0.1.1 (2023-07-23)
==================

### Breaking Changes

- Changed the mergeRequest kind to merge-request (PORT-4327)

### Bug Fixes

- Creating the gitlab webhook with more event triggers (job_events, pipeline_events, etc...) (PORT-4325)


1.0.1 (2023-07-20)

### Features

- Implemented gitlab integration using ocean (PORT-4307)
