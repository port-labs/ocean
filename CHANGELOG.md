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
