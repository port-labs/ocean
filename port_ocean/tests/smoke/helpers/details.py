from os import environ

from pydantic.v1 import BaseModel


class SmokeTestDetails(BaseModel):
    integration_identifier: str
    blueprint_department: str
    blueprint_person: str
    integration_type: str
    integration_version: str


def get_smoke_test_details() -> SmokeTestDetails:
    blueprint_department = "fake-department"
    blueprint_person = "fake-person"
    integration_identifier = "smoke-test-integration"
    smoke_test_suffix = environ.get("SMOKE_TEST_SUFFIX")
    if smoke_test_suffix is not None:
        integration_identifier = f"{integration_identifier}-{smoke_test_suffix}"
        blueprint_person = f"{blueprint_person}-{smoke_test_suffix}"
        blueprint_department = f"{blueprint_department}-{smoke_test_suffix}"

    return SmokeTestDetails(
        integration_identifier=integration_identifier,
        blueprint_person=blueprint_person,
        blueprint_department=blueprint_department,
        integration_version="0.1.4-dev",
        integration_type="smoke-test",
    )
