# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.28 (2023-12-24)

### Improvements

- Bumped ocean version to ^0.4.12 (#1)


# Port_Ocean 0.1.27 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


# Port_Ocean 0.1.26 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


# Port_Ocean 0.1.25 (2023-12-19)

### Features

- Added support for exporting PagerDuty schedules (#25)


# Port_Ocean 0.1.24 (2023-12-14)

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


# Port_Ocean 0.1.23 (2023-12-05)

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


# Port_Ocean 0.1.22 (2023-12-04)

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


# Port_Ocean 0.1.21 (2023-12-03)

### Bug Fixes

- Fixed an issue where get_oncall_users only returned 1 on call instead of everyone (#251)

# Port_Ocean 0.1.20 (2023-11-30)

### Improvements

- Bumped ocean version to ^0.4.5 (#1)


# Port_Ocean 0.1.19 (2023-11-29)

### Improvements

- Enhance oncalls API with detailed logging (#19)


# Port_Ocean 0.1.18 (2023-11-29)

### Improvements

- Bumped ocean version to ^0.4.4 (#1)
- Changed the httpx client to be the ocean's client for better connection error handling and request retries


# Port_Ocean 0.1.17 (2023-11-23)

### Improvements

- Added retry handler to the pagerduty client to handle connection errors and rate limiting (#1)


# Port_Ocean 0.1.16 (2023-11-23)

### Bug Fixes

- Fixed incomplete oncall list over the `Service` kind by adding pagination support to the request


# Port_Ocean 0.1.15 (2023-11-21)

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


# Port_Ocean 0.1.14 (2023-11-08)

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


# Port_Ocean 0.1.13 (2023-11-03)

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


# Port_Ocean 0.1.12 (2023-11-01)

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener (#1)


# Port_Ocean 0.1.11 (2023-10-29)

### Improvements

- Bumped ocean version to 0.3.2 (#1)


# Port_Ocean 0.1.10 (2023-10-18)

### Improvement

- Changed api query api_query_params key in the port configuration to apiQueryParams (PORT-4965)


# Port_Ocean 0.1.9 (2023-10-18)

### Features

- Extended api query abilities for services & incidents exporting (PORT-4965)

### Improvement

- Used async generator syntax to return exported kinds instead of waiting for all the data (PORT-4965)


# Port_Ocean 0.1.8 (2023-10-17)

### Bug Fixes

- Fixed default mapping for the oncall user (PORT-4964)


# Port_Ocean 0.1.7 (2023-09-27)

### Improvements

- Bumped ocean to version 0.3.1 (#1)

# Port_Ocean 0.1.5 (2023-08-29)

### Improvements

- Changed the `app_host` to not be required for the installation (PORT-4527)
- Bumped Ocean to 0.2.3 (#1)

# Port_Ocean 0.1.4 (2023-08-11)

### Improvements

- Optimized dockerfile to produce smaller images (PORT-4485)

# Port_Ocean 0.1.3 (2023-08-11)

### Improvements

- Upgraded ocean to version 0.2.2

# Port_Ocean 0.1.2 (2023-08-09)

### Improvements

- Integration syntax improvements

# Port_Ocean 0.1.1 (2023-08-07)

### Features

- Added oncall user and improved on service url (#1)

# Port_Ocean 0.1.0 (2023-07-30)

### Features

- Implemented Pagerduty integration using Ocean (#0)
