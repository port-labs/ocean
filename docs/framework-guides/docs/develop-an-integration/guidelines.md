---
title: Development Guidelines
sidebar_label: 🚧 Development Guidelines
sidebar_position: 6
---

# 🚧 Development Guidelines

import Structure from './\_mdx/integration_structure.md'
import HttpxExample from '../\_common/httpx-instead-of-requests.md'

This section provides guidelines for developing an integration.

## Integration structure

An integration should follow the following structure:

<Structure />

## Important development guidelines

### `httpx` instead of `requests`

<HttpxExample />

### Scaffold using the CLI

To scaffold a new integration you can use the following options:

- `ocean new` - available through the Ocean CLI
- `make new` - available when cloning the [Ocean](https://github.com/port-labs/port-ocean) repository locally

### Integration maturity

Make sure that your integration passes linting and type checks as described in
the [Publishing](../develop-an-integration/publish-an-integration.md#prerequisites) page.

Use `make lint` to run the linting locally

### Integration should be agnostic

Be agnostic to the integration usage, do not assume it will be used in a specific way and try to just return the data
as-is. Integration users can use the mapping configuration to choose how to ingest the data into Port, the integration
should serve as a straightforward way to get the raw data from the 3rd-party for mapping.

Extensions to the basic kind data with additional custom fields should be done using keys that start with `__` (
e.g. `__my_custom_field`)

### Logging

Use loguru for logging

```python showLineNumbers
from loguru import logger

logger.info('Hello World')
```

### Live Events (Webhook)

When handling live events in the integration, make sure to not register the event data as the data to sync.
Often the data incoming from the live event is not the same as the data that is being retrieved from the api, which will
cause to an inconsistency in the data passed to the transformation and can result in inconsistent entities.

### Accessing the configuration

The integration configuration is available in the `ocean.integration_config` variable.

The configuration is a dictionary that contains the configuration keys in a CamelCase format.

:::info
The configuration is parsed from the environment variables, config.yml and the pydantic model defaults and later on
formatted to a CamelCase format.
:::

### Performance

Make sure your integration is performant and does not block the event loop if possible.

You can read more about possible performance enhancements in the [performance](../develop-an-integration/performance.md)
page

### Code Principles

1. > "_Simple is better than complex._" - [The Zen of Python](https://peps.python.org/pep-0020/#the-zen-of-python)

   It suggests that it's better to have straightforward and easy-to-understand solutions rather than overly intricate
   ones. Complex code can be harder to maintain, debug, and extend. Prioritizing simplicity helps in creating code
   that's more readable and approachable for everyone involved.

   consider splitting the `main.py` into multiple files and import them when needed.

   :::tip ✅ Do

   ```python showLineNumbers
   # Do use simple and straightforward code
   result = 0
   for num in range(1, 11):
       result += num
   print(result)
   ```

   :::

   :::danger ❌ Don't

   ```python showLineNumbers
   # Don't use unnecessarily complex expressions
   result = sum([num for num in range(1, 11)])
   print(result)
   ```

   :::

2. > "_Flat is better than nested._" - [The Zen of Python](https://peps.python.org/pep-0020/#the-zen-of-python)

   This means that keeping code structures shallow and avoiding deeply nested blocks or structures can improve
   readability and make it easier to follow the logic. It encourages breaking down complex tasks into separate functions
   and modules instead of creating deeply nested structures that can be difficult to comprehend.

   :::tip ✅ Do

   ```python showLineNumbers
   # Do use a single level of nesting for clarity
   if condition:
       do_something()
   else:
       do_another_thing()
   ```

   :::

   :::danger ❌ Don't

   ```python showLineNumbers
   # Don't nest multiple conditions excessively
   if condition1:
       if condition2:
           if condition3:
               do_something()
   ```

   :::

3. "_Readability Counts._" - [The Zen of Python](https://peps.python.org/pep-0020/#the-zen-of-python)

   This principle emphasizes the significance of writing code that is easy to read and understand. Code is often read by
   other developers, including your future self, so it's crucial to prioritize clarity over cleverness.

   :::tip ✅ Do

   ```python showLineNumbers
   # Choose meaningful variable, function, and class names that convey their purpose or functionality.
   # Avoid single-letter or cryptic names.
   total_score = calculate_total_score()
   ```

   :::

   :::danger ❌ Don't

   ```python showLineNumbers
   # Don't use single-letter or cryptic names
   ts = calc_score()
   ```

   :::
