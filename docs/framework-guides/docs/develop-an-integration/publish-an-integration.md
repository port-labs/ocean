---
title: Publish an Integration
sidebar_label: 📦 Publish an Integration
sidebar_position: 4
---

# 📦 Publish an Integration

This guide outlines the steps required to publish an integration built using the Ocean framework.

This guide assumes that you already went through the [quickstart](../getting-started/getting-started.md) and you have an integration in development.

## Prerequisites

- Ensure you have a `.port` folder with a `spec.yaml` file that holds information about the integration, including version, configuration, features, and type.
- Your integration should pass the following linting checks using the `make lint` command:
  - `black` for code formatting.
  - `mypy` for type checking.
  - `ruff` for code quality analysis.
  - `poetry check` for dependency checks.

:::note

All of the integrations powered by Ocean are expected to pass the automated CI check, when you open a PR to the [Port Ocean](https://github.com/port-labs/port-ocean) repository in Github, Port's CI will validate that your new code passes the CI checks and Port's team will only merge your code once it passes.

:::

## Steps to publish an integration

### Create a fork

Fork the Ocean framework repository to your GitHub account. This will create a copy of the repository under your account.

### Clone your fork

Clone the forked repository to your local machine using the following command:

```bash showLineNumbers
git clone https://github.com/your-username/ocean-framework.git
```

### Add your integration

Place your integration code inside the `integrations` folder of your local repository. Ensure the file hierarchy matches that of other public integrations.

### Run linting and checks

Run `make lint` to ensure your integration meets the required quality standards as specified in the [prerequisites](#prerequisites) section

### Commit and push

Commit your changes to the branch and push the changes to your fork on GitHub.

### Open a pull request

Open a pull request from your branch in your fork to the `main` branch of the Ocean framework repository.

### Review and collaboration

Collaborate with the community and maintainers to address any feedback on your pull request. Make necessary changes to ensure your integration aligns with the framework's standards.

### Merge and publish

Once your pull request is approved and passes all checks, it will be merged into the main repository. Your integration will now be available to all users of Port and the Ocean framework.

## Publishing a new version

When merging a new version of your integration, ensure that the version number in the `spec.yaml` file is updated. This will allow the CI to detect the new version and publish it to port's image registry.

## Conclusion

Publishing an Ocean integration allows you to contribute to Port's capabilities and extend its integration library, by leveraging the abstractions provided by the Ocean framework. Following the steps outlined in this guide ensures that your integration meets the framework's quality standards and becomes a valuable addition to the framework.
