---
title: 🗺 Development Guidelines
---

import Structure from './_integration_structure.md'

This section provides guidelines for developing an integration.

## Integration structure

An integration should follow the following structure:

<Structure />

## Important development guidelines

- Use httpx for making HTTP requests (a requests like library that supports async)
- Use the Ocean CLI or the make new command to scaffold a new integration
- Make sure that your integration is passing all linting and type checks
- Be agnostic to the integration usage, do not assume it will be used in a specific way and try to just return the data as-is
- Extensions to the basic kind data with additional custom fields should be done using in keys that start with `__` (e.g. `__my_custom_field`)