---
sidebar_position: 1
slug: /
title: Ocean Overview
sidebar_label: 🌊 Ocean Overview
---

# 🌊 Ocean Overview

![Thumbnail](https://github.com/port-labs/ocean/blob/f61343caa69d886f8ffe48fe05326f7442bca294/assets/Thumbnail.jpg?raw=true)

## What is Ocean?

Ocean is an open source integration framework for [Port](https://getport.io). Ocean is meant to make it easy to connect Port with your existing infrastructure and 3rd-party tools.

Ocean does this by providing a streamlined interface to interact with Port, including abstractions and commonly required functionality to interact with [Port's REST API](https://api.getport.io/).

This out-of-the-box functionality greatly simplifies the process of writing a new integration for Port, because as a developer your only requirement is to implement the logic that will query your desired 3rd-party system.

This documentation is meant to describe two main use cases for the Ocean framework:

- Developing and contributing to Ocean's core, including its various abstractions and interfaces.
- Developing, contributing and using integrations built using Ocean.

### Why Ocean?

Port aims to be the hub for everything developers, platform, DevOps teams and other personas require in an organization, by providing an open developer portal. Because Port aims to be such a central element of an organization's R&D, it aims to truly be a virtual Port - providing a safe, organized and intuitive way to store data, enable visibility, provide self-service actions, and expose scorecards and insights.

To build on this goal, Port follows a theme of nautical elements, including in its own name, design, names of internal services and teams in the R&D department.

Following that theme, we wanted Ocean to be the ultimate framework to integrate Port with the rest of your environment, and make it easy to connect Port with your organization and infrastructure, in whichever way made sense to you. In a way, it is meant to open you an _Ocean_ of possibilities.

## How does Ocean work?

Ocean is made up of two distinct pieces:

- Ocean CLI - used to create boilerplate for new Ocean integrations, and to aid in their development.
- Ocean framework - provides common functionality and interfaces to make the development of new Port integrations faster and easier.

The following section explains specifically about the Ocean framework, to learn more about the Ocean CLI, refer to the [CLI](./framework/cli/cli.md) docs

### The Ocean framework

The Ocean framework provides a variety of features meant to make the development and deployment of integrations with Port easier.

The goal of Ocean is to provide a layer of abstraction for a multitude of common operations that any integration between Port and a 3rd-party service requires, some of the abstractions provided by the Ocean framework:

- Authentication with Port's REST API to make requests
- High-throughput ingestion of blueprints and entities into Port
- Application of JQ mapping to information received from 3rd-party services for ingestion into Port
- Sync and re-sync information from a 3rd-party service
- Support a multitude of connection modes to receive commands and requests from Port, to account for any network or security configuration:
  - Trigger by webhook from Port
  - Trigger by querying configuration from Port
  - Trigger by reading a message from a Kafka topic provided by Port
- Support a multitude of deployment methods to account for any environment, infrastructure or architecture:
  - Kubernetes (via helm)
  - AWS ECS (via Terraform module)
  - Azure Container App (via Terraform module)

To learn more about the tools and abstractions provided by the Ocean framework to make it easier to develop new integrations, refer to the [features](./framework/features/features.md) docs.

## How do integrations powered by the Ocean framework work?

Since Ocean provides so many abstractions and common functionality out-of-the-box, creating a new integration for Port, powered by the Ocean framework is as easy as:

1. Scaffolding a new integration
2. Defining the inputs required by the integration
3. Writing the business logic to query information from the 3rd-party service
4. Testing the integration locally
5. Opening a PR to the Port team via the [Port Ocean](https://github.com/port-labs/port-ocean) repository on GitHub
6. Done! once the PR is approved and merged, the new integration will appear for all users in the list of available data sources

Port encourages the community to contribute their own integrations, as well as improve existing integrations and the core of the Ocean framework itself.

## Next steps

- To view the list of integrations powered by the Ocean framework, refer to the [integrations library](./integrations-library/integrations-library.md) page
  - You can also take a look at the variety of integrations and methods to ingest data into Port at Port's [documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/)
- To start developing your own integration with Port, powered by the Ocean framework, refer to the [getting started](./getting-started/getting-started.md) page
