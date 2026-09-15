# Changelog

All notable changes to this integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0-beta (2026-08-10)

### Features

- Initial beta release of the Sonatype Lifecycle (Nexus IQ Server) integration.
- Sync `organization`, `application`, `report` (per lifecycle stage),
  `policyViolation`, `component`, `vulnerability` (CVE), and `sourceControl`
  resources into Port.
- Surface open-source components with their licenses, CVEs (deduplicated across
  applications) and Sonatype's recommended fix/upgrade version via the Component
  Remediation API (opt-in per component).
- Link applications to GitHub repositories from IQ Source Control Management
  (`githubRepository` relation + component `repositoryIdentifier` mirror).
- Example configuration for linking Sonatype applications to an existing Port
  `service` blueprint.
- Real-time updates via Sonatype IQ webhooks (Application Evaluation and Policy
  Management events) with optional HMAC-SHA1 signature verification.
- Optional per-stage filtering for reports, violations and components.
