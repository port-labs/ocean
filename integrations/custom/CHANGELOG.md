## 0.2.23-beta (2025-12-04)


### Improvements

- Bumped ocean version to ^0.30.7


## 0.2.22-beta (2025-12-03)


### Improvements

- Bumped ocean version to ^0.30.7


## 0.2.21-beta (2025-12-01)


### Improvements

- Bumped ocean version to ^0.30.6


## 0.2.20-beta (2025-11-27)


### Improvements

- Bumped ocean version to ^0.30.5


## 0.2.19-beta (2025-11-26)


### Improvements

- Bumped ocean version to ^0.30.4


## 0.2.18-beta (2025-11-25)


### Improvements

- Bumped ocean version to ^0.30.3


## 0.2.17-beta (2025-11-24)


### Improvements

- Bumped ocean version to ^0.30.2


## 0.2.16-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.30.1


## 0.2.15-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.30.0


## 0.2.14-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.29.10


## 0.2.13-beta (2025-11-20)


### Improvements

- Bumped ocean version to ^0.29.9


## 0.2.12-beta (2025-11-19)


### Improvements

- Bumped ocean version to ^0.29.8


# Changelog

All notable changes to the Custom integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.11-beta] - 2025-01-27

### Bug Fixes
- Fixed timeout configuration to use Ocean's core `client_timeout` capability directly - removed duplicate timeout parameter to fully leverage Ocean's core functionality
- Fixed SSL verification (`verify_ssl`) configuration not being properly applied to HTTP requests
- Fixed data path auto-detection logic to correctly handle explicit `data_path` configurations vs auto-detection scenarios

## [0.2.2] - 2025-04-11
### Improvements
Fixed docs shown in generic http integration


## [0.2.1] - 2025-03-11
### Improvements
Added docs to other installation methods in custom integration other than helm


## [0.1.0] - 2024-01-01

### Added
- Initial release of HTTP Server integration
- Support for multiple authentication methods (Bearer token, Basic auth, API key, none)
- Support for multiple pagination patterns (offset/limit, page/size, cursor-based, none)
- Configurable HTTP client with timeout and SSL verification settings
- Standard Ocean resource mapping with JQ transformations
- Automatic data extraction from common response formats
- Comprehensive error handling and logging
- Complete documentation and examples
