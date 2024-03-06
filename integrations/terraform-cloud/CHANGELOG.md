# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.15 (2024-03-06)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


# Port_Ocean 0.1.14 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


# Port_Ocean 0.1.13 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.3 (#1)


# Port_Ocean 0.1.12 (2024-02-21)

### Improvements

- Bumped ocean version to ^0.5.2 (#1)


# Port_Ocean 0.1.11 (2024-02-20)

### Improvements

- Bumped ocean version to ^0.5.1 (#1)


# Port_Ocean 0.1.10 (2024-02-18)

### Improvements

- Bumped ocean version to ^0.5.0 (#1)


# Port_Ocean 0.1.9 (2024-01-25)

### Bug Fixes

- Fixed a bug that prevented the creation of workspace webhooks especially when the notification configuration is set to enabled (PORT-6201)


# Port_Ocean 0.1.8 (2024-01-23)

### Improvements

- Bumped ocean version to ^0.4.17 (#1)


# Port_Ocean 0.1.7 (2024-01-11)

### Features

- Added support for Terraform Organization (PORT-5917)

### Improvements

- Added Tags to terraform cloud (PORT-6043)


# Port_Ocean 0.1.6 (2024-01-11)

### Improvements

- Bumped ocean version to ^0.4.16 (#1)


# Port_Ocean 0.1.5 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.15 (#1)


# Port_Ocean 0.1.4 (2024-01-07)

### Improvements

- Bumped ocean version to ^0.4.14 (#1)


# Port_Ocean 0.1.3 (2024-01-02)

### Features

- Added Support for Terraform Project (PORT-5876)

### Improvements

- Fixed bug failing Terraform Workspaces sync (#1)
- Introduced http_async_client for handling unexpected rate limit errors (#2)

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

- Added terraform cloud ocean integration  (#1)
- created incoming webhook endpoint for ingesting runs (#2)
- on startup, create terraform cloud webhook if not already created (#3)