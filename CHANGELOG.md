# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

0.1.1 (2023-07-26)
==================

### Breaking Changes

- Changed SAMPLE event listener to POLLING. (Make sure to update your eventListener.type field in your config.yaml for the integration) (PORT-4346)

### Improvements

- Seperated the cli commands to multiple files under the `port_ocean/cli/commands folder` (PORT-4303)
- Improved error messages from the PortClient (PORT-4337)

### Bug Fixes

- Fixed Webhook event listener not triggering
- Fixed PortClient using httpx async client from another event loop

  (PORT-4306)
- Fixed `ocean new` jinja crash for the config.yaml in the scaffold (PORT-4328)
- Fixed issue where the integration did not create the integration config on creation (PORT-4341)
- Fixed an issue with initializePortResources that caused failure for unknown file nmaes on init (PORT-4343)


0.1.0 (2023-07-20)
==================

### Features

- ### First version changelog

  #### Added
  - Handlers
    - Added entities state applier first port HTTP implementation.
    - Added entity processor first jq implementation.
    - Added port app config first port HTTP implementation.
  
  - Event Listeners
    - Added KAFKA event listener.
    - Added SAMPLE event listener.
    - Added WEBHOOK event listener.

  - Core
    - Added Ocean contexts & contexts global variables.
    - Added validation to the integration config according to its `.port/spec.yaml`.
    - Added a way to specify default resources to be created on installation.
    - Added a new way to return data from the resync using generators.
    - Added provider-based injection for the config yaml.
  
  - CLI
    - Added `ocean list` to list all public integrations in the port-ocean repo.
    - Added `ocean new` to scaffold an Ocean project.
    - Added `ocean pull` to pull one of the public integrations from the port-ocean repo.
    - Added `ocean sail` to run the integration.
    - Added `ocean version` to get the framework version.
    - Added `make new` to scaffold in the Ocean repository.

  (PORT-4307)
