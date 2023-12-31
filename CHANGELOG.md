# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.4.13 (2023-12-31)

### Features

- Added capability to create pages as part of the integration setup (PORT-5689)

### Improvements

- Added integration and blueprints existence check before creating default resources (#1)
- Added verbosity to diff deletion process after resync (#2)

## 0.4.12 (2023-12-22)


### Bug Fixes

- Fixed `ocean new` scaffolding error `'collections.OrderedDict object' has no attribute 'public_integration'` (PORT-5728)


## 0.4.11 (2023-12-21)

### Improvements

- Added handling for aggregation properties when initializing the integration, so it will patch the aggregation properties after creating the relations (PORT-5717)
- Changed entity property in the `portResourceConfig` to be required instead of optional, as we don't support creation of blueprints as part of the app config (PORT-4549)


## 0.4.10 (2023-12-21)


### Improvements

- Wrapped the httpx async client with implementation that overrides the default transport class with custom transport to apply all default httpx features that are ignored when passing a custom transport instance. This allows the missing behevior of the http [proxy environment variable](https://www.python-httpx.org/environment_variables/#proxies) (PORT-5676)
- Changed deprecated `poetry lock --check` in the make files to `poetry check` (PORT-5711)

### Bug Fixes

- Changed the way we upsert and delete bulk of entities from the catalog to be batched rather than spawning all requests at once


## 0.4.9 (2023-12-19)


### Improvements

- Added a way to create the integration without the Dockerfile and .dockerignore to use the global Docker files when scaffolding a new integration.


## 0.4.8 (2023-12-13)


### Bug Fixes

- Fixed the incorrect search of entities by datasource, which was causing entities from older versions not to be deleted. (PORT-5583)


## 0.4.7 (2023-12-05)


### Improvements

- Allowing POST requests for getting port tokens to be retryable (PORT-5442)

### Bug Fixes

- Changed the default limitations and timeouts for requests to Port in order to handle PoolTimeout error caused by a large amout of requests sent in parallel (PORT-5442)


## 0.4.6 (2023-12-04)


### Bug Fixes

- Fixed a bug that triggered the integration to update during the initialization process when the integration already existed and the organization lacked default blueprints (PORT-5378).
- Fixed an issue where setting integration type or identifier that contains a capital letter will not show the integration in the UI (PORT-5399)


## 0.4.5 (2023-11-30)


### Features

- Added handling for transport errors like connection timeout error for outbound requests from ocean integrations and core (PORT-5369)
- Changed port request option `merge` to be true by default (PORT-5396)

### Improvements

- Changed the port request options defaults to be constructed in the port app config model instead of setting the defaults in many places (PORT-5369)


## 0.4.4 (2023-11-29)


### Features

- Added a httpx client that recreate itself on new threads using localproxy & localstack bundled with the `RetryTransport` transport featured in 0.4.3 (PORT-5333)

### Improvements

- Added `TokenRetryTransport` to the port client httpx client to handle connection errors and create new access tokens when the token is expiring while requesting (PORT-5333)
- Removed the retry handler decorator from the port client. Now using the `TokenRetryTransport` (PORT-5333)
- Handled `CycleError` for cyclic dependency in entities with better error message and ocean exception class (PORT-5333)


## 0.4.3 (2023-11-09)

### Features

- Added `RetryTransport` as a helper for retrying requests that integrations can use (PORT-5161)

### Bug Fixes

- Fixed kafka consumer to poll messages asynchronously, to avoid max poll timeout when running long resyncs (PORT-5160)
- Fixed a bug where the expiration of a Port token is not properly handled (PORT-5161)
- Fixed a bug where the `retry_every` didn't count failed runs as repetitions (PORT-5161) 

## 0.4.2 (2023-11-04)

### Features

- Added the current integration version to the port requests for future features and better debugging (PORT-4310)

### Bug Fixes

- Added the `install/prod` command to the integration scaffold template as was intended (PORT-5107)
- Changed the serializing of the port app config so when initializing it there wont be any None or default values displayed in the UI (PORT-5108)

### Improvements

- Removed version field from the spec.yml in the scaffolded integration (Version will be taken from the pyproject.toml) (PORT-5107)
- Changed the integration type in spec.yml to be the integration slug when scaffolding a new integration (PORT-5107)
- Added more logs to the ocean package for better debugging of the integration (PORT-4780)
- Seperated `SyncRawMixin` from `SyncRawMixin` (moved `SyncRawMixin` to `core/integrations/mixins/sync_raw.py`)
- Improved code readability for `SyncRawMixin`


## 0.4.1 (2023-11-03)

### Bug Fixes

- Fixed the `initialize-port-resources` option in `ocean sail` to not be a flag.
- Changed default of `initialize-port-resources` to `true`.
- Catch all exceptions in the resync of ONCE event listener,to make sure the application will exit gracefully 


## 0.4.0 (2023-10-31)

### Features

- Added support for running ocean integrations once and new ocean sail options to support it. As part of it we added ImmediateEventListener.


## 0.3.2 (2023-10-29)

### Improvements

- createMissingRelatedEntities + deleteDependentEntities are now defaulted to true


## 0.3.1 (2023-09-27)

### Bug Fixes

- Fix missing user agent when apply default resources on initialization (PORT-4813)

## 0.3.0 (2023-09-06)

### Deprecations

- Removed the `batch_work_size` configuration. Integrations should use the async generator syntax instead (PORT-4616)

### Features

- Added support for a configurable resync interval for integrations (PORT-4616)
- Added a new feature that will abort a running resync if a new resync is attempting to start (PORT-4619)

### Improvements

- Changed the way an empty port app config is handled in the `PortAppConfig Handler` (PORT-4483)
- Added yaml linter (#1)
- Removed the Ocean version parameter from the integration scaffold template, the version is now queried directly from the Ocean framework library used by the integration (#2)
- Changed the publish integration workflow to get the integration version from the `pyproject.toml` file of the integration and not from the `spec.yml` file (#3)

### Bug Fixes

- Fixed a bug that rollbacked all blueprints instead of only those created during integration setup, when the setup encountered an issue with blueprint creation
- Fixed a bug that caused values that resulted with a falsy jq evaluation to convert them to null. The values will now be ingested using their proper falsy representation (0 as 0, empty array as empty array, false as false, etc.)
- Fixed the injections of parameters to the `config.yaml` file, the injected values will now be wrapped with `""` (#1)

## 0.2.3 (2023-08-17)

### Features

- Added the ability to create and clean the defaults of an integration using the following CLI commands: `ocean defaults dock` and `ocean defaults clean` (dock-clean-defaults)

### Improvements

- Optimized dockerfile to produce smaller images (PORT-4485)
- Changed default log level to INFO in the cli

### Bug Fixes

- Fixed an issue with loading the configuration from the environment variables if the config is a dictionary
- Move Resource Config Selector class to public
- Handled delete events from change log where there is no after

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
