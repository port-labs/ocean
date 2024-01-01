# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

0.1.23 (2024-01-01)

### Improvements

- Bumped ocean version to ^0.4.13 (#1)


v0.1.22 (2023-12-25)

### Improvements

- Fix stale relation identifiers in default blueprints (port-5799)


v0.1.21 (2023-12-24)

### Improvements

- Updated default blueprints and config mapping to include integration name as blueprint identifier prefix
- Bumped ocean version to ^0.4.12 (#1)


0.1.20 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


0.1.19 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


v0.1.18 (2023-12-20)

### Improvements

- Updated authentication method to use built-in basic auth function
- Added warning message when 0 issues or projects are queried from the Jira API


0.1.17 (2023-12-18)

### Improvements

- Updated the Jira issue blueprint by adding entity properties including created datetime, updated datetime and priority (#17)


0.1.16 (2023-12-14)

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


0.1.15 (2023-12-05)

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


0.1.14 (2023-12-04)

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


0.1.13 (2023-11-30)

### Improvements

- Bumped ocean version to ^0.4.5 (#1)
- Changed http client default timeout to 30 seconds


0.1.12 (2023-11-29)

### Improvements

- Bumped ocean version to ^0.4.4 (#1)
- Changed the httpx client to be the ocean's client for better connection error handling and request retries


0.1.11 (2023-11-21)

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


0.1.10 (2023-11-08)

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


0.1.9 (2023-11-03)

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


0.1.8 (2023-11-01)

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener (#1)


0.1.7 (2023-10-30)

### Improvements

- Fixed the default mapping to exclude issues with status `Done` (#1)


0.1.6 (2023-10-29)

### Improvements

- Bumped ocean version to 0.3.2 (#1)


0.1.5 (2023-09-27)

### Improvements

- Bumped ocean to version 0.3.1 (#1)

  0.1.4 (2023-09-13)

### Improvements

- Bumped ocean to 0.3.0 (#1)

  0.1.3 (2023-08-29)

### Improvements

- Changed the app_host to not be required for the installation (PORT-4527)
- Bumped Ocean to 0.2.3 (#1)

  0.1.2 (2023-08-11)

### Improvements

- Optimized dockerfile to produce smaller images (PORT-4485)

  0.1.1 (2023-08-11)

### Improvements

- Upgraded ocean to version 0.2.2

v0.1.0 (2023-08-10)

### Features

- Added Jira integration with support for projects and issues (PORT-4410)
