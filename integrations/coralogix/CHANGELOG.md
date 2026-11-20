# Changelog - Ocean - coralogix

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.3-beta (2026-11-19)


### Improvements

- Bumped ocean version to ^0.62.0


## 0.1.2-beta (2026-11-19)


### Improvements

- Bumped ocean version to ^0.61.8


## 0.1.1-beta (2026-11-19)


### Improvements

- Bumped ocean version to ^0.61.7


## 0.1.0-beta (2026-11-16)


### Features

- Initial Coralogix integration syncing APM services (RED metrics from span metrics), SLOs with compliance and error budget, alert definitions, and cases.
- Incremental resync for cases, using the created-at filter and the Ocean cursor. Other kinds stay on the full resync.
