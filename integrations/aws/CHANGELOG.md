# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.94 (2025-02-04)


### Improvements

- Bumped ocean version to ^0.18.8


## 0.2.93 (2025-01-29)


### Improvements

- Bumped ocean version to ^0.18.6


## 0.2.92 (2025-01-28)


### Improvements

- Bumped ocean version to ^0.18.5


## 0.2.91 (2025-01-24)


### Bug Fixes

- Handled the `AWSOrganizationsNotInUseException` properly to avoid breaking the sync process when using accounts that does not belong to an organization.


## 0.2.90 (2025-01-23)


### Improvements

- Bumped ocean version to ^0.18.4


## 0.2.89 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.3


## 0.2.88 (2025-01-22)


### Improvements

- Bumped ocean version to ^0.18.2


## 0.2.87 (2025-01-21)


### Improvements

- Bumped ocean version to ^0.18.1


## 0.2.86 (2025-01-19)


### Improvements

- Bumped ocean version to ^0.18.0


## 0.2.85 (2025-01-16)


### Improvements

- Bumped ocean version to ^0.17.8


## 0.2.84 (2025-01-15)


### Improvements

- Bumped jinja version to 3.1.5


## 0.2.83 (2025-01-12)


### Improvements

- Bumped ocean version to ^0.17.7


## 0.2.82 (2025-01-10)


### Improvements

- Added rate limiting and concurrency management in resync_cloudcontrol function to handle AWS throttling more effectively.
- Improved memory issues by reducing calls to create new boto3 clients.


## 0.2.81 (2025-01-08)


### Bug Fixes

- Updated the serialized response to include valid custom property json key by accessing the StrEnum value properly.


## 0.2.80 (2025-01-08)


### Improvements

- Bumped ocean version to ^0.17.6


## 0.2.79 (2025-01-07)


### Improvements

- Bumped ocean version to ^0.17.5


## 0.2.78 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.4


## 0.2.77 (2025-01-02)


### Improvements

- Bumped ocean version to ^0.17.3


## 0.2.76 (2024-12-31)


### Improvements

- Bumped ocean version to ^0.17.2


## 0.2.75 (2024-12-30)


### Improvements

- Added title to the configuration properties


## 0.2.74 (2024-12-26)


### Improvements

- Bumped ocean version to ^0.16.1


## 0.2.73 (2024-12-24)


### Improvements

- Bumped ocean version to ^0.16.0


## 0.2.72 (2024-12-22)


### Improvements

- Bumped ocean version to ^0.15.3


## 0.2.71 (2024-12-16)


### Improvements

- Updated the aiohttp dependency to version 3.11.10, resolving known vulnerability issues with medium severity


## 0.2.70 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.2


## 0.2.69 (2024-12-15)


### Improvements

- Bumped ocean version to ^0.15.1


## 0.2.68 (2024-12-12)


### Improvements

- Bumped ocean version to ^0.15.0


## 0.2.67 (2024-12-10)


### Improvements

- Bumped ocean version to ^0.14.7


## 0.2.66 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.6


## 0.2.65 (2024-12-04)


### Improvements

- Bumped ocean version to ^0.14.5


## 0.2.64 (2024-11-27)


### Bug Fixes

- Fixed an issue where the region policy was not properly handled for global resources. Now, when a region policy is specified, it strictly adheres to the allowed regions only.


## 0.2.63 (2024-11-25)


### Bug Fixes

- Do not break delete entities when a region is not accessible


## 0.2.62 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.3


## 0.2.61 (2024-11-25)


### Improvements

- Bumped ocean version to ^0.14.2


## 0.2.60 (2024-11-21)


### Bug Fixes

- Fix an issue where the integration enters an endless loop on permission error when querying resources in a region without permission


## 0.2.59 (2024-11-21)


### Improvements

- Bumped ocean version to ^0.14.1


## 0.2.58 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.14.0


## 0.2.57 (2024-11-12)


### Improvements

- Bumped ocean version to ^0.13.1


## 0.2.56 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.13.0


## 0.2.55 (2024-11-10)


### Improvements

- Bumped ocean version to ^0.12.9


## 0.2.54 (2024-11-06)


### Improvements

- Bumped ocean version to ^0.12.8


## 0.2.53 (2024-10-31)


### Improvements

- Added the option to query resources from specific regions, configurable via the regionPolicy in the selector field of the mapping.
- Introduced `maximumConcurrentAccount` parameter to control the maximum number of accounts synced concurrently.

### Bug Fixes

- Skip missing resources in a region without interrupting sync across other regions.


## 0.2.52 (2024-10-30)


### Bug Fixes

-  Updated `joined_timestamp` mapping in AWS Organizations to comply with RFC3339 timestamp format by replacing the space delimiter with 'T' in the `JoinedTimestamp` field.


## 0.2.51 (2024-10-23)


### Improvements

- Bumped ocean version to ^0.12.7


## 0.2.50 (2024-10-22)


### Improvements

- Bumped ocean version to ^0.12.6


## 0.2.49 (2024-10-14)


### Improvements

- Removed iterative calls to the cache for tracking expiry, reducing the likelihood of a thundering herd problem.
- Enhanced semaphore implementation to properly limit concurrency across tasks, rather than within tasks, improving performance and resource utilization.


## 0.2.48 (2024-10-14)


### Improvements

- Bumped ocean version to ^0.12.4


## 0.2.47 (2024-10-09)


### Improvements

- Bumped ocean version to ^0.12.3


## 0.2.46 (2024-10-08)


### Improvements

- Bumped ocean version to ^0.12.2


## 0.2.45 (2024-10-01)


### Improvements

- Bumped ocean version to ^0.12.1


## 0.2.44 (2024-09-29)


### Improvements

- Bumped ocean version to ^0.11.0


## 0.2.43 (2024-09-18)


### Improvements

- Improved support for parralel fetching of aws account resources
- Fixed ExpiredTokenException by replacing event-based caching with a time-dependent caching mechanism. The new approach reassumes the role and refreshes session credentials when 80% of the session duration has been used, ensuring credentials are refreshed before expiry.


## 0.2.42 (2024-09-24)


### Bug Fixes

- Fixes an issue where `is_access_denied_exception` could raise an `AttributeError` if `e.response` is `None`.


## 0.2.41 (2024-09-22)


### Improvements

- Bumped ocean version to ^0.10.12


## 0.2.40 (2024-09-17)


### Improvements

- Bumped ocean version to ^0.10.11


## 0.2.39 (2024-09-12)


### Improvements

- Bumped ocean version to ^0.10.10 (#1)


## 0.2.38 (2024-09-05)


### Improvements

- Bumped ocean version to ^0.10.9 (#1)


## 0.2.37 (2024-09-04)


### Improvements

- Bumped ocean version to ^0.10.8 (#1)


## 0.2.36 (2024-09-01)


### Improvements

- Bumped ocean version to ^0.10.7 (#1)


## 0.2.35 (2024-08-30)


### Improvements

- Bumped ocean version to ^0.10.5 (#1)


## 0.2.34 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.4 (#1)


## 0.2.33 (2024-08-28)


### Improvements

- Bumped ocean version to ^0.10.3 (#1)


## 0.2.32 (2024-08-28)


### Improvements

- Fix typo in integrations/aws/integration.py


## 0.2.31 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.2 (#1)


## 0.2.30 (2024-08-26)


### Improvements

- Bumped ocean version to ^0.10.1 (#1)


## 0.2.29 (2024-08-22)


### Improvements

- Bumped ocean version to ^0.10.0 (#1)


## 0.2.28 (2024-08-20)


### Improvements

- Bumped ocean version to ^0.9.14 (#1)


## 0.2.27 (2024-08-13)


### Improvements

- Bumped ocean version to ^0.9.13 (#1)


## 0.2.26 (2024-08-11)


### Improvements

- Bumped ocean version to ^0.9.12 (#1)


# Port_Ocean 0.2.25 (2024-08-05)

### Improvements

- Add live events error handling

# Port_Ocean 0.2.24 (2024-08-05)

### Improvements

- Fix global resources not reading through all accounts


## 0.2.23 (2024-08-05)


### Improvements

- Bumped ocean version to ^0.9.11 (#1)


## 0.2.22 (2024-08-04)


### Improvements

- Bumped ocean version to ^0.9.10 (#1)


## 0.2.21 (2024-08-01)


###  Improvements

- Added _target='blank' attribute to spec links to open a new browser tab instead of the current browser


## 0.2.20 (2024-07-31)


###  Improvements

- Upgraded integration dependencies (#1)


## 0.2.19 (2024-07-31)


###  Improvements

- Bumped ocean version to ^0.9.7 (#1)


## 0.2.18 (2024-07-31)


### Improvements

- Bumped ocean version to ^0.9.6 (#1)


## 0.2.17 (2024-07-24)


### Improvements

- Bumped ocean version to ^0.9.5


## 0.2.16 (2024-07-16)


### Bug Fixes

- Add auto-discover for available regions in case global resources do not have permissions in default region
- Add access denied handler to STS:AssumeRole
- Add access denied handler to custom kind resync


## 0.2.15 (2024-07-12)


### Improvements

- Add logs to indicate the size of batches being fetched in each resync


## 0.2.14 (2024-07-11)


### Improvements

- Add access denied exception support (#1)

## 0.2.13 (2024-07-10)


### Improvements

- Bumped ocean version to ^0.9.4 (#1)


## 0.2.12 (2024-07-09)


### Improvements

- Fix default useGetResourceAPI property name (#1)
- Use by default the actual S3 Bucket region instead of default region used to fetch it (#2)

## 0.2.11 (2024-07-09)


### Improvements

- Bumped ocean version to ^0.9.3 (#1)


## 0.2.10 (2024-07-07)


### Improvements

- Bumped ocean version to ^0.9.2 (#1)


## 0.2.9 (2024-07-02)


### Bugfix

- Ensure default region for global resources (#1)


## 0.2.8 (2024-06-23)


### Improvements

- Added support for default installation methods ( Helm, docker, githubworkflow and gitlabCI ) to improve ease of use (#1)


## 0.2.7 (2024-06-23)


### Improvements

- Bumped ocean version to ^0.9.1 (#1)


## 0.2.6 (2024-06-19)


### Improvements

- Bumped ocean version to ^0.9.0 (#1)


## 0.2.5 (2024-06-17)


### Improvements

- Changed default mapping to include describeResources for resources which doesn't include tags by default from cloud control (#1)

## 0.2.4 (2024-06-17)


### Improvements

- Fix _aws_credentials overflow bug (#1)

## 0.2.3 (2024-06-17)


### Improvements

- Add missing backwards compatible kinds (#1)
- Fix NextToken is not valid bug (#2)
- Fix AWS rate-limit issues (#3)


## 0.2.2 (2024-06-16)


### Improvements

- Run all single describe in parallel (#1)

## 0.2.1 (2024-06-16)


### Improvements

- Updated spec.yaml indication that saas installation is not supported


## 0.2.0 (2024-06-16)


### Improvements

- Added support for "describeResource" mapping option (#1)


## 0.1.8 (2024-06-16)


### Improvements

- Bumped ocean version to ^0.8.0 (#1)



## 0.1.7 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.1 (#1)


## 0.1.6 (2024-06-13)


### Improvements

- Add support for syncing ACM certificates, AMI images and Cloudformation Stacks


## 0.1.5 (2024-06-13)


### Improvements

- Bumped ocean version to ^0.7.0 (#1)


## 0.1.4 (2024-06-10)


### Improvements

- Bumped ocean version to ^0.6.0 (#1)


## 0.1.3 (2024-06-05)


### Improvements

- Bumped ocean version to ^0.5.27 (#1)


## 0.1.2 (2024-06-03)


### Improvements

- Bumped ocean version to ^0.5.25 (#1)


## 0.1.1 (2024-06-02)


### Improvements

- Bumped ocean version to ^0.5.24 (#1)


## 0.1.0 (2024-05-30)


### Features

- Added AWS ocean integration [PORT-7056] (#0)
