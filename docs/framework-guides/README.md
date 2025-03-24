<h1 align="center">
  <p align="center">Port Documentation</p>
  <a href="https://docs.port.io"><img src="https://port-graphical-assets.s3.eu-west-1.amazonaws.com/Port+Logo.svg" alt="Port"></a>
</h1>

<p align="center">
  <a href="https://github.com/port-labs/port-docs/actions/workflows/verify-docs-build.yml"><img src="https://github.com/port-labs/port-docs/actions/workflows/verify-docs-build.yml/badge.svg" alt="GitHub Actions status"></a>
  <a href= "https://github.com/prettier/prettier"><img alt="code style: prettier" src="https://img.shields.io/badge/code_style-prettier-ff69b4.svg"></a>

</p>

## Introduction

Port is a Developer Platform made to make life easier for developers and DevOps in an organization, by creating a single platform that acts as a single source-of-truth for all of the infrastructure assets and operations existing in the organization's tech stack.

## Port's documentation

This is the repository for Port's documentation website (available at [https://docs.port.io](https://docs.port.io))

Port's documentation is built using [Docusaurus 2](https://docusaurus.io/), a modern static website generator.

Our documentation is hosted using [AWS Amplify](https://aws.amazon.com/amplify/).

## Installation

Install [NodeJS](https://nodejs.org), it is recommended to use [NVM](https://github.com/nvm-sh/nvm#install--update-script) to make installation and management of different NodeJS versions on the same machine easier:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
# After this, you can use nvm to install the latest version of node:
nvm install node
```

If you prefer installing NodeJS directly, please install the are not using NVM, just install the latest LTS version of Node.

Next, clone this repository and then in the project directory run:

```bash
npm install
```

Then run:

```bash
npm run start
```

The docs will start running locally on [https://localhost:4000](https://localhost:4000)

## Contributing

Port's documentation is open source because we want the documentation to be the most comprehensive resource for users to learn how to use Port. We believe that developers and DevOps professionals who use Port on a daily basis will want to contribute and help make it that comprehensive resource.

In order to learn how you can contribute to Port's documentation, read our [contributing guide](./CONTRIBUTING.md)
