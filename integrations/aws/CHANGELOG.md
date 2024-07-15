# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.2.15 (2024-07-12)

### Improvements

- Add logs to indicate the size of batches being fetched in each resync


# Port_Ocean 0.2.14 (2024-07-11)

### Improvements

- Add access denied exception support (#1)

# Port_Ocean 0.2.13 (2024-07-10)

### Improvements

- Bumped ocean version to ^0.9.4 (#1)


# Port_Ocean 0.2.12 (2024-07-09)

### Improvements

- Fix default useGetResourceAPI property name (#1)
- Use by default the actual S3 Bucket region instead of default region used to fetch it (#2)

# Port_Ocean 0.2.11 (2024-07-09)

### Improvements

- Bumped ocean version to ^0.9.3 (#1)


# Port_Ocean 0.2.10 (2024-07-07)

### Improvements

- Bumped ocean version to ^0.9.2 (#1)


# Port_Ocean 0.2.9 (2024-07-02)

### Bugfix

- Ensure default region for global resources (#1)


# Port_Ocean 0.2.8 (2024-06-23)

### Improvements

- Added support for default installation methods ( Helm, docker, githubworkflow and gitlabCI ) to improve ease of use (#1)


# Port_Ocean 0.2.7 (2024-06-23)

### Improvements

- Bumped ocean version to ^0.9.1 (#1)


# Port_Ocean 0.2.6 (2024-06-19)

### Improvements

- Bumped ocean version to ^0.9.0 (#1)


# Port_Ocean 0.2.5 (2024-06-17)

### Improvements

- Changed default mapping to include describeResources for resources which doesn't include tags by default from cloud control (#1)

# Port_Ocean 0.2.4 (2024-06-17)

### Improvements

- Fix _aws_credentials overflow bug (#1)

# Port_Ocean 0.2.3 (2024-06-17)

### Improvements

- Add missing backwards compatible kinds (#1)
- Fix NextToken is not valid bug (#2)
- Fix AWS rate-limit issues (#3)


# Port_Ocean 0.2.2 (2024-06-16)

### Improvements

- Run all single describe in parallel (#1)

# Port_Ocean 0.2.1 (2024-06-16)

### Improvements

- Updated spec.yaml indication that saas installation is not supported


# Port_Ocean 0.2.0 (2024-06-16)

### Improvements

- Added support for "describeResource" mapping option (#1)


# Port_Ocean 0.1.8 (2024-06-16)

### Improvements

- Bumped ocean version to ^0.8.0 (#1)



# Port_Ocean 0.1.7 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.1 (#1)


# Port_Ocean 0.1.6 (2024-06-13)

### Improvements

- Add support for syncing ACM certificates, AMI images and Cloudformation Stacks


# Port_Ocean 0.1.5 (2024-06-13)

### Improvements

- Bumped ocean version to ^0.7.0 (#1)


# Port_Ocean 0.1.4 (2024-06-10)

### Improvements

- Bumped ocean version to ^0.6.0 (#1)


# Port_Ocean 0.1.3 (2024-06-05)

### Improvements

- Bumped ocean version to ^0.5.27 (#1)


# Port_Ocean 0.1.2 (2024-06-03)

### Improvements

- Bumped ocean version to ^0.5.25 (#1)


# Port_Ocean 0.1.1 (2024-06-02)

### Improvements

- Bumped ocean version to ^0.5.24 (#1)


# Port_Ocean 0.1.0 (2024-05-30)

### Features

- Added AWS ocean integration [PORT-7056] (#0)
