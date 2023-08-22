---
title: 🗺 Development Guidelines
---

import Structure from './_integration_structure.md'
import HttpxExample from '../_common/httpx-instead-of-requests.md'

This section provides guidelines for developing an integration.

## Integration structure

An integration should follow the following structure:

<Structure />

## Important development guidelines

### `httpx` instead of `requests`

<HttpxExample />

### Scaffold using the CLI

Use the Ocean CLI or the make new command to scaffold a new integration

`ocean new` or `make new`

### Integration maturity

Make sure that your integration is passing all linting and type checks as described in
the [Publishing](../develop-an-integration/publish-an-integration.md#prerequisites) page.

Use `make lint` to run the linting locally

### Integration should be agnostic

Be agnostic to the integration usage, do not assume it will be used in a specific way and try to just return the data
as-is

Extensions to the basic kind data with additional custom fields should be done using in keys that start with `__` (
e.g. `__my_custom_field`)

### Logging

Use loguru for logging

```python
from loguru import logger

logger.info('Hello World')
```

### Performance

Make sure your integration is performant and does not block the event loop for too long.

You can read more about possible performance enhancements in the [Performance](../develop-an-integration/performance.md)

### Code Principles

1. > "_Simple is better than complex._" - [The Zen of Python](https://peps.python.org/pep-0020/#the-zen-of-python)

   It suggests that it's better to have straightforward and easy-to-understand solutions rather than overly intricate
   ones. Complex code can be harder to maintain, debug, and extend. Prioritizing simplicity helps in creating code
   that's more readable and approachable for everyone involved.

   consider splitting the `main.py` into multiple files and import to import them.

   :::tip ✅ Do

    ```python
    # Do use simple and straightforward code
    result = 0
    for num in range(1, 11):
        result += num
    print(result)
    ```

   :::

   :::danger ❌ Don't

    ```python
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

    ```python
    # Do use a single level of nesting for clarity
    if condition:
        do_something()
    else:
        do_another_thing()
    ```

   :::

   :::danger ❌ Don't

    ```python
    # Don't nest multiple conditions excessively
    if condition1:
        if condition2:
            if condition3:
                do_something()
    ```

   :::

3. "_Readability Counts._"  - [The Zen of Python](https://peps.python.org/pep-0020/#the-zen-of-python)

   This principle emphasizes the significance of writing code that is easy to read and understand. Code is often read by
   other developers, including your future self, so it's crucial to prioritize clarity over cleverness.

   :::tip ✅ Do

    ```python
    # Choose meaningful variable, function, and class names that convey their purpose or functionality.
    # Avoid single-letter or cryptic names.
    total_score = calculate_total_score()
    ```

   :::

   :::danger ❌ Don't

    ```python
    # Don't use single-letter or cryptic names
    ts = calc_score()
    ```

   :::