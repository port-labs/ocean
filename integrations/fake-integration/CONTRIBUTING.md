# Contributing to Ocean - Fake Integration

## Running locally

`make run`

This fake integration will create random "people" using the python package `faker`.

The fake integration exposes the HTTP routes that simulate the "3rd party" integration.

In the `./fake_org_data/fake_client.py` we actually call the integration itself.

You can create your own routes in `./fake_org_data/faker_router.py` and add more "kinds" / customize the existing ones for your usage.
