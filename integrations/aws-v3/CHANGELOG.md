# Changelog - Ocean - aws-v3

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 1.3.7-beta (2025-09-30)


### Features

- Add support for AWS::ECS::Service Kind


## 1.3.6-beta (2025-09-28)


### Bug Fixes

- Fixed a bug in the AWS Organization Account kind where the title property was incorrectly set to use "AccountName" instead of the correct "Name" property.


## 1.3.5-beta (2025-09-28)


### Improvements

- Bumped ocean version to ^0.28.11


## 1.3.4-beta (2025-09-25)


### Improvements

- Bumped ocean version to ^0.28.9


## 1.3.3-beta (2025-09-25)


### Improvements

- Bumped ocean version to ^0.28.8


## 1.3.2-beta (2025-09-18)


### Improvements

- Add docs and installation docs to the integration


## 1.3.1-beta (2025-09-17)


### Improvements

- Improve runtime complexity by processing accessible accounts concurrently


## 1.3.0-beta (2025-09-17)


### Features

- Add support for AWS::Organizations::Account Kind


## 1.2.2-beta (2025-09-17)


### Improvements

- Bumped ocean version to ^0.28.7


## 1.2.1-beta (2025-09-16)


### Improvements

- Bumped ocean version to ^0.28.5


## 1.2.0-beta (2025-09-09)


### Features

- Add support for AWS::Account:Info Kind

### Improvements

- Relate Existing resources to Account


## 1.1.2-beta (2025-09-10)


### Improvements

- Bumped ocean version to ^0.28.4


## 1.1.1-beta (2025-09-09)


### Features

- Add support for AWS::ECS:Cluster Kind


## 1.1.0-beta (2025-09-09)


### Features

- Add support for AWS::EC2:Instance Kind


## 1.0.4-beta (2025-09-07)


### Bug Fixes

- Removed unused and unimplemented properties from the S3 Bucket Default models.

### Improvements

- Refactored the architecture to natively support actions that operate on multiple identifiers.
- Introduced the ExtraContext property to store enrichment data separately, ensuring that models remain compliant with CloudFormation template requirements.
- Restricted S3 blueprints and mapping to include only the default action properties, ensuring consistency and removing any extraneous or unused fields.


## 1.0.3-beta (2025-09-08)


### Improvements

- Bumped ocean version to ^0.28.3


## 1.0.2-beta (2025-09-03)


### Features

- Added Support S3 Exporter


## 1.0.1-beta (2025-09-01)


### Improvements

- Renamed integration to AWS Hosted by Port
- Add disableDefaultInstallationMethods to the integration


## 1.0.0-beta (2025-08-31)


### Features

- Breaking changes: accountRoleArn -> accountRoleArns
- accountRoleArn is now used for both multi-account (using organizations) and single-account modes
- accountRoleArns is now used for multi-account mode for direct arn access


## 0.3.7-beta (2025-08-28)


### Improvements

- Add saas enabled to the integration


## 0.3.6-beta (2025-08-28)


### Improvements

- Publish aws-v3 initial version for closed beta


## 0.3.6-dev (2025-08-28)


### Improvements

- Bumped ocean version to ^0.28.2


## 0.3.5-dev (2025-08-27)


### Improvements

- Bumped ocean version to ^0.28.1


## 0.3.4-dev (2025-08-26)


### Improvements

- Add use_organizations flag to the integration


## 0.3.3-dev (2025-08-25)


### Improvements

- Bumped ocean version to ^0.28.0


## 0.3.2-dev (2025-08-24)


### Improvements

- Bumped ocean version to ^0.27.10


## 0.3.1-dev (2025-08-20)


### Improvements

- Bumped ocean version to ^0.27.9


## 0.3.0-dev (2025-08-19)


### Features

- Add support for AWS Organizations


## 0.2.10-dev (2025-08-18)


### Improvements

- Bumped ocean version to ^0.27.8


## 0.2.9-dev (2025-08-17)


### Improvements

- Bumped ocean version to ^0.27.7


## 0.2.8-dev (2025-08-13)


### Improvements

- Bumped ocean version to ^0.27.6


## 0.2.7-dev (2025-08-13)


### Improvements

- Bumped ocean version to ^0.27.5


## 0.2.6-dev (2025-08-11)


### Improvements

- Bumped ocean version to ^0.27.3


## 0.2.5-dev (2025-08-11)


### Improvements

- Bumped ocean version to ^0.27.2


## 0.2.4-dev (2025-08-07)


### Improvements

- Bumped ocean version to ^0.27.1


## 0.2.3-dev (2025-08-05)


### Improvements

- Bumped ocean version to ^0.27.0


## 0.2.2-dev (2025-08-04)


### Improvements

- Bumped ocean version to ^0.26.3


## 0.2.1-dev (2025-08-03)


### Improvements

- Bumped ocean version to ^0.26.2


## 0.2.0-dev (2025-07-20)


### Improvements

- Add assume role with web identity provider

## 0.1.2-dev (2025-07-20)


### Improvements

- Bumped ocean version to ^0.26.1


## 0.1.1-dev (2025-07-16)


### Bug Fixes

- Patch `ResyncStrategyFactory.create` in single-account and multi-account session tests to ensure full test isolation. This fixes test flakiness caused by reliance on global state and real factory logic in `TestGetAllAccountSessions` (in `test_session_factory.py`).


## 0.1.0-dev (2025-07-09)


### Features

- Introduced support for both multi-account and single-account resync strategies.
- Enabled authentication using static credentials and IAM roles.
- Removed the requirement for organization/root account-level permissions.
