from enum import StrEnum


class ObjectKind(StrEnum):
    """The resource kinds supported by the Sonatype Lifecycle integration.

    The string values are the identifiers used in ``.port/resources`` mappings,
    in ``spec.yaml`` and by the ``@ocean.on_resync(...)`` decorators.
    """

    ORGANIZATION = "organization"
    APPLICATION = "application"
    REPORT = "report"
    POLICY_VIOLATION = "policyViolation"
    COMPONENT = "component"
    VULNERABILITY = "vulnerability"
    SOURCE_CONTROL = "sourceControl"
