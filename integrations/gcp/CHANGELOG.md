# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.31 (2024-07-24)

### Improvements

- Bumped ocean version to ^0.9.5


# Port_Ocean 0.1.30 (2024-07-17)

### Improvements

- Added labels property to the default blueprint and mapping


# Port_Ocean 0.1.29 (2024-07-10)

### Improvements

- Bumped ocean version to ^0.9.4 (#1)


# Port_Ocean 0.1.28 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


# Port_Ocean 0.1.27 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


# Port_Ocean 0.1.26 (2024-06-23)

### Improvements

- Added support for default installation methods ( Helm, docker, githubworkflow and gitlabCI ) to improve ease of use (#1)


# Port_Ocean 0.1.25 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


# Port_Ocean 0.1.24 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


# Port_Ocean 0.1.23 (2024-06-16)

### Improvements

- Updated spec.yaml indication that saas installation is not supported


# Port_Ocean 0.1.22 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)


# Port_Ocean 0.1.21 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


# Port_Ocean 0.1.20 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


# Port_Ocean 0.1.19 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


# Port_Ocean 0.1.18 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


# Port_Ocean 0.1.17 (2024-06-03)

### Bug Fixes

- Bump terraform provider version to 0.0.25 (#1)
- Change Service icon to Microservice (#2)


# Port_Ocean 0.1.16 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


# Port_Ocean 0.1.15 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


# Port_Ocean 0.1.14 (2024-05-30)

### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


# Port_Ocean 0.1.13 (2024-05-29)

### Improvements

- Bumped ocean version to ^0.5.22 (#1)


# Port_Ocean 0.1.12 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.21 (#1)


# Port_Ocean 0.1.11 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


# Port_Ocean 0.1.10 (2024-05-23)

### Breaking Changes

- Updated the returned response from the GCP integration to reflect the latest known resource version as identified by the GCP Asset Inventory. Removed the need for `.versioned_resources | max_by(.version).resource | .<property_name>`, now only requiring `.<property_name>` (#1)

# Port_Ocean 0.1.9 (2024-05-22)

### Improvements

- Replaced GCP tf variable names to more readable ones (#1)


# Port_Ocean 0.1.8 (2024-05-22)

### Bug Fixes

- Fixed single resource fetching for Topics, Projects, Folders and Organizations by fixing ids parsing (#1)


# Port_Ocean 0.1.7 (2024-05-16)

### Improvements

- Bumped ocean version to ^0.5.19 (#1)


# Port_Ocean 0.1.6 (2024-05-12)

### Improvements

- Bumped ocean version to ^0.5.18 (#1)


# Port_Ocean 0.1.5 (2024-05-02)

### Features

- Added Terraform deployment method as main deployment method (#1)
- Added logs for Project/Folder/Org Injestion (#1)

# Port_Ocean 0.1.4 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.17 (#1)


# Port_Ocean 0.1.3 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.16 (#1)


# Port_Ocean 0.1.2 (2024-04-30)

### Improvements

- Bumped ocean version to ^0.5.15 (#1)


# Port_Ocean 0.1.1 (2024-04-24)

### Improvements

- Bumped ocean version to ^0.5.14 (#1)


# 0.1.0 (2024-04-22)

### Features

- Created GCP integration using Ocean (PORT-6501)
