# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# 0.1.5 (2023-08-29)

### Improvements

- Bumped ocean from 0.2.1 to 0.2.3 (PORT-4527)


# 0.1.4 (2023-08-22)

### Bug Fixes

- Added event_grid_system_topic_name and event_grid_event_filter_list to the spec.yaml extra vars (#1)


# 0.1.3 (2023-08-22)

### Bug Fixes

- Fixed subscriptionID description in the spec.yaml


# 0.1.2 (2023-08-21)

### Bug Fixes

- Aligned the deployment method attribute in spec.yaml to our new terraform module architecture


# 0.1.1 (2023-08-20)

### Bug Fixes

- Removed capability to remove port entity on received event of resource deletion
- Changed deployment method to point to full terraform module path

# 0.1.0 (2023-08-13)

### Features

- Added Azure ocean integration [PORT-4351] (#0)
