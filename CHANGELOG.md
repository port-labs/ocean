# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.0 (2023-07-20)

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
  - Core
    - Added ocean contexts & contexts global variables.
    - Added validation to the integration config according to its spec.yaml.
    - Integration can specify default resources to be created on installation.
    - Added a new way to return data from the resync using generators.
    - Added provider-based injection for the config yaml.
  
  - CLI
    - Added ocean list for listing all public integrations in the port-ocean repo.
    - Added new command to the ocean CLI for scaffolding an ocean new project in a specific path.
    - Added make new for scaffolding in the repository.
    - Added ocean pull for pulling one of the public integrations from the port-ocean repo.
    - Introducing ocean sail command for running the integration.

  (PORT-4307)
