# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->
# Port_Ocean 0.1.3 (2024-01-02)

### Features

- Added Support for Terraform Project (0.1.3)

### Improvements

- Fixed bug failing Terraform Workspaces sync (0.1.3)
- Introduced http_async_client for handling unexpected rate limit errors (0.1.3)

# Port_Ocean 0.1.2 (2024-01-01)

### Improvements

- Bumped ocean version to ^0.4.13 (#1)

# Port_Ocean 0.1.2 (2023-12-27)

### Features

- Allowing clients to pass the terraformCloudParameter for self hosted terraform cloud (PORT-5858)


# Port_Ocean 0.1.1 (2023-12-25)

### Improvement

- Removed the usage of terraform cloud host parameter

# Port_Ocean 0.1.0 (2023-12-25)

### Features

- Added terraform cloud ocean integration (0.1.0)
- created incoming webhook endpoint for ingesting runs (0.1.0)
- on startup, create terraform cloud webhook if not already created (0.1.0)