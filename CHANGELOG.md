# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.2 (2023-08-11)

### Bug Fixes

- Fixed an issue causing the config yaml providers to not be parsed


## 0.2.1 (2023-08-09)


### Bug Fixes

- Fixed an issue causing ocean to convert the integration config objects to camelized objects


## 0.2.0 (2023-08-09)


### Breaking Changes

- Updated the `on_resync` generator to use a list of items instead of a single item

### Improvements

- Changed default log level to `INFO`
- Changed the extra object messages log level from `INFO` to `DEBUG`
- Removed a wrongful error log at the integration installation that says the integration does not exists

### Bug Fixes

- Added support for many relations for the same entity (PORT-4379)
- Added the resource config to the event context (PORT-4398)
- Fixed lack of support for multiple relations (PORT-4411)
- Added traceback output to the integration resync method exception log (PORT-4422)
- Fixed an issue that caused the jq `None` values for relations to become a string with the value `"None"` instead of being interpreted as `null` in JSON


## 0.1.3 (2023-08-02)


### Bug Fixes

- Fixed an issue preventing the setup of an integration with config values passed exclusively as environment variables. This fix also enables the option to deploy an integration to AWS ECS using Terraform (PORT-4379)


## 0.1.2 (2023-07-27)


### Breaking Changes

- All integration configuration variables are now passed to the integration code in snake_case format
- Renamed `port_ocean.config.integration` -> `port_ocean.config.settings`

### Features

- All the settings can now be set using environment variables with prefix of `OCEAN__{The name of the field}` and `__` between nested fields
- The broker field in the kafka settings now has the Port production brokers as the default value

### Improvements

- Using pyhumps to automatically camelize the aliases of the settings

### Bug Fixes

- Fixed a crash when there are no resources in the port-app-config


## 0.1.1 (2023-07-26)


### Breaking Changes

- Changed SAMPLE event listener to POLLING. (Make sure to update your `eventListener.type` field in your `config.yaml` for the integration) (PORT-4346)

### Improvements

- Seperated the cli commands to multiple files under the `port_ocean/cli/commands` folder (PORT-4303)
- Improved error messages from the PortClient (PORT-4337)

### Bug Fixes

- Fixed Webhook event listener not triggering
- Fixed PortClient using httpx async client from another event loop

  (PORT-4306)
- Fixed `ocean new` jinja crash for the config.yaml in the scaffold (PORT-4328)
- Fixed issue where the integration did not create the integration config on creation (PORT-4341)
- Fixed an issue with initializePortResources that caused failure for unknown file names on init (PORT-4343)


## 0.1.0 (2023-07-20)


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
