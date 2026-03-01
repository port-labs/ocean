# Changelog - Ocean - harbor

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->
## [0.2.0] - 2025-10-14

### Added
- Authored end-to-end setup documentation covering configuration, filtering, webhook registration, and Harbor smoke tests.
- Published example Port `config.yaml` (`examples/config.sample.yaml`) together with Harbor blueprints (`harborProject`, `harborRepository`, `harborArtifact`, `harborUser`) and the matching mapping file for ingestion.

### Fixed
- Structured resync and webhook logs now include the Port organization identifier so multi-org environments can trace Harbor ingestion activity.
