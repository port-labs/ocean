"""Regression tests for ``ResourceInspector`` concurrent merge alignment.

``ResourceInspector.inspect`` correlates concurrent action results positionally
(``resource_data[idx] |= item``), so every action implementation must return
one entry per input identifier in input order. These tests document and lock
in that contract: they fail loudly if anyone reintroduces a code path that
silently drops items (the bug class that caused enrichment data to attach to
the wrong AWS resource).
"""

from typing import Any, Dict, List, Type

import pytest
from pydantic import BaseModel
from unittest.mock import AsyncMock

from aws.core.interfaces.action import Action
from aws.core.modeling.resource_inspector import ResourceInspector
from aws.core.modeling.resource_models import ResourceModel

_FakeActionInput = List[str]


class _FakeProperties(BaseModel):
    class Config:
        extra = "allow"


class _FakeResource(ResourceModel[_FakeProperties]):
    Type: str = "Test::Fake::Resource"
    Properties: _FakeProperties = _FakeProperties()


def _make_action_class(
    name: str, payloads: List[Dict[str, Any]]
) -> Type[Action[_FakeActionInput]]:
    """Build a one-off Action subclass that returns a canned payload list."""

    async def _execute(
        self: Action[_FakeActionInput], identifiers: _FakeActionInput
    ) -> List[Dict[str, Any]]:
        return payloads

    return type(name, (Action,), {"_execute": _execute})


class _FakeActionMap:
    """Minimal ActionMap that returns the supplied action classes verbatim."""

    def __init__(self, actions: List[Type[Action[_FakeActionInput]]]) -> None:
        self.defaults: List[Type[Action[_FakeActionInput]]] = actions
        self.options: List[Type[Action[_FakeActionInput]]] = []

    def merge(self, include: List[str]) -> List[Type[Action[_FakeActionInput]]]:
        return list(self.defaults)


class TestResourceInspectorAlignment:
    @pytest.mark.asyncio
    async def test_placeholder_keeps_sibling_actions_correlated(self) -> None:
        """An empty dict at index ``i`` from action B must not pull index ``i+1``
        into index ``i`` when merged with action A's aligned full-length result.
        """
        action_a = _make_action_class("ActionA", [{"a": 1}, {"a": 2}, {"a": 3}])
        action_b = _make_action_class("ActionB", [{"b": 1}, {}, {"b": 3}])

        inspector = ResourceInspector[_FakeResource, _FakeActionInput](
            AsyncMock(),
            _FakeActionMap([action_a, action_b]),
            _FakeResource,
        )

        resources = await inspector.inspect(["res-1", "res-2", "res-3"], include=[])

        assert len(resources) == 3
        # Resource 0 gets data from both actions; resource 1 only from A
        # because B's placeholder is a no-op; resource 2 again from both.
        assert resources[0]["Properties"] == {"a": 1, "b": 1}
        assert resources[1]["Properties"] == {"a": 2}
        assert resources[2]["Properties"] == {"a": 3, "b": 3}

    @pytest.mark.asyncio
    async def test_missing_placeholder_corrupts_alignment(self) -> None:
        """Regression guard: locks in what the bug looked like.

        If an action erroneously skips an entry instead of appending an empty
        placeholder, ``ResourceInspector`` shifts subsequent entries by one
        position so resource 2 receives resource 3's enrichment data. This
        test documents the failure mode so any new action that reintroduces
        the bug pattern will trip this assertion in CI.
        """
        action_a = _make_action_class("ActionA", [{"a": 1}, {"a": 2}, {"a": 3}])
        # Buggy shape: only two entries for three inputs (index 1 was skipped
        # without a placeholder, as the pre-fix code did on a recoverable
        # error).
        action_b = _make_action_class("ActionB", [{"b": 1}, {"b": 3}])

        inspector = ResourceInspector[_FakeResource, _FakeActionInput](
            AsyncMock(),
            _FakeActionMap([action_a, action_b]),
            _FakeResource,
        )

        resources = await inspector.inspect(["res-1", "res-2", "res-3"], include=[])

        assert len(resources) == 3
        # res-1 still aligned; res-2 INCORRECTLY receives action B's second
        # entry which actually belongs to res-3; res-3 only has action A.
        assert resources[0]["Properties"] == {"a": 1, "b": 1}
        assert resources[1]["Properties"] == {"a": 2, "b": 3}  # corrupted
        assert resources[2]["Properties"] == {"a": 3}
