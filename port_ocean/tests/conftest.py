# ruff: noqa
pytest_plugins = ["port_ocean.tests.smoke.plugin"]

from port_ocean.tests.smoke.conftest import port_client_for_fake_integration
