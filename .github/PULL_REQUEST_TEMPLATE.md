# Description

What -

Why -

How -

## Type of change

Please leave one option from the following and delete the rest:

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] New Integration (non-breaking change which adds a new integration)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Non-breaking change (fix of existing functionality that will not change current behavior)
- [ ] Documentation (added/updated documentation)

<h4> All tests should be run against the port production environment(using a testing org). </h4>

### Core testing checklist

- [ ] Integration able to create all default resources from scratch
- [ ] Resync finishes successfully
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Scheduled resync able to abort existing resync and start a new one
- [ ] Tested with at least 2 integrations from scratch
- [ ] Tested with Kafka and Polling event listeners
- [ ] Tested deletion of entities that don't pass the selector


### Integration testing checklist

- [ ] Integration able to create all default resources from scratch
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Resync finishes successfully
- [ ] If new resource kind is added or updated in the integration, add example raw data, mapping and expected result to the `examples` folder in the integration directory.
- [ ] If resource kind is updated, run the integration with the example data and check if the expected result is achieved
- [ ] If new resource kind is added or updated, validate that live-events for that resource are working as expected
- [ ] Docs PR link [here](#)

### Preflight checklist

- [ ] Handled rate limiting
- [ ] Handled pagination
- [ ] Implemented the code in async
- [ ] Support Multi account

## Screenshots

Include screenshots from your environment showing how the resources of the integration will look.

## API Documentation

Provide links to the API documentation used for this integration.
