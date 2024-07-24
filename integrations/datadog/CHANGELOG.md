# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.18 (2024-07-24)

### Improvements

- Bumped ocean version to ^0.9.5


# Port_Ocean 0.1.17 (2024-07-10)

### Improvements

- Bumped ocean version to ^0.9.4 (#1)


# Port_Ocean 0.1.16 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


# Port_Ocean 0.1.15 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


# Port_Ocean 0.1.14 (2024-07-04)

### Improvements

- Added support to fetch SLOs history back to 1 year ago (#1)

# Port_Ocean 0.1.13 (2024-07-01)

### Improvements

- Changed the way we handle concurrency from asyncio gather to use a queuing mechanism to reduce the chance of rate limit


# Port_Ocean 0.1.12 (2024-07-01)

### Improvements

- Added support for SLO history (#1)


### Bug Fixes

- Changed Target and Warning threshold to number instead of string in SLO blueprint (#2)


# Port_Ocean 0.1.11 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


# Port_Ocean 0.1.10 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


# Port_Ocean 0.1.9 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)


# Port_Ocean 0.1.8 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


# Port_Ocean 0.1.7 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


# Port_Ocean 0.1.6 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


# Port_Ocean 0.1.5 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


# Port_Ocean 0.1.4 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


# Port_Ocean 0.1.3 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


# Port_Ocean 0.1.2 (2024-05-30)

### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


# Port_Ocean 0.1.1 (2024-05-29)

### Improvements

- Bumped ocean version to ^0.5.22 (#1)


# 0.1.0 (2024-05-28)

### Features

- Implemented Datadog integration to bring host, monitor, service catalog and SLO entities (PORT-5633)
