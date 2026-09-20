import pytest

from actions.abstract_action_input import AbstractPagerDutyActionInput
from actions.exceptions import MissingExecutionPropertyError


class _SampleInput(AbstractPagerDutyActionInput):
    name: str


class TestAbstractPagerDutyActionInput:
    def test_from_execution_properties(self) -> None:
        inputs = _SampleInput.from_execution_properties({"name": "test"})
        assert inputs.name == "test"

    def test_from_execution_properties_raises_on_validation_error(self) -> None:
        with pytest.raises(MissingExecutionPropertyError, match="Field required"):
            _SampleInput.from_execution_properties({})

    def test_ignores_unknown_execution_properties(self) -> None:
        inputs = _SampleInput.from_execution_properties(
            {"name": "test", "unexpectedField": "ignored"}
        )
        assert inputs.name == "test"
