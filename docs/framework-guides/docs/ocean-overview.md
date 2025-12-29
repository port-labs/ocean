---
sidebar_position: 1
slug: /
title: Overview
sidebar_label: 🌊 Overview
---

import OceanExporterArchSvg from '../static/img/ExportArchitecture.svg'
import OceanRealTimeArchSvg from
  '!@svgr/webpack?-svgo!../static/img/RealTimeUpdatesArchitecture.svg';

# Overview

![Thumbnail](https://raw.githubusercontent.com/port-labs/ocean/main/assets/Thumbnail.png)

<p align="center">
<a href="https://github.com/tiangolo/fastapi/actions?query=lint+event:push+branch:main" target="_blank" style={{marginRight: "0.5em"}}>
    <img src="https://github.com/port-labs/Port-Ocean/actions/workflows/lint.yml/badge.svg" alt="Lint" />
</a>
<a href="https://pypi.org/project/port-ocean" target="_blank" style={{marginRight: "0.5em"}}>
    <img src="https://img.shields.io/pypi/v/port-ocean?color=%2334D058&label=pypi%20package" alt="Package version"/>
</a>
<a href="https://pypi.org/project/port-ocean" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/port-ocean.svg?color=%2334D058" alt="Supported Python versions"/>
</a>
</p>

## What is Ocean?

Ocean is an open source extensibility framework for [Port](https://getport.io). Ocean is meant to make it easy to connect Port with your existing infrastructure and 3rd-party tools.

Ocean does this by providing a streamlined interface to interact with Port, including abstractions and commonly required functionality to interact with [Port's REST API](https://api.getport.io/).

This out-of-the-box functionality greatly simplifies the process of writing a new integration for Port, because as a developer your only requirement is to implement the logic that will query your desired 3rd-party system.

Port encourages members of its community to contribute their own integrations, as well as improve existing integrations and the core of the Ocean framework itself.

This documentation is meant to describe two main use cases for the Ocean framework:

- Developing and contributing to Ocean's core, including its various abstractions and interfaces.
- Developing, contributing and using integrations built using Ocean.

### Why Ocean?

Port aims to be the hub for everything developers, platform, DevOps teams and other personas require in an organization, by providing an open developer portal. Because Port aims to be such a central element of an organization's R&D, it aims to truly be a virtual Port - providing a safe, organized and intuitive way to store data, enable visibility, provide self-service actions, and expose scorecards, initiatives and insights.

To build on this goal, Port follows a theme of nautical elements, including in its name, design, names of internal services and teams in the R&D department.

Following that theme, we wanted Ocean to be the ultimate framework to integrate Port with the rest of your environment, and make it easy to connect Port with your organization and infrastructure, in whichever way made sense to you. In a way, Ocean opens an _Ocean_ of possibilities (pun intended).

## How does Ocean work?

Ocean is made up of two distinct pieces:

- Ocean CLI - used to create boilerplates for new Ocean integrations, and to aid in their development.
- The Ocean Framework - provides common functionalities and interfaces to make the development of new Port integrations faster and easier.

The following section provides a deep dive into the Ocean framework, To learn more about the Ocean CLI, refer to the [CLI](./framework/cli/cli.md) docs

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
  - Kubernetes (using helm or ArgoCD)
  - AWS ECS (using Terraform module)
  - Azure Container App (using Terraform module)
  - Docker
  - As part of your CI pipeline, either manually or as part of a schedule

To learn more about the tools and abstractions provided by the Ocean framework to make it easier to develop new integrations, refer to the [features](./framework/features/features.md) docs.

## What is an Integration?

An **integration** is a standalone Python application that acts as a bridge between a 3rd-party system (like GitLab, Jira, AWS, etc.) and Port. Each integration is responsible for:

- **Extracting** data from the external system via its APIs
- **Transforming** that data using configurable JQ mappings
- **Synchronizing** the transformed data as entities into your Port catalog

Think of an integration as a specialized connector that knows how to talk to one specific 3rd-party tool and translate its data into Port's universal entity model.

### Operating Modes

Integrations powered by the Ocean framework support two methods to get data from 3rd-party systems:

**Exporter mode** — When the integration starts, and also every time its configuration changes, it queries the 3rd-party system, gathers the desired information, and sends it to Port:

<OceanExporterArchSvg/>

<br/>
<br/>

**Real-time updates mode** — (Optional) As the integration runs, it can listen to live events sent by the 3rd-party system (via webhooks) and send the results to Port in real-time:

<OceanRealTimeArchSvg/>

<br/>

Most integrations implement both modes: exporter mode ensures a complete sync of all data, while real-time mode keeps Port updated between syncs without waiting for the next scheduled resync.

### Relationship to Ocean Core

The Ocean framework is structured as a **monorepo** with two main components:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Ocean Core** | `port_ocean/` | The shared framework library providing common abstractions, handlers, and utilities |
| **Integrations** | `integrations/` | Individual integration implementations for specific 3rd-party systems |

**Ocean Core** (`port_ocean/`) provides:
- Authentication with Port's REST API
- High-throughput entity ingestion pipelines
- JQ-based data transformation engine
- Event listener infrastructure (polling, webhooks, Kafka)
- Resync orchestration and state management
- Webhook processor management for live events
- CLI tools for scaffolding and development

**Integrations** consume the core framework and implement:
- API clients specific to the 3rd-party system
- Resync handlers that define *what* data to fetch
- Webhook processors for real-time event handling
- Custom resource configurations and selectors

This separation allows integration developers to focus solely on the 3rd-party system logic while Ocean Core handles all the complexity of communicating with Port.

### Basic Integration Structure

Every integration follows a consistent file structure:

```
my-integration/
├── main.py                 # Core resync handlers and webhook processors
├── integration.py          # Custom resource configs and integration class
├── pyproject.toml          # Python dependencies and metadata
├── Makefile                # Common development commands
├── .port/
│   ├── spec.yaml           # Integration specification and configuration schema
│   └── resources/
│       ├── blueprints.json       # Default Port blueprints
│       └── port-app-config.yaml  # Default entity mappings
├── my_integration/         # (Optional) Additional modules
│   ├── clients/            # API client implementations
│   ├── helpers/            # Utility functions
│   └── webhook/            # Webhook processors
└── tests/                  # Unit and integration tests
```

**Key files explained:**

| File | Purpose |
|------|---------|
| `main.py` | Defines `@ocean.on_resync()` handlers that fetch data from the 3rd-party system, and registers webhook processors for live events |
| `integration.py` | Extends the base integration with custom resource configurations, selectors, and entity processors |
| `.port/spec.yaml` | Declares the integration's configuration schema (required parameters, secrets, features) |
| `.port/resources/` | Contains default blueprints and entity mappings that get created in Port |

### How an Integration Runs

When an integration starts, the following sequence occurs:

1. **Initialization**: Ocean Core loads the integration configuration from `spec.yaml` and connects to Port
2. **Default Resources**: Blueprints and mappings from `.port/resources/` are created/updated in Port
3. **Event Listener Setup**: Based on configuration, sets up polling, webhook, or Kafka-based event listening
4. **On Start Hooks**: Any `@ocean.on_start()` handlers execute (e.g., creating webhooks in the 3rd-party system)
5. **Resync Loop**: The integration fetches data from the 3rd-party system and syncs it to Port
6. **Live Events**: If configured, webhook processors handle real-time updates

### Important Things to Note

:::tip Key Concepts
Understanding these concepts will help you develop effective integrations:
:::

1. **Async-First Architecture**: All data fetching and processing uses Python's `async/await`. Use generators (`yield`) to stream large datasets without memory issues.

2. **Kind-Based Organization**: Data is organized by "kinds" (e.g., `project`, `group`, `merge-request`). Each kind has its own resync handler and can have custom selectors for filtering.

3. **JQ Mappings**: Raw API responses are transformed into Port entities using JQ expressions defined in `port-app-config.yaml`. The integration doesn't need to know about Port's entity structure.

4. **Resource Configurations**: Custom `Selector` and `ResourceConfig` classes in `integration.py` allow users to filter and customize what data gets synced.

5. **Webhook Processors**: For live events, create processor classes that inherit from `AbstractWebhookProcessor` and implement the `should_process_event` and `get_matching_kinds` methods.

6. **Event Contexts**: Ocean provides context objects (`ocean` and `event`) that give access to configuration, the current event being processed, and the Port client.

7. **Batching and Streaming**: Use `async for` with generators to yield data in batches. This prevents memory exhaustion and enables incremental progress.

8. **Configuration Precedence**: Integration config comes from multiple sources (environment variables, `.env` files, Port's integration settings). Ocean Core merges these automatically.

:::caution Common Pitfalls
- **Don't block the event loop**: Avoid synchronous I/O operations; use the async HTTP client from Ocean Core
- **Don't fetch everything at once**: Implement pagination and yield batches to handle large datasets
- **Don't hardcode mappings**: Let users define their own JQ mappings in Port's UI or config files
:::

## Next steps

- To view the list of integrations powered by the Ocean framework, refer to the [integrations library](./integrations-library/integrations-library.md) page
  - You can also take a look at the variety of integrations and methods to ingest data into Port at Port's [documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)
- To start developing your own integration with Port, powered by the Ocean framework, refer to the [getting started](./getting-started/getting-started.md) page
