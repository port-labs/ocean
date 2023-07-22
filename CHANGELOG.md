# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

# Port_Ocean 0.1.0 (2023-07-20)

### Features

- ### First version changelog

  #### Added

  - Added entities state applier first port http implementation
  - Added entity processor first jq implementation
  - Integration can specify default resources to be created on installation
  - Added validation to the integration config according to its spec.yaml
  - Added KAFKA event listener
  - Added ocean contexts & contexts global variables
  - Added `ocean list` for listing all public integrations in port-ocean repo
  - Added new command to the ocean cli for scaffolding a `ocean new` project in path & `make new` for scaffolding in the repo
  - Added `ocean pull` for pulling one of the public integrations in port-ocean repo
  - Added `ocean sail` command for running the integration
  - Added port app config first port http implementation
  - Added a new way to return data from the resync using generators
  - Added SAMPLE event listener
  - Added spec.yaml to the scaffolding
  - Added provider based injection for the config yaml
  - Added WEBHOOK event listener

  (PORT-4307)
