---
title: Update Integration Code
sidebar_label: ⚙️ Update Integration Code
sidebar_position: 1
---

# ⚙️ Update Integration Code

This section outlines the structure of a brand new integration, as well as provide some standards and practices to add your own custom logic to the integration.

## Integration folder structure

After scaffolding a new integration (using the `ocean new` command), a new directory with the integration name you provided will be created, it will have the following structure:

```text
└── my_new_integration
    ├── tests
    │   └── __init__.py
    ├── pyproject.toml
    ├── poetry.toml
    ├── main.py
    ├── debug.py
    ├── config.yaml
    ├── changelog
    ├── README.md
    ├── Makefile
    ├── Dockerfile
    └── CHANGELOG.md
```

Let's go over some important files and how to use them during the integration's development.

## `main.py` - run an integration

This file serves as the entrypoint for the integration logic, when you scaffold a new integration it will already contain placeholders that guide you how and where in the code to implement your logic.

Of course since this file is only the entrypoint, you can add as many other `.py` files as needed and construct your own directory structure including classes and modules when developing your integration.

:::tip OCEAN SAIL
When running the command `ocean sail`, the Ocean CLI triggers a run of the integration using the `main.py` file, after loading all of the necessary context and resources required by the Ocean framework.

:::

## `debug.py` - debug an integration

This file is used to trigger a local development run of the integration, it is useful to debug your integration and examine its execution through your IDE or preferred Python debugging interface.

In most cases **you should not change this file**, only use it as the target for your debug execution of the integration.

## `pyproject.toml`

This file consists of 3 main responsibilities: 

- `version` - the integration's current version, should be bumped when a new version of the integration is released
- `dependencies` - the integration's dependencies, should be updated when new dependencies are added to the integration
- Configuration for automated tools that ensure consistent code quality for every developed integration. These
  include `mypy`, `ruff` and `black`. In addition it includes the setup for `towncrier` to maintain a proper CHANGELOG
  for the integration.

### Add dependencies to the integration

It is very common that an integration needs to make HTTP requests or utilize some 3rd-party library to perform its unique logic. This means the integration requires additional dependencies during its runtime.

Ocean framework integrations use Poetry to manage their dependencies, you can refer to the Poetry website for the CLI reference and documentation, here are some common commands:

- `poetry install` - install all dependencies listed in the `pyproject.toml` file in the virtual env of the integration
- `poetry add X` - add the specified package to the list of dependencies required by the integration (and also install it)
  - `poetry add -D x` - add the specified package to the list of dev dependencies used during the integration's development (and also install it)
- `poetry remove X` - remove the specified package from the list of dependencies used by the integration
