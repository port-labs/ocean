---
sidebar_position: 1
slug: /
title: Overview
sidebar_label: 🌊 Overview
---

import OceanExporterArchSvg from '../static/img/ExportArchitecture.svg'
import OceanRealTimeArchSvg from '../static/img/RealTimeUpdatesArchitecture.svg'

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

## How do Ocean integrations work?

Integrations powered by the Ocean framework support two methods to get the desired information from the desired 3rd-party:

**Exporter mode** - when the integration starts, and also every time its configuration changes, it will query the 3rd-party system, gather the desired information and send it to Port:

<OceanExporterArchSvg/>

<br/>
<br/>

**Real-time updates mode** - (optional) as the integration runs, it can listen to webhook events sent by the 3rd-party system and send the results to Port in real-time:

<OceanRealTimeArchSvg/>

## Next steps

- To view the list of integrations powered by the Ocean framework, refer to the [integrations library](./integrations-library/integrations-library.md) page
  - You can also take a look at the variety of integrations and methods to ingest data into Port at Port's [documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)
- To start developing your own integration with Port, powered by the Ocean framework, refer to the [getting started](./getting-started/getting-started.md) page
