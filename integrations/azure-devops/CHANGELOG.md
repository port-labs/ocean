# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.43 (2024-07-24)

### Improvements

- Bumped ocean version to ^0.9.5


# Port_Ocean 0.1.41 (2024-07-18)

### Bug Fixes

- Fixed `visibility` property in mapping which had a typo and changed the default relation to required `false` to be more permissive 


# Port_Ocean 0.1.41 (2024-07-10)

### Improvements

- Set the `isProjectsLimited` paramater to True by default
- Revise the configuration parameters' descriptions.

# Port_Ocean 0.1.40 (2024-07-09)

### Improvements

- Added description to the integration configuration variables

# Port_Ocean 0.1.39 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


# Port_Ocean 0.1.38 (2024-07-08)

### Features

- Make webhook creation project-scoped by default

# Port_Ocean 0.1.37 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


# Port_Ocean 0.1.36 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


# Port_Ocean 0.1.35 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


# Port_Ocean 0.1.34 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)


# Port_Ocean 0.1.33 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


# Port_Ocean 0.1.32 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


# Port_Ocean 0.1.31 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


# Port_Ocean 0.1.30 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


# Port_Ocean 0.1.29 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


# Port_Ocean 0.1.28 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


# Port_Ocean 0.1.27 (2024-05-30)

### Improvements

- Bumped ocean version to ^0.5.23 (#1)
- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`


# Port_Ocean 0.1.26 (2024-05-29)

### Improvements

- Bumped ocean version to ^0.5.22 (#1)


# Port_Ocean 0.1.25 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.21 (#1)


# Port_Ocean 0.1.24 (2024-05-26)

### Improvements

- Bumped ocean version to ^0.5.20 (#1)
- Removed the config.yaml file due to unused overrides


# Port_Ocean 0.1.23 (2024-05-16)

### Improvements

- Bumped ocean version to ^0.5.19 (#1)


# Port_Ocean 0.1.22 (2024-05-15)

### Bug Fixes

- Fixed default relation mapping between service and project (#1)

# Port_Ocean 0.1.21 (2024-05-12)

### Improvements

- Bumped ocean version to ^0.5.18 (#1)


# Port_Ocean 0.1.20 (2024-05-10)

### Improvements

- Enhanced the jq functionality for both 'repository' and 'repository-policy' identifiers, automatically removing spaces and converting all characters to lowercase by default. (PORT-7916)


# Port_Ocean 0.1.19 (2024-05-08)

### Improvements

- Removed spaces from service identifier field (#1)


# Port_Ocean 0.1.18 (2024-05-08)

### Improvements

- Changed url to service from api url to remoteUrl (#1)


# Port_Ocean 0.1.17 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.17 (#1)


# Port_Ocean 0.1.16 (2024-05-01)

### Improvements

- Bumped ocean version to ^0.5.16 (#1)


# Port_Ocean 0.1.15 (2024-04-30)

### Improvements

- Bumped ocean version to ^0.5.15 (#1)


# Port_Ocean 0.1.14 (2024-04-24)

### Improvements

- Bumped ocean version to ^0.5.14 (#1)


# Port_Ocean 0.1.13 (2024-04-17)

### Improvements

- Bumped ocean version to ^0.5.12 (#1)


# Port_Ocean 0.1.12 (2024-04-15)

### Features

- Added project kind as well as relation between repo and project, to get the team mirror property (PORT-7573)


# Port_Ocean 0.1.11 (2024-04-15)

### Bug Fixes

- Made defaultBranch not required in the repository body when fetching repository policies


# Port_Ocean 0.1.10 (2024-04-11)

### Improvements

- Bumped ocean version to ^0.5.11 (#1)


# Port_Ocean 0.1.9 (2024-04-10)

### Improvements

- Bumped ocean version to ^0.5.10 (#1)


# Port_Ocean 0.1.8 (2024-04-01)

### Improvements

- Bumped ocean version to ^0.5.9 (#1)


# Port_Ocean 0.1.7 (2024-03-28)

### Improvements

- Bumped ocean version to ^0.5.8 (#1)


# Port_Ocean 0.1.6 (2024-03-20)

### Improvements

- Bumped ocean version to ^0.5.7 (#1)


# Port_Ocean 0.1.5 (2024-03-17)

### Improvements

- Bumped ocean version to ^0.5.6 (#1)


# Port_Ocean 0.1.4 (2024-03-07)

### Bug Fixes

- Fixed issue causing disabled repositories to fail resynchronization for pull requests, policies, and item content (#413)


# Port_Ocean 0.1.3 (2024-03-03)

### Improvements

- Bumped ocean version to ^0.5.4 (#1)


# 0.1.2 (2024-03-03)

### Improvements
- Fixed the default scorecard to match the rule

# 0.1.1 (2024-03-03)

### Bugs

- Fix compatibility issue with None type and operand "|"

# 0.1.0 (2024-03-03)

### Features

- Created Azure DevOps integration using Ocean (PORT-4585)

