# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.12.7 (2024-10-23)


### Bug Fixes

- Fixed get_integration_ocean_app test fixture configuration injection (0.12.7)


## 0.12.6 (2024-10-20)


### Bug Fixes

- Fixed get_integration_resource_config assumption for port-app-config files to be of .yaml extension only (0.12.6)


## 0.12.5 (2024-10-21)


### Bug Fixes

- Fixed get_integration_resource_config assumption for port-app-config files to be of .yml extension only (0.12.5)


## 0.12.3 (2024-10-09)

### Improvements

- Updated docker base image to improve security vulnerabilities


## 0.12.2 (2024-10-06)

### Improvements

- Added a util `semaphore_async_iterator` to enable seamless control over concurrent executions.


## 0.12.1 (2024-10-02)

### Bug Fixes

- Fixed a bug when running jq with iterator that caused the integration to crash
- Reverted image to `python:3.11-slim-buster` to fix the issue with the alpine image

## 0.12.0 (2024-10-01)

### Improvements

- Replace `python:3.11-slim-bookworm` with `python:3.11-alpine` to reduce dependencies and fix vulnerabilities

### Bug Fixes

- Fixed smoke tests to run concurrently and clean up after themselves

## 0.11.0 (2024-09-29)

### Improvements

- Replace pyjq with jq.py to bump jq version from 1.5.2 to 1.7.1

## 0.10.12 (2024-09-19)

### Bug Fixes

- Fixed updating state of resync when the resync is being cancelled by a new resync event

## 0.10.11 (2024-09-17)

### Improvements

- Add smoke test with a live integration to validate core changes

## 0.10.10 (2024-09-12)

### Bug Fixes

- Fixed failing on initialization of the integration when one of the actions exists in port

### Improvements

- Added fix lint command to the makefile as well as the pre-commit hook


## 0.10.9 (2024-09-05)

### Bug Fixes

- Replaced StopAsyncIteration with a return statement to ignore prevent errors in cases where empty tasks are sent to the stream_async_iterators_tasks function


## 0.10.8 (2024-09-04)

### Bug Fixes

- Avoid raising exception when receiving ReadTimeout on batch upsert entities
- Increased both internal port client and third party client timeout to handle long requests


## 0.10.7 (2024-08-28)

### Improvements

- Add search identifier support (Allow to run a search query to find the identifier of the entity as part of the mapping)


## 0.10.6 (2024-08-31)

### Bug Fixes

- Fixed error log when looking for existence of integration on initialization


## 0.10.5 (2024-08-27)

### Improvements

- Test support and helpers


## 0.10.4 (2024-08-28)

### Bug Fixes

- Fixed upsert entity failure when saving modified data for search relations calculations


## 0.10.3 (2024-08-28)

### Bug Fixes

- Bugfix Semaphores get fail when moving to the next scheduled resync when syncing a large number of entities, using a single event loop for all threads


## 0.10.2 (2024-08-26)

### Bug Fixes

- Reverted last bugfix


## 0.10.1 (2024-08-26)

### Bug Fixes

- Fixed unhashable type: 'dict' error when trying to delete entities with search identifier/relations


## 0.10.0 (2024-08-19)

### Improvements

- Add support for reporting the integration resync state to expose more information about the integration state in the portal
- Fix kafka listener never ending resync loop due to resyncState updates


## 0.9.14 (2024-08-19)

### Bug Fixes

- Fixed an issue causing the cli to fail in a directory with no pyproject.toml in it


## 0.9.13 (2024-08-13)

### Improvements

- Changed action CREATE route to use new v2 option


## 0.9.12 (2024-08-06)

### Bug Fixes

- Fixed resync issue when calculating the diff of entities failed due to search identifier in relation mapping


## 0.9.11 (2024-08-05)


### Bug Fixes

- Not showing misleading error message if port state is empty

## 0.9.10 (2024-08-04)


### Bug Fixes

- Fixed & Aligned scaffolding files


## 0.9.9 (2024-08-04)


### Bug Fixes

- Fixed an issue where passing an object for OCEAN__INTEGRATION__CONFIG that holds an object might not be parsed correctly and cause validation error for invalid type (#1)


## 0.9.8 (2024-08-01)


### Bug Fixes

- Fixed an issue where a `ValueError` was raised in `unregister_raw` method due to incorrect unpacking of results from asyncio.gather. The fix involved using zip to properly handle the output and ensure both entities and errors are processed correctly.


## 0.9.7 (2024-07-31)


### Bug Fixes

- Fix vulnerabilities and bump versions of dependencies
- Add python-dateutil to the core dependencies
- Fix misspelling in the `bump-all.sh` script


## 0.9.6 (2024-07-30)


### Bug Fixes

- Flush all remaining buffered logs when exiting application


## 0.9.5 (2024-07-23)


### Bug Fixes

- Initialize missing _port_app_config


## 0.9.4 (2024-07-09)


### Bug Fixes

- Handle non existing config mapping for cases where the integration was created by SAAS and the config mapping was not set


## 0.9.3 (2024-07-08)


### Improvements

- Added Ocean integration config to remove all environment variables from jq access
- Added log for when receiving invalid port app config mapping

## 0.9.2 (2024-07-05)


### Improvements

- Added log of the used integration mapping for each resync event
- Added log when failed on processing jq mapping for raw result

### Bug Fixes

- Fixed an issue where raw results were not being sent if raw data didn't map to any entity


## 0.9.1 (2024-06-23)


### Bug Fixes

- Safely get changelogDestination key instead of accessing it directly


## 0.9.0 (2024-06-19)


### Features

- Added validation of whether the integration can run in the desired runtime


## 0.8.0 (2024-06-16)


### Improvements

- Add search relation support (Allow to to run a search query to find the relation to the entity as part of the mapping)


## 0.7.1 (2024-06-13)


### Bug Fixes

- Fixed values unpack error in register_raw


## 0.7.0 (2024-06-13)


### Improvements

- Added pydantic's dotenv extra to the core dependencies for reading .env files on the integration startup
- Added .python-version to the repository for easier setup with pyenv install


## 0.6.0 (2024-06-10)


### Improvements

- Changed initialization to always apply default mapping if no other mapping is configured


## 0.5.27 (2024-06-05)


### Bug Fixes

- Fixed incorrect pydantic validation over the integration settings


## 0.5.26 (2024-06-04)


### Bug Fixes

- Fixed an issue causing integrations with no configuration to fail during the initialization process


## 0.5.25 (2024-06-03)


### Bug Fixes

- Fixed faulty error handling caused by gather_and_split_errors_from_results raising errors that are not directly under BaseException (#1)


## 0.5.24 (2024-06-02)


### Improvements

- Improved exception propagation for the entity processing (#1)
- QOL utility (`core.utils.gather_and_split_errors_from_results`) for when calling `asyncio.gather` with the `return_exceptions` parameter set to `True` and there is need for separating the errors from the data itself (#2)

### Bug Fixes

- Fixed unhandled exceptions caused by the entity parsing, resulting in the integration freezing (#1)


## 0.5.23 (2024-05-30)


### Improvements

- Updated the base image used in the Dockerfile that is created during integration scaffolding from `python:3.11-slim-buster` to `python:3.11-slim-bookworm`

## 0.5.22 (2024-05-29)


### Bug Fixes

- Fixed an issue in `send_raw_data_examples` when there are slashes in integration kind


## 0.5.21 (2024-05-26)


### Features

- Added `send_raw_data_examples` integration config to allow sending raw data examples from the third party API to port (on resync), for testing and managing the integration mapping


## 0.5.20 (2024-05-26)


### Improvements

- Made config.yaml file optional in the integration setup process.
- Integration type is now determined by the name specified in the pyproject.toml file.
- Switched to using the FastAPI lifespan feature instead of the deprecated on_shutdown and on_start methods.

### Bug Fixes

- Fixed the FastAPI server staying stale after shutdown by using the FastAPI lifespan feature for handling shutdown signals, preventing override of the shutdown process.
- Fixed issue with integration continuing to run after shutdown by canceling the resync async generator task.


## 0.5.19 (2024-05-16)


### Improvements

- Added caching to port-app-config.yml retrieval from port api (only for live events)


## 0.5.18 (2024-05-12)


### Improvements

- Added a util function that allows to run multiple asynchronous tasks in a bounded way to prevent overload and memory issues
- Use that utility when calculating JQ mapping for raw entities



## 0.5.17 (2024-05-01)


### Bug Fixes

- Fixed an issue in creating a child event context from the parent context by removing an unnecessary line of code



## 0.5.16 (2024-05-01)


### Features

- Allowing override of parent event context in ocean's event context manager


## 0.5.15 (2024-04-30)


### Bug Fixes

- Fixed error in `register_raw` when there's no relevant mappings for a specific kind


## 0.5.14 (2024-04-24)


### Improvements

- Implemented real-time entity deletion exclusively for instances that haven't matched any selectors.
- Change the JQ calculation to process only identifier and blueprint for raw entities not selected during real-time events to only get the required data for the delete.

## 0.5.13 (2024-04-17)


### Features

- Delete entities that doesn't passed the selector on real time events


## 0.5.12 (2024-04-12)


### Features

- Added a util function that allows to iterate over a list of async iterators and stream the results of each iterator as they are available


## 0.5.11 (2024-04-11)


### Improvements

- Improved the handling of integration entities by adding retries and running it after the upsert to prevent blocking the resync
- Changed entities search timeout to 30 seconds to prevent blocking the resync

### Features

- Added a way to enable request retries for any request even if its request method is not part of the retryable methods


## 0.5.10 (2024-04-10)


### Bug Fixes

- Fixed application settings to be loaded from the environment variables

### Improvements

- Added integration version label to docker


## 0.5.9 (2024-03-30)


### Bug Fixes

- Fixed a bug where every time after the first token expiration, the framework didn't actually marked that the token got refreshed, causing the token to be refreshed every time when a request is made to Port. (#1)


## 0.5.8 (2024-03-27)


### Bug Fixes

- Fixed a bug in loguru which fails to deserialize an exceptions (#1)


## 0.5.7 (2024-03-20)


### Features

- Added the ability to map entities from raw array attributes by introducing `itemsToParse` key in the mapping configuration


## 0.5.6 (2024-03-17)


### Features

- Added array to possible integration configuration types (PORT-7262)


## 0.5.5 (2024-03-06)


### Bug Fixes

- Changed caching to detect changes in params of function (#1)


## 0.5.4 (2024-03-03)


### Bug Fixes

- Fixed an issue where a failure in the entity processing step might fail the whole resync (#1)


## 0.5.3 (2024-03-03)


### Improvements

- Cahnged the JQ Entity processor to work with async callss to allow better parallelism and async work (#1)


## 0.5.2 (2024-02-21)


### Bug Fixes

- Fixed an issue causing the integration to crash when passing a sensitive configuration with invalid regex characters due to a missing escaping (PORT-6836)


## 0.5.1 (2024-02-20)


### Features

- Added handling for kafka consumer empty partition assignment and shutting the application down with an error (PORT-5475)
- Added QOL decorator to help with caching the third party response (PORT-5475_2)

### Improvements

- Changed the Kafka consumer to run in the event loop in async instead of sync in another thread (PORT-5475)

### Bug Fixes

- Fixed an issue causing all the character to be redacted when passing empty string to a sensitive field


## 0.5.0 (2024-02-18)


### Features

- Added a method for ocean integration to redact sensitive information from the logs and automatically apply it to sensitive configurations and known sensitive patterns. (#1)
- Added an HTTP handler for Ocean logs to facilitate sending the logs to the Port. (#2)

### Improvements

- Seperated the `port_ocean.utils` file into multiple files within the `utils` folder to improve code organization. (#1)
- Changed the Ocean context to be a global variable instead of using Localstack, preventing the framework from re-initiating the context for each thread. (#2)

### Bug Fixes

- Fixed an issue where the event listener was causing the application to continue running even after receiving a termination signal. (#1)
- Fixed a bug that caused some termination signal handlers to not work by consolidating the signal listeners in a single class, as signals can only have one listener. (#2)


## 0.4.17 (2024-01-23)


### Features

- Added sonarcloud files for public integration scaffolding (PORT-6181)
- Replaced the `remove-docker` option from the `ocean new` cli with `private` & `public` flags (PORT-6181)


## 0.4.16 (2024-01-11)


### Improvements

- Increased the default timeout for requests to 3rd party targets to 30 seconds, and made it configurable (PORT-6074)


## 0.4.15 (2024-01-07)


### Bug Fixes

- Fixed issue causing app config with no team mapping to fail due the core using None when not set (PORT-5938)


## 0.4.14 (2024-01-07)


### Bug Fixes

- Fixed missing team parameter in the port app config model (PORT-5938)


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
