# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.22 (2024-01-01)

### Improvements

- Bumped ocean version to ^0.4.13 (#1)


# Port_Ocean 0.1.21 (2023-12-24)

### Improvements

- Bumped ocean version to ^0.4.12 (#1)


# Port_Ocean 0.1.20 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.11 (#1)


# Port_Ocean 0.1.19 (2023-12-21)

### Improvements

- Bumped ocean version to ^0.4.10 (#1)


# Port_Ocean 0.1.18 (2023-12-14)

### Improvements

- Bumped ocean version to ^0.4.8 (#1)


# Port_Ocean 0.1.17 (2023-12-06)

### Bug Fixes

- Corrected SonarQube On-Premise authentication to resolve 401 error codes previously experienced by users. This fix now properly utilizes Basic authentication (#17)


# Port_Ocean 0.1.16 (2023-12-05)

### Bug Fixes

- Update startup code to skip initializing integration resources when organization_id is not specified for SonarCloud. (#16)


# Port_Ocean 0.1.15 (2023-12-05)

### Improvements

- Bumped ocean version to ^0.4.7 (#1)


# Port_Ocean 0.1.14 (2023-12-04)

### Improvements

- Bumped ocean version to ^0.4.6 (#1)


# Port_Ocean 0.1.13 (2023-11-30)

### Improvements

- Bumped ocean version to ^0.4.5 (#1)


# Port_Ocean 0.1.12 (2023-11-29)

### Improvements

- Bumped ocean version to ^0.4.4 (#1)
- Changed the httpx client to be the ocean's client for better connection error handling and request retries


# Port_Ocean 0.1.11 (2023-11-21)

### Improvements

- Added retry mechanism for sonarqube client (#1)

# Port_Ocean 0.1.10 (2023-11-21)

### Improvements

- Bumped ocean version to ^0.4.3 (#1)


# Port_Ocean 0.1.9 (2023-11-08)

### Improvements

- Bumped ocean version to ^0.4.2 (#1)


# Port_Ocean 0.1.8 (2023-11-03)

### Improvements

- Bumped ocean version to ^0.4.1 (#1)


# Port_Ocean 0.1.7 (2023-11-01)

### Improvements

- Bumped ocean version to ^0.4.0 and handle ONCE event listener(#1)


# Port_Ocean 0.1.6 (2023-10-29)

### Improvements

- Bumped ocean version to 0.3.2 (#1)


# Port_Ocean 0.1.5 (2023-10-22)

### Features

- Added a sanity check for sonarqube to check the sonarqube instance is accessible before starting the integration (PORT4908)

### Improvements

- Updated integration default port app config to have the `createMissingRelatedEntities` & `deleteDependentEntities` turned on by default (PORT-4908)
- Change organizationId configuration to be optional for on prem installation (PORT-4908)
- Added more verbose logging for the http request errors returning from the sonarqube (PORT-4908)
- Updated integration default port app config to have the  &  turned on by default (PORT4908)

### Bug Fixes

- Changed the sonarqube api authentication to use basic auth for on prem installations (PORT-4908)


# Sonarqube 0.1.4 (2023-10-15)

### Improvements

- Changed print in the http error handling to log info


# Sonarqube 0.1.3 (2023-10-04)

### Improvements

- Skip analysis resync for onpremise Sonarqube (#3)


# Sonarqube 0.1.2 (2023-09-27)

### Improvements

- Bumped ocean to version 0.3.1 (#1)


# Sonarqube 0.1.1 (2023-09-13)

### Improvements

- Bumped ocean to 0.3.0 (#1)

# Sonarqube 0.1.0 (2023-08-09)

### Features

- Implemented Sonarqube integration using Ocean
